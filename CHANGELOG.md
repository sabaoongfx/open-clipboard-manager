# Changelog

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
