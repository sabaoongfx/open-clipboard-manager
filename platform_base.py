"""The contract every OS backend (platform_windows.py, platform_macos.py) implements.

Declaring it as an abstract class means a backend that forgets a method fails when it is created,
not later when a user happens to press the matching button.
"""
import os
from abc import ABC, abstractmethod

APP_NAME = "Open Clipboard Manager"
APP_VERSION = "0.3.0"  # bump here, then tag v<version> (see CLAUDE.md > Releasing)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ENTRY_SCRIPT = os.path.join(APP_DIR, "winclipman.py")  # what "start at login" launches


class PlatformBase(ABC):
    # Class attributes every backend sets:
    #   name                 "windows" / "macos"
    #   default_hotkey       hotkey used until the user changes it
    #   hotkey_examples      help text shown next to the hotkey setting
    #   default_actions_file bundled actions JSON for this OS
    #   data_dir             where history, images and settings live
    #   ui_font              family name for the window text

    # -- appearance ---------------------------------------------------------------
    @abstractmethod
    def is_dark_mode(self): ...

    # -- clipboard ----------------------------------------------------------------
    @abstractmethod
    def clipboard_token(self):
        """A value that changes whenever the clipboard content changes."""

    @abstractmethod
    def get_text(self):
        """The clipboard's text, or None if it holds no text."""

    @abstractmethod
    def set_text(self, text): ...

    @abstractmethod
    def get_image(self):
        """A PIL image if the clipboard holds a bitmap, else None."""

    @abstractmethod
    def set_image(self, img): ...

    # -- pasting into the previously active window ----------------------------------
    @abstractmethod
    def activate_self(self):
        """Bring our own windows to the front."""

    @abstractmethod
    def remember_foreground(self):
        """An opaque handle for the window/app that is currently in front."""

    @abstractmethod
    def focus(self, window): ...

    @abstractmethod
    def send_paste(self): ...

    # -- global hotkey ------------------------------------------------------------
    @abstractmethod
    def validate_hotkey(self, spec):
        """Raise ValueError if the hotkey text is not usable."""

    @abstractmethod
    def start_hotkey(self, spec, on_trigger, on_error):
        """Listen for the hotkey; raises ValueError for a bad spec."""

    @abstractmethod
    def change_hotkey(self, spec):
        """Switch to a new, already validated hotkey, falling back to the old one if it is taken."""

    # -- start with the OS --------------------------------------------------------
    @abstractmethod
    def autostart_enabled(self): ...

    @abstractmethod
    def set_autostart(self, enabled): ...

    # -- files and commands -------------------------------------------------------
    @abstractmethod
    def open_path(self, path): ...

    @abstractmethod
    def edit_file(self, path): ...

    @abstractmethod
    def sanitize_arg(self, value):
        """Make clipboard text safe to place inside "double quotes" in this OS's shell."""
