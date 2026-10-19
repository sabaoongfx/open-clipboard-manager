"""Linux backend for Open Clipboard Manager.

- Clipboard: `xclip` on X11, `wl-clipboard` (`wl-paste` / `wl-copy`) on Wayland. Neither desktop offers a
  cheap "the clipboard changed" signal to a plain script, so the change token is a hash of what is on it.
- Global hotkey: X11 only (python-xlib). Wayland gives apps no global hotkeys; bind a desktop shortcut to
  `python winclipman.py --show` instead (it opens the window of the running app).
- Pasting into the previous window: `xdotool` on X11, `wtype` or `ydotool` on Wayland.

Written and unit-tested without a Linux desktop to hand; the CI job runs the tests on Ubuntu.
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import threading

from PIL import Image

from platform_base import APP_DIR, ENTRY_SCRIPT, PlatformBase

AUTOSTART_FILE = os.path.expanduser("~/.config/autostart/open-clipboard-manager.desktop")

# X11 modifier masks (from X.h), so a hotkey can be parsed without python-xlib installed.
SHIFT_MASK, LOCK_MASK, CONTROL_MASK, ALT_MASK, NUM_LOCK_MASK, SUPER_MASK = 1, 2, 4, 8, 16, 64

TEXT_TARGETS = ("text/plain;charset=utf-8", "UTF8_STRING", "text/plain", "STRING")
IMAGE_TARGETS = ("image/png", "image/bmp", "image/jpeg")


def _parse_hotkey(spec):
    """Return (modifier mask, X keysym name) for text like "ctrl+alt+h"."""
    mods, key = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= CONTROL_MASK
        elif part in ("alt", "option"):
            mods |= ALT_MASK
        elif part == "shift":
            mods |= SHIFT_MASK
        elif part in ("super", "win", "cmd", "command"):
            mods |= SUPER_MASK
        elif re.fullmatch(r"f([1-9]|1[0-2])", part):
            key = part.upper()
        elif len(part) == 1 and part.isalnum():
            key = part
        else:
            raise ValueError(f"unsupported hotkey part: {part!r}")
    if key is None or mods == 0:
        raise ValueError("hotkey needs at least one modifier and one key")
    return mods, key


def is_wayland(environ=os.environ):
    return environ.get("XDG_SESSION_TYPE", "").lower() == "wayland" or (
        bool(environ.get("WAYLAND_DISPLAY")) and not environ.get("DISPLAY"))


class _X11Hotkey:
    """Grabs one key combination on the X11 root window and calls back when it is pressed."""

    def __init__(self, spec, on_trigger, on_error):
        self.mods, self.key = _parse_hotkey(spec)
        self.spec, self.on_trigger, self.on_error = spec, on_trigger, on_error
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.ok = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        self.ready.wait(3)
        return self.ok

    def stop(self):
        self.stop_event.set()
        self.thread.join(2)

    def _run(self):
        try:
            from Xlib import X, XK, display, error
        except ImportError:
            self.on_error("The global hotkey needs python-xlib: pip install python-xlib")
            self.ready.set()
            return
        try:
            disp = display.Display()
            root = disp.screen().root
            keycode = disp.keysym_to_keycode(XK.string_to_keysym(self.key))
            if not keycode:
                raise ValueError(f"no key named {self.key!r} on this keyboard")
            problems = []
            handler = error.CatchError(error.BadAccess)
            # Num Lock and Caps Lock change the modifier state, so grab every combination of them.
            for extra in (0, LOCK_MASK, NUM_LOCK_MASK, LOCK_MASK | NUM_LOCK_MASK):
                root.grab_key(keycode, self.mods | extra, True, X.GrabModeAsync, X.GrabModeAsync, onerror=handler)
            disp.sync()
            if handler.get_error():
                problems.append("it is already used by another program")
            if problems:
                self.on_error(f"Could not register hotkey {self.spec}: {problems[0]}.")
                disp.close()
                self.ready.set()
                return
        except Exception as e:  # no X server, no such key, ...
            self.on_error(f"Could not register hotkey {self.spec}: {e}")
            self.ready.set()
            return
        self.ok = True
        self.ready.set()
        while not self.stop_event.is_set():
            while disp.pending_events():
                event = disp.next_event()
                if event.type == X.KeyPress:
                    self.on_trigger()
            self.stop_event.wait(0.05)
        try:
            root.ungrab_key(keycode, X.AnyModifier)
            disp.sync()
        finally:
            disp.close()


class Platform(PlatformBase):
    name = "linux"
    default_hotkey = "super+v"
    default_actions_file = os.path.join(APP_DIR, "actions_linux.json")
    data_dir = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "winclipman")
    ui_font = "DejaVu Sans"

    def __init__(self):
        self.wayland = is_wayland()
        self._backend = self._detect_backend()
        self._snapshot = None
        self._hotkey = None
        self._on_trigger = self._on_error = None
        self.hotkey_examples = (
            "Not available on Wayland. Bind a desktop shortcut to: python winclipman.py --show"
            if self.wayland else "e.g. super+v, ctrl+alt+h, ctrl+shift+v")

    # -- helpers ------------------------------------------------------------------
    def _detect_backend(self):
        if self.wayland and shutil.which("wl-paste") and shutil.which("wl-copy"):
            return "wl"
        if shutil.which("xclip"):
            return "xclip"
        return None

    @staticmethod
    def _run(args, data=None, timeout=3):
        """Run a helper program; returns its stdout bytes, or None if it is missing or failed."""
        try:
            result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result.stdout if result.returncode == 0 else None

    @staticmethod
    def _spawn_owner(args, data):
        """Start a program that owns the clipboard in the background (xclip, wl-copy) and feed it data."""
        try:
            proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            proc.stdin.write(data)
            proc.stdin.close()
            proc.wait(timeout=3)
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _targets(self):
        if self._backend == "wl":
            out = self._run(["wl-paste", "--list-types"])
        elif self._backend == "xclip":
            out = self._run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"])
        else:
            out = None
        return out.decode("utf-8", "replace").split() if out else []

    def _read(self, mime):
        if self._backend == "wl":
            return self._run(["wl-paste", "--no-newline", "--type", mime])
        return self._run(["xclip", "-selection", "clipboard", "-t", mime, "-o"])

    def _read_snapshot(self):
        targets = self._targets()
        text = image = None
        for mime in TEXT_TARGETS:
            if mime in targets:
                data = self._read(mime)
                if data is not None:
                    text = data.decode("utf-8", "replace")
                    break
        if text is None:
            for mime in IMAGE_TARGETS:
                if mime in targets:
                    image = self._read(mime)
                    if image:
                        break
        digest = hashlib.sha1(image).hexdigest() if image else None
        self._snapshot = (text, image, hash((tuple(targets), text, digest)))
        return self._snapshot

    # -- clipboard ------------------------------------------------------------------
    def clipboard_token(self):
        """A value that changes whenever the clipboard content changes (it reads the clipboard to compute it)."""
        return self._read_snapshot()[2]

    def get_text(self):
        return (self._snapshot or self._read_snapshot())[0]

    def get_image(self):
        data = (self._snapshot or self._read_snapshot())[1]
        if not data:
            return None
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except (OSError, ValueError):
            return None

    def set_text(self, text):
        self._snapshot = None
        data = text.encode("utf-8")
        if self._backend == "wl":
            return self._spawn_owner(["wl-copy", "--type", "text/plain;charset=utf-8"], data)
        if self._backend == "xclip":
            return self._spawn_owner(["xclip", "-selection", "clipboard", "-t", "UTF8_STRING", "-i"], data)
        return False

    def set_image(self, img):
        self._snapshot = None
        buf = io.BytesIO()
        img.save(buf, "PNG")
        data = buf.getvalue()
        if self._backend == "wl":
            return self._spawn_owner(["wl-copy", "--type", "image/png"], data)
        if self._backend == "xclip":
            return self._spawn_owner(["xclip", "-selection", "clipboard", "-t", "image/png", "-i"], data)
        return False

    # -- pasting into the previously active window ---------------------------------
    def activate_self(self):
        """The window manager raises our window; nothing to do."""

    def remember_foreground(self):
        if self.wayland or not shutil.which("xdotool"):
            return None
        out = self._run(["xdotool", "getactivewindow"])
        return out.decode().strip() if out else None

    def focus(self, window):
        if window:
            self._run(["xdotool", "windowactivate", "--sync", str(window)])

    def send_paste(self):
        if self.wayland:
            if shutil.which("wtype"):
                self._run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"])
            elif shutil.which("ydotool"):
                self._run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"])
        elif shutil.which("xdotool"):
            self._run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])

    # -- global hotkey ------------------------------------------------------------
    def validate_hotkey(self, spec):
        _parse_hotkey(spec)

    def start_hotkey(self, spec, on_trigger, on_error):
        """Grab the hotkey on X11; raises ValueError for a bad spec. A no-op on Wayland."""
        _parse_hotkey(spec)
        self._on_trigger, self._on_error = on_trigger, on_error
        if self.wayland:
            return
        self._hotkey = _X11Hotkey(spec, on_trigger, on_error)
        self._hotkey.start()

    def change_hotkey(self, spec):
        """Switch to a new, already validated hotkey; falls back to the old one if it is taken."""
        if self.wayland or self._on_trigger is None:
            return
        previous = self._hotkey
        if previous:
            previous.stop()
        candidate = _X11Hotkey(spec, self._on_trigger, self._on_error)
        if candidate.start():
            self._hotkey = candidate
        elif previous:
            restored = _X11Hotkey(previous.spec, self._on_trigger, self._on_error)
            restored.start()
            self._hotkey = restored

    # -- appearance ---------------------------------------------------------------
    def is_dark_mode(self):
        for key in ("color-scheme", "gtk-theme"):
            out = self._run(["gsettings", "get", "org.gnome.desktop.interface", key], timeout=2)
            if out and ("dark" in out.decode("utf-8", "replace").lower()):
                return True
        return False

    # -- start with the OS --------------------------------------------------------
    def _launch_command(self):
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" "{ENTRY_SCRIPT}"'

    def autostart_enabled(self):
        return os.path.exists(AUTOSTART_FILE)

    def set_autostart(self, enabled):
        if not enabled:
            try:
                os.remove(AUTOSTART_FILE)
            except FileNotFoundError:
                pass
            return
        os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
        with open(AUTOSTART_FILE, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Open Clipboard Manager\n"
                    f"Exec={self._launch_command()}\nX-GNOME-Autostart-enabled=true\n")

    # -- files and commands -------------------------------------------------------
    def open_path(self, path):
        subprocess.Popen(["xdg-open", path])

    def edit_file(self, path):
        subprocess.Popen(["xdg-open", path])

    def sanitize_arg(self, value):
        """Make clipboard text safe to place inside "double quotes" in a sh command line."""
        return re.sub(r'["\\$`\r\n]', "", value)
