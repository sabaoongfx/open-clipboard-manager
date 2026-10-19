"""macOS backend for Open Clipboard Manager:NSPasteboard clipboard, Carbon hotkey, paste and LaunchAgent autostart.

Written without access to a Mac: it has not been run on macOS yet.
"""
import ctypes
import ctypes.util
import io
import os
import plistlib
import re
import subprocess
import sys

from PIL import Image

try:
    from AppKit import (NSApplicationActivateIgnoringOtherApps, NSPasteboard, NSPasteboardTypePNG,
                        NSPasteboardTypeString, NSPasteboardTypeTIFF, NSRunningApplication, NSWorkspace)
    from Foundation import NSData
except ImportError:
    raise SystemExit("Open Clipboard Manager needs PyObjC on macOS: pip install pyobjc-framework-Cocoa")

from platform_base import APP_DIR, ENTRY_SCRIPT, PlatformBase

LAUNCH_AGENT = os.path.expanduser("~/Library/LaunchAgents/io.github.openclipboardmanager.plist")

# Carbon hot keys need no Accessibility permission and are delivered through the app's own
# event loop, so they work alongside Tk without a separate listener thread.
K_EVENT_CLASS_KEYBOARD = 0x6B657962  # 'keyb'
K_EVENT_HOTKEY_PRESSED = 5
MOD_CMD, MOD_SHIFT, MOD_OPTION, MOD_CONTROL = 0x100, 0x200, 0x800, 0x1000
HOTKEY_SIGNATURE = 0x57434C50  # 'WCLP'

# Virtual key codes (ANSI keyboard layout).
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def _parse_hotkey(spec):
    mods, key = 0, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part in ("alt", "option", "opt"):
            mods |= MOD_OPTION
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("cmd", "command", "win", "super"):
            mods |= MOD_CMD
        elif part in KEY_CODES:
            key = KEY_CODES[part]
        else:
            raise ValueError(f"unsupported hotkey part: {part!r}")
    if key is None or mods == 0:
        raise ValueError("hotkey needs at least one modifier and one key")
    return mods, key


