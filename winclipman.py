"""Open Clipboard Manager: a cross-platform take on the Xfce Clipman clipboard manager.

Keeps a persistent clipboard history (text and images), offers a tray icon and a global
hotkey popup, and runs regex-matched "actions" on a clipboard entry. OS-specific work
lives in platform_windows.py and platform_macos.py.
"""
import enum
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

import pystray
from PIL import Image, ImageDraw

from platform_base import APP_NAME
from ui import MainWindow

if sys.platform == "win32":
    from platform_windows import Platform
elif sys.platform == "darwin":
    from platform_macos import Platform
else:
    raise SystemExit(f"{APP_NAME} supports Windows and macOS only.")

PLATFORM = Platform()
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = PLATFORM.data_dir
IMAGE_DIR = os.path.join(DATA_DIR, "images")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
USER_ACTIONS_FILE = os.path.join(DATA_DIR, "actions.json")
DEFAULT_ACTIONS_FILE = PLATFORM.default_actions_file

DEFAULT_CONFIG = {
    "max_items": 100,
    "preview_chars": 80,
    "hotkey": PLATFORM.default_hotkey,
    "paste_on_select": True,
    "save_history": True,
    "save_images": True,
}


class Event(enum.Enum):
    """Messages other threads (tray menu, hotkey, image worker) post to the Tk thread."""
    HOTKEY = "hotkey"      # the global hotkey was pressed
    SHOW = "show"          # open the window from the tray
    SETTINGS = "settings"
    TOGGLE = "toggle"      # pause / resume capturing
    CLEAR = "clear"
    DATA = "data"          # open the data folder
    QUIT = "quit"
    ERROR = "error"        # payload: message to show
    IMAGE = "image"        # payload: a stored image entry ready for the history


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Actions:
    """Regex-matched commands, in the spirit of Clipman's actions."""

    def __init__(self):
        path = USER_ACTIONS_FILE if os.path.exists(USER_ACTIONS_FILE) else DEFAULT_ACTIONS_FILE
        self.actions = []
        for a in load_json(path, []):
            try:
                self.actions.append((a["name"], re.compile(a["regex"], re.S), a["commands"]))
            except (KeyError, re.error):
                continue

    def match(self, text):
        """Return [(action name, command name, command template, match)]."""
        found = []
        for name, rx, commands in self.actions:
            m = rx.search(text)
            if m:
                for c in commands:
                    found.append((name, c["name"], c["exec"], m))
        return found

    @staticmethod
    def run(template, match):
        def sub(m):
            try:
                value = match.group(int(m.group(1))) or ""
            except IndexError:
                value = ""
            return PLATFORM.sanitize_arg(value)

        subprocess.Popen(re.sub(r"\\(\d)", sub, template), shell=True)


def item_key(item):
    """Identity of an entry; the type is part of it so a text can never collide with an image file name."""
    return (item["type"], item["text"] if item["type"] == "text" else item["file"])


def image_path(item):
    return os.path.join(IMAGE_DIR, item["file"])


class History:
    """Entries are dicts: {"type": "text", "text"} or {"type": "image", "file", "w", "h"}.

    Images live as PNG files in IMAGE_DIR, named by a hash of their pixels.
    """

    def __init__(self, config):
        self.config = config
        self.items = []
        if config["save_history"]:
            for entry in load_json(HISTORY_FILE, []):
                if isinstance(entry, str):  # history written before image support
                    entry = {"type": "text", "text": entry}
                if not isinstance(entry, dict):
                    continue
                if entry.get("type") == "text" and isinstance(entry.get("text"), str):
                    self.items.append(entry)
                elif entry.get("type") == "image" and os.path.exists(image_path(entry)):
                    self.items.append(entry)
            self._trim()
        self._sweep_orphan_images()

    def _sweep_orphan_images(self):
        """Delete image files no entry refers to, e.g. left behind by a crash or by running without saved history."""
        keep = {i["file"] for i in self.items if i["type"] == "image"}
        try:
            names = os.listdir(IMAGE_DIR)
        except OSError:
            return
        for name in names:
            if name not in keep:
                try:
                    os.remove(os.path.join(IMAGE_DIR, name))
                except OSError:
                    pass

    def apply_limits(self):
        """Re-apply the configured history size after it changed, and persist the result."""
        self._trim()
        self.save()

    def bump(self, item):
        """Move an entry to the top, as if it had just been copied."""
        self._insert(item)

    def _insert(self, item):
        item["time"] = int(time.time())
        key = item_key(item)
        self.items = [i for i in self.items if item_key(i) != key]
        self.items.insert(0, item)
        self._trim()
        self.save()

    def _trim(self):
        for dropped in self.items[self.config["max_items"]:]:
            self._discard_file(dropped)
        del self.items[self.config["max_items"]:]

    @staticmethod
    def _discard_file(item):
        if item["type"] == "image":
            try:
                os.remove(image_path(item))
            except OSError:
                pass

    def add_text(self, text):
        if text and text.strip():
            self._insert({"type": "text", "text": text})

    def store_image(self, img):
        """Write a picture to the image folder and return its entry (None if images are turned off).

        This does the slow part (hashing, PNG encoding) and touches no shared state, so it is safe to
        run on a worker thread; add_item() then puts the entry in the history on the main thread.
        """
        if not self.config["save_images"]:
            return None
        digest = hashlib.sha1(img.mode.encode() + repr(img.size).encode() + img.tobytes()).hexdigest()
        item = {"type": "image", "file": digest + ".png", "w": img.width, "h": img.height}
        if not os.path.exists(image_path(item)):
            os.makedirs(IMAGE_DIR, exist_ok=True)
            img.save(image_path(item), "PNG")
        return item

    def add_item(self, item):
        self._insert(item)

    def add_image(self, img):
        item = self.store_image(img)
        if item is not None:
            self.add_item(item)

    def remove(self, item):
        self.items = [i for i in self.items if item_key(i) != item_key(item)]
        self._discard_file(item)
        self.save()

    def clear(self):
        for item in self.items:
            self._discard_file(item)
        self.items.clear()
        self.save()

    def save(self):
        if self.config["save_history"]:
            save_json(HISTORY_FILE, self.items)


