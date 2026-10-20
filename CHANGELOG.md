# Changelog

## 0.3.1

- The Windows exe files and the installer now carry the product name (*Open Clipboard Manager*), company, copyright and version in their file properties (Details tab). Needed for code signing.

## 0.3.0

More ways to install, matching Open Task Manager's download list:

- **Windows installer** (`Open-Clipboard-Manager-x64-setup.exe`): per-user by default, Start menu entry, optional desktop shortcut, uninstaller. It installs the one-folder build, which starts faster than the portable exe.
- **macOS disk images** (`Open-Clipboard-Manager-aarch64.dmg` for Apple Silicon and `-x64.dmg` for Intel) replace the `.zip`. The app is now called *Open Clipboard Manager* and has an icon.
- **Intel macOS build.**
- **Debian/Ubuntu package** (`Open-Clipboard-Manager-amd64.deb`) and **Fedora/openSUSE package** (`Open-Clipboard-Manager-x86_64.rpm`) with a `/usr/bin/open-clipboard-manager` launcher, an app-menu entry and an icon.
- Every package is installed, started and removed (or mounted) in CI before a release is built.

## 0.2.1

- **Copy button** in the History toolbar, plus a copy icon on every row: puts the entry on the clipboard without pasting it or closing the window.
- **Trash icon on every row** to remove just that entry.
- The list's scrollbar now shows only when there are more rows than fit.
- The History toolbar is a little more compact (narrower search box) to make room for the Copy button; the window opens at 1000 px wide.

## 0.2.0

- **Win+V opens the clipboard history on every OS.** On Windows the hotkey is now Win+V (replacing Windows'
  own clipboard panel while the app runs, through a keyboard hook that also keeps the Start menu from
  opening). Linux uses Super+V (X11). macOS uses Ctrl+Cmd+V, because Cmd+V is the system Paste shortcut.
  An unchanged old default (Ctrl+Alt+H) is moved to the new one automatically, once.
- **Linux support**: clipboard through `xclip` or `wl-clipboard`, an X11 global hotkey, paste through
  `xdotool` / `wtype` / `ydotool`, start at login. Wayland has no global hotkeys, so bind a desktop
  shortcut to `python winclipman.py --show`.
- **Single instance**: starting the app again (or `--show` / `--settings`) opens the window of the copy
  that is already running instead of starting a second one that fights over the hotkey.
- Packaged builds for Windows, Linux and macOS are built by CI on every release.
- Fixed: a pending timer could leave an "invalid command name" error after the window was rebuilt for a
  theme change.

## 0.1.0

First release.

- Clipboard history for text and images, with search, preview and a global hotkey (Ctrl+Alt+H).
- Pick an entry to put it back on the clipboard and paste it into the previous window.
- Regex-matched actions on right-click (open URL, bug lookup, show file in Explorer/Finder).
- Window styled after Open Task Manager: sidebar, card, rounded controls, light and dark mode.
- Settings page: hotkey, history size, preview length, paste behaviour, start at login.
- Windows: single-file executable. macOS: source only, not yet tested on a Mac.
