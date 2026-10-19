"""Windows backend for Open Clipboard Manager:Win32 clipboard, hotkey, paste and autostart."""
import ctypes
import io
import os
import re
import subprocess
import sys
import threading
import time
import winreg
from ctypes import wintypes

from PIL import Image, ImageGrab

from platform_base import APP_DIR, ENTRY_SCRIPT, PlatformBase

CF_DIB = 8
CF_DIBV5 = 17
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
WM_HOTKEY = 0x0312
WM_APP = 0x8000
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "OpenClipboardManager"  # name of our entry under RUN_KEY
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]


def _open_clipboard():
    for _ in range(10):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.01)
    return False


def _put_clipboard_data(fmt, data):
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(fmt, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _parse_hotkey(spec):
    mods, key = MOD_NOREPEAT, None
    for part in spec.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "super"):
            mods |= MOD_WIN
        elif re.fullmatch(r"f([1-9]|1[0-9]|2[0-4])", part):
            key = 0x70 + int(part[1:]) - 1
        elif len(part) == 1 and part.isalnum():
            key = ord(part.upper())
        else:
            raise ValueError(f"unsupported hotkey part: {part!r}")
    if key is None or mods == MOD_NOREPEAT:
        raise ValueError("hotkey needs at least one modifier and one key")
    return mods, key


class Platform(PlatformBase):
    name = "windows"
    default_hotkey = "ctrl+alt+h"
    hotkey_examples = "e.g. ctrl+alt+h, ctrl+shift+v, alt+f2"
    default_actions_file = os.path.join(APP_DIR, "actions_windows.json")
    data_dir = os.path.join(os.environ.get("APPDATA", APP_DIR), "winclipman")
    ui_font = "Segoe UI"

    def is_dark_mode(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except OSError:
            return False

    # -- clipboard ------------------------------------------------------------
    def clipboard_token(self):
        """A value that changes whenever the clipboard content changes."""
        return user32.GetClipboardSequenceNumber()

    def get_text(self):
        """Return the clipboard's text, or None if it holds no text."""
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT) or not _open_clipboard():
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.wstring_at(ptr)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    def set_text(self, text):
        return _put_clipboard_data(CF_UNICODETEXT, text.encode("utf-16-le") + b"\x00\x00")

    def get_image(self):
        """Return a PIL image if the clipboard holds a bitmap, else None."""
        if not (user32.IsClipboardFormatAvailable(CF_DIB) or user32.IsClipboardFormatAvailable(CF_DIBV5)):
            return None
        try:
            img = ImageGrab.grabclipboard()
        except Exception:
            return None
        return img if isinstance(img, Image.Image) else None

    def set_image(self, img):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, (255, 255, 255))
            flat.paste(img, mask=img.getchannel("A"))
            img = flat
        else:
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "BMP")
        return _put_clipboard_data(CF_DIB, buf.getvalue()[14:])  # CF_DIB is a BMP without its file header

    # -- pasting into the previously active window ------------------------------
    def activate_self(self):
        """Windows lets the popup take focus from the hotkey press; nothing to do."""

    def remember_foreground(self):
        return user32.GetForegroundWindow()

    def focus(self, window):
        if window:
            user32.SetForegroundWindow(window)

    def send_paste(self):
        VK_CONTROL, VK_V, KEYUP = 0x11, 0x56, 0x2
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)

    # -- global hotkey ----------------------------------------------------------
    def validate_hotkey(self, spec):
        _parse_hotkey(spec)

    def start_hotkey(self, spec, on_trigger, on_error):
        """Listen for the hotkey on its own thread; raises ValueError for a bad spec."""
        _parse_hotkey(spec)
        self._tid = None
        self._request = None
        self._active = None
        self._on_trigger, self._on_error = on_trigger, on_error
        threading.Thread(target=self._hotkey_loop, args=(spec,), daemon=True).start()

    def _register(self, spec):
        mods, key = _parse_hotkey(spec)
        if user32.RegisterHotKey(None, 1, mods, key):
            self._active = spec
            return True
        self._on_error(f"Could not register hotkey {spec}; it may be in use.")
        return False

    def _hotkey_loop(self, spec):
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # create this thread's message queue
        self._tid = kernel32.GetCurrentThreadId()
        self._register(spec)
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self._on_trigger()
            elif msg.message == WM_APP:
                previous = self._active
                user32.UnregisterHotKey(None, 1)
                self._active = None
                if not self._register(self._request) and previous:
                    self._register(previous)

    def change_hotkey(self, spec):
        """Switch to a new, already validated hotkey; falls back to the old one if it is taken."""
        if self._tid is None:
            return
        self._request = spec
        user32.PostThreadMessageW(self._tid, WM_APP, 0, 0)

    # -- start with the OS ------------------------------------------------------
    def _autostart_command(self):
        if getattr(sys, "frozen", False):  # a packaged build is its own executable
            return f'"{sys.executable}"'
        exe = sys.executable
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pythonw):
            exe = pythonw
        return f'"{exe}" "{ENTRY_SCRIPT}"'

    def autostart_enabled(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
                return True
        except OSError:
            return False

    def set_autostart(self, enabled):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, self._autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except OSError:
                    pass

    # -- files and commands -----------------------------------------------------
    def open_path(self, path):
        os.startfile(path)

    def edit_file(self, path):
        subprocess.Popen(["notepad.exe", path])

    def sanitize_arg(self, value):
        """Make clipboard text safe to place inside "double quotes" in a cmd.exe command line."""
        return value.replace('"', "").replace("\r", "").replace("\n", "")