def make_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 10, 52, 58), 6, fill=(60, 120, 200), outline=(255, 255, 255), width=2)
    d.rounded_rectangle((22, 4, 42, 16), 4, fill=(230, 230, 230), outline=(90, 90, 90), width=2)
    for y in (26, 36, 46):
        d.line((20, y, 44, y), fill=(255, 255, 255), width=3)
    return img


class App:
    POLL_MS = 300

    def __init__(self):
        self.config = {**DEFAULT_CONFIG, **load_json(CONFIG_FILE, {})}
        self.history = History(self.config)
        self.actions = Actions()
        self.events = queue.Queue()
        self.paused = False
        self.last_seq = None
        self.prev_window = None

        self.root = tk.Tk()
        self.root.withdraw()
        app_icon = make_icon()
        self.window = MainWindow(self.root, self, PLATFORM, app_icon)

        self.tray = pystray.Icon(
            "winclipman",
            app_icon,
            APP_NAME,
            pystray.Menu(
                pystray.MenuItem("Open", lambda: self.post(Event.SHOW), default=True),
                pystray.MenuItem("Pause", lambda: self.post(Event.TOGGLE), checked=lambda _: self.paused),
                pystray.MenuItem("Clear history", lambda: self.post(Event.CLEAR)),
                pystray.MenuItem("Settings…", lambda: self.post(Event.SETTINGS)),
                pystray.MenuItem("Open data folder", lambda: self.post(Event.DATA)),
                pystray.MenuItem("Quit", lambda: self.post(Event.QUIT)),
            ),
        )

    # -- background plumbing ------------------------------------------------
    def post(self, event, payload=None):
        """Hand an event to the Tk thread; safe to call from any thread."""
        self.events.put((event, payload))

    def start_hotkey_thread(self):
        # Raises ValueError on a bad hotkey in the config.
        PLATFORM.start_hotkey(self.config["hotkey"], lambda: self.post(Event.HOTKEY),
                              lambda msg: self.post(Event.ERROR, msg))

    def pump(self):
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event is Event.HOTKEY:
                # Remember where to paste, unless our own window already has the focus.
                if not self.window.has_focus():
                    self.prev_window = PLATFORM.remember_foreground()
                PLATFORM.activate_self()
                self.window.show()
            elif event is Event.SHOW:
                self.prev_window = None
                PLATFORM.activate_self()
                self.window.show()
            elif event is Event.SETTINGS:
                PLATFORM.activate_self()
                self.window.show("settings")
            elif event is Event.TOGGLE:
                self.toggle_pause()
            elif event is Event.CLEAR:
                self.clear_history()
            elif event is Event.DATA:
                self.open_data_folder()
            elif event is Event.IMAGE:
                self.history.add_item(payload)
                self.window.refresh()
            elif event is Event.ERROR:
                messagebox.showwarning(APP_NAME, payload)
            elif event is Event.QUIT:
                self.quit()
                return
        self.root.after(100, self.pump)

    def poll_clipboard(self):
        try:
            seq = PLATFORM.clipboard_token()
            if seq != self.last_seq:
                self.last_seq = seq
                if not self.paused:
                    self.capture_clipboard()
        finally:
            # Always schedule the next poll: one failed read must not stop clipboard watching for good.
            self.root.after(self.POLL_MS, self.poll_clipboard)

    def capture_clipboard(self):
        """Record the clipboard's current content; text wins over an image."""
        text = PLATFORM.get_text()
        if text is not None:
            self.history.add_text(text)
            self.window.refresh()
            return
        img = PLATFORM.get_image()
        if img is not None:
            # Hashing and encoding a large screenshot takes a moment; keep the window responsive.
            threading.Thread(target=self._store_image, args=(img,), daemon=True).start()

    def _store_image(self, img):
        item = self.history.store_image(img)
        if item is not None:
            self.post(Event.IMAGE, item)

    # -- operations used by the window --------------------------------------------
    def toggle_pause(self):
        self.paused = not self.paused
        self.window.update_pause()

    def clear_history(self):
        self.history.clear()
        self.window.refresh()

    def remove_item(self, item):
        self.history.remove(item)
        self.window.refresh()

    def open_data_folder(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        PLATFORM.open_path(DATA_DIR)

    def image_file(self, item):
        return image_path(item)

    def use_item(self, item):
        """Put an entry back on the clipboard and paste it into the window we came from."""
        self.window.hide()
        if item["type"] == "text":
            ok = PLATFORM.set_text(item["text"])
        else:
            try:
                with Image.open(image_path(item)) as img:
                    ok = PLATFORM.set_image(img)
            except (OSError, ValueError):
                ok = False
        if not ok:
            return
        self.last_seq = PLATFORM.clipboard_token()
        self.history.bump(item)
        self.window.refresh()
        target, self.prev_window = self.prev_window, None
        if self.config["paste_on_select"] and target:
            PLATFORM.focus(target)
            self.root.after(120, PLATFORM.send_paste)

    def run_action(self, template, match):
        self.window.hide()
        Actions.run(template, match)

    def edit_actions(self):
        """Open the user's actions.json in a text editor, seeding it from the bundled defaults."""
        if not os.path.exists(USER_ACTIONS_FILE):
            os.makedirs(DATA_DIR, exist_ok=True)
            shutil.copyfile(DEFAULT_ACTIONS_FILE, USER_ACTIONS_FILE)
        PLATFORM.edit_file(USER_ACTIONS_FILE)

    def reload_actions(self):
        self.actions = Actions()

    def save_settings(self, values):
        """Validate and apply the Settings page.

        Returns (saved, message): saved is False when nothing was applied; message is an error, or a
        warning about a part that failed after the rest was saved, or None.
        """
        hotkey = values["hotkey"].strip().lower()
        try:
            PLATFORM.validate_hotkey(hotkey)
        except ValueError as e:
            return False, f"Invalid hotkey: {e}"
        try:
            max_items, preview_chars = int(values["max_items"]), int(values["preview_chars"])
            if not (1 <= max_items <= 1000 and 20 <= preview_chars <= 300):
                raise ValueError
        except ValueError:
            return False, "History size must be 1-1000 and preview length 20-300."
        old_hotkey = self.config["hotkey"]
        self.config.update(hotkey=hotkey, max_items=max_items, preview_chars=preview_chars,
                           paste_on_select=values["paste_on_select"], save_history=values["save_history"],
                           save_images=values["save_images"])
        save_json(CONFIG_FILE, self.config)
        if hotkey != old_hotkey:
            PLATFORM.change_hotkey(hotkey)
        self.history.apply_limits()
        self.reload_actions()
        try:
            PLATFORM.set_autostart(values["autostart"])
        except OSError as e:
            return True, f"Saved, but could not change the startup setting: {e}"
        return True, None

    # -- lifecycle ------------------------------------------------------------
    def quit(self):
        if self.config["save_history"]:
            self.history.save()
        else:
            self.history.clear()  # don't leave image files behind
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        try:
            self.start_hotkey_thread()
        except ValueError as e:
            messagebox.showerror(APP_NAME, f"Bad hotkey in config: {e}")
            return
        try:
            self.tray.run_detached()
        except Exception as e:  # the hotkey and window still work without a tray icon
            print(f"{APP_NAME}: tray icon unavailable: {e}", file=sys.stderr)
        self.last_seq = PLATFORM.clipboard_token()
        self.capture_clipboard()
        self.root.after(self.POLL_MS, self.poll_clipboard)
        self.root.after(100, self.pump)
        self.root.mainloop()


if __name__ == "__main__":
    if not os.path.exists(CONFIG_FILE):
        save_json(CONFIG_FILE, DEFAULT_CONFIG)
    App().run()