class Platform(PlatformBase):
    name = "macos"
    # The Mac's "Windows key" is Cmd, but Cmd+V is the system Paste shortcut, so the default adds Ctrl.
    default_hotkey = "ctrl+cmd+v"
    hotkey_examples = "e.g. ctrl+cmd+v, ctrl+alt+h, cmd+shift+v"
    default_actions_file = os.path.join(APP_DIR, "actions_macos.json")
    data_dir = os.path.expanduser("~/Library/Application Support/winclipman")
    ui_font = ".AppleSystemUIFont"

    def is_dark_mode(self):
        result = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                                capture_output=True, text=True)
        return result.stdout.strip() == "Dark"

    # -- clipboard ------------------------------------------------------------
    def clipboard_token(self):
        """A value that changes whenever the clipboard content changes."""
        return NSPasteboard.generalPasteboard().changeCount()

    def get_text(self):
        """Return the clipboard's text, or None if it holds no text."""
        text = NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)
        return str(text) if text is not None else None

    def set_text(self, text):
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        return bool(pb.setString_forType_(text, NSPasteboardTypeString))

    def get_image(self):
        """Return a PIL image if the clipboard holds a bitmap, else None."""
        pb = NSPasteboard.generalPasteboard()
        for kind in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            data = pb.dataForType_(kind)
            if data is not None:
                try:
                    img = Image.open(io.BytesIO(bytes(data)))
                    img.load()
                    return img
                except (OSError, ValueError):
                    return None
        return None

    def set_image(self, img):
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png = buf.getvalue()
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        return bool(pb.setData_forType_(NSData.dataWithBytes_length_(png, len(png)), NSPasteboardTypePNG))

    # -- pasting into the previously active app ---------------------------------
    def activate_self(self):
        """Bring our own windows to the front (a plain script is not an active app by default)."""
        NSRunningApplication.currentApplication().activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def remember_foreground(self):
        return NSWorkspace.sharedWorkspace().frontmostApplication()

    def focus(self, app):
        if app is not None:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def send_paste(self):
        # Needs the Accessibility permission for the app running Python (System Settings > Privacy & Security).
        subprocess.Popen(["osascript", "-e",
                          'tell application "System Events" to keystroke "v" using command down'])

    # -- global hotkey ----------------------------------------------------------
    def validate_hotkey(self, spec):
        if _parse_hotkey(spec) == (MOD_CMD, KEY_CODES["v"]):
            raise ValueError("Cmd+V is the system Paste shortcut; add another modifier, e.g. ctrl+cmd+v")

    def start_hotkey(self, spec, on_trigger, on_error):
        """Register the hotkey; raises ValueError for a bad spec."""
        self.validate_hotkey(spec)
        self._on_trigger, self._on_error = on_trigger, on_error
        self._ref = None
        self._active = None
        self._carbon = ctypes.CDLL(ctypes.util.find_library("Carbon"))
        carbon = self._carbon
        carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        carbon.InstallEventHandler.argtypes = [ctypes.c_void_p, _HANDLER, ctypes.c_uint32,
                                               ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p, ctypes.c_void_p]
        carbon.InstallEventHandler.restype = ctypes.c_int32
        carbon.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
                                               ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        carbon.RegisterEventHotKey.restype = ctypes.c_int32
        carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        carbon.UnregisterEventHotKey.restype = ctypes.c_int32

        def handler(_call_ref, _event, _user_data):
            self._on_trigger()
            return 0

        self._handler = _HANDLER(handler)  # keep a reference so it is not garbage collected
        spec_type = _EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOTKEY_PRESSED)
        status = carbon.InstallEventHandler(carbon.GetApplicationEventTarget(), self._handler, 1,
                                            ctypes.byref(spec_type), None, None)
        if status != 0:
            on_error(f"Could not install the hotkey handler (error {status}).")
            return
        self._register(spec)

    def _register(self, spec):
        mods, key = _parse_hotkey(spec)
        ref = ctypes.c_void_p()
        status = self._carbon.RegisterEventHotKey(key, mods, _EventHotKeyID(HOTKEY_SIGNATURE, 1),
                                                  self._carbon.GetApplicationEventTarget(), 0, ctypes.byref(ref))
        if status != 0:
            self._on_error(f"Could not register hotkey {spec}; it may be in use (error {status}).")
            return False
        self._ref, self._active = ref, spec
        return True

    def change_hotkey(self, spec):
        """Switch to a new, already validated hotkey; falls back to the old one if it is taken."""
        previous = self._active
        if self._ref is not None:
            self._carbon.UnregisterEventHotKey(self._ref)
            self._ref = self._active = None
        if not self._register(spec) and previous:
            self._register(previous)

    # -- start with the OS ------------------------------------------------------
    def autostart_enabled(self):
        return os.path.exists(LAUNCH_AGENT)

    def set_autostart(self, enabled):
        """Install or remove a LaunchAgent; it takes effect at the next login."""
        if not enabled:
            try:
                os.remove(LAUNCH_AGENT)
            except FileNotFoundError:
                pass
            return
        os.makedirs(os.path.dirname(LAUNCH_AGENT), exist_ok=True)
        plist = {
            "Label": "io.github.openclipboardmanager",
            "ProgramArguments": [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, ENTRY_SCRIPT],
            "RunAtLoad": True,
        }
        with open(LAUNCH_AGENT, "wb") as f:
            plistlib.dump(plist, f)

    # -- files and commands -----------------------------------------------------
    def open_path(self, path):
        subprocess.Popen(["open", path])

    def edit_file(self, path):
        subprocess.Popen(["open", "-t", path])

    def sanitize_arg(self, value):
        """Make clipboard text safe to place inside "double quotes" in a sh command line."""
        return re.sub(r'["\\$`\r\n]', "", value)
