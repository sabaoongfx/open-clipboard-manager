<p align="center">
  <img src="public/open-clipboard-manager.svg" width="72" alt="Open Clipboard Manager logo" />
</p>

<h1 align="center">Open Clipboard Manager</h1>

<p align="center">
  A small, open-source clipboard history manager: text and images, a global hotkey, regex-matched
  actions, and a window styled after <strong>Open Task Manager</strong> (the Windows&nbsp;11 Task Manager
  layout). Built with Python and Tk for Windows and macOS, modelled on Xfce's Clipman.
</p>

<p align="center">
  <a href="https://github.com/sabaoongfx/open-clipboard-manager/releases">
    <img src="https://img.shields.io/github/v/release/sabaoongfx/open-clipboard-manager?include_prereleases&label=Download&style=for-the-badge&color=E93233" alt="Download latest release" />
  </a>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#features">Features</a> ·
  <a href="#development">Development</a> ·
  <a href="#releasing">Releasing</a>
</p>

---

<p align="center">
  <img src="docs/screenshot-history.png" width="80%" alt="History tab: searchable list of copied text and images with a preview pane" />
  <br />
  <img src="docs/screenshot-history-dark.png" width="80%" alt="The same window in dark mode" />
  <br />
  <img src="docs/screenshot-settings.png" width="80%" alt="Settings tab: hotkey, history size, paste behaviour, start at login" />
</p>

## What it is

Open Clipboard Manager remembers what you copy. Press the hotkey (**Ctrl+Alt+H** by default), pick
an earlier entry, and it is pasted into the window you were in. Everything stays on your computer:
no telemetry, no account, no network access.

It follows the look of [Open Task Manager](#credits): a navigation rail on the left, a card with a
title and toolbar, a flat table, rounded controls, and light/dark colours that follow your system.

## Install

### Windows

Download [`Open-Clipboard-Manager-x64.exe`](https://github.com/sabaoongfx/open-clipboard-manager/releases/latest/download/Open-Clipboard-Manager-x64.exe)
(always the newest version) and run it. It is a single portable file; the first launch takes a few
seconds while it unpacks. It isn't code-signed yet, so SmartScreen may warn you: choose
*More info → Run anyway*. A checksum file (`SHA256SUMS.txt`) is attached to every release.

The app lives in the system tray; use *Settings → Start at login* to launch it with Windows.

### macOS

There is no packaged build yet. Run it from source (see [Development](#development)). The macOS code
has been written but **has not been run on a Mac**, so expect rough edges; bug reports are welcome.
Auto-paste needs the Accessibility permission for the app that runs Python.

### From source (Windows or macOS)

```bash
git clone https://github.com/sabaoongfx/open-clipboard-manager
cd open-clipboard-manager
pip install -r requirements.txt
python winclipman.py          # on Windows, `pythonw` hides the console
```

Needs Python 3 with Tk (the python.org installers include it). Developed and tested on Python 3.14.

## Features

### History

- **Text and images**: screenshots and copied pictures are kept as thumbnails; text shows its length.
- **Search as you type**: the box is focused when the window opens. Type `image` to find pictures.
- **Pick and paste**: Enter or double-click copies the entry back and pastes it into the window you
  came from (when opened with the hotkey). Opened from the tray, it only copies.
- **Remove, clear, pause**: toolbar buttons; `Delete` removes the selected entry.
- **Preview pane**: the full text, or a larger picture, of the selected entry.
- **Images tab**: the same list, pictures only.

### Actions

Regex-matched commands, in the spirit of Clipman's actions. Right-click an entry to see the ones that
match: open a URL, look up a bug number, show a file in Explorer or Finder. Edit them from the *Actions*
tab (*Edit actions*, then *Reload*); your copy lives in the data folder as `actions.json`.

Clipboard text is stripped of quotes, backslashes, line breaks (and, on macOS, `$` and backticks)
before it is placed in a command, but an action is still a shell command: only add ones you trust.

### Settings

Popup hotkey (changes take effect immediately), history size (1-1000), preview length, paste after
choosing, remember history between sessions, record images, and start at login.

### Look

Sidebar with a collapse button, rounded card/buttons/inputs, accent colours, and light or dark mode
that follows the operating system each time the window opens.

## Roadmap

- A packaged macOS build, and testing the macOS backend on a real Mac.
- Signed Windows builds.
- Rounded table rows and scrollbar (the standard Tk table can't draw them).
- Sharper rendering on high-DPI screens.
- A window for editing actions without a text editor.

## Tech stack

| Layer            | Choice                                                    |
| ---------------- | --------------------------------------------------------- |
| Language / UI    | Python 3 + Tk (`tkinter`, `ttk`), drawn icons via Pillow  |
| Tray icon        | [pystray](https://github.com/moses-palmer/pystray)        |
| Windows backend  | Win32 clipboard, `RegisterHotKey`, registry (via `ctypes`)|
| macOS backend    | NSPasteboard via PyObjC, Carbon `RegisterEventHotKey`     |
| Packaging        | PyInstaller (single-file Windows exe)                     |
| Testing          | `unittest` (no extra dependencies)                        |

## Development

### Prerequisites

Python 3 with Tk (developed and tested on 3.14). On macOS also `pip install pyobjc-framework-Cocoa` (included in
`requirements.txt`).

### Run it

```bash
pip install -r requirements.txt
python winclipman.py
```

### Run the tests

```bash
python -m unittest discover -s tests -v
```

They use a temporary folder, so your real history and settings are never touched, and need no
clipboard. The window tests need a display and skip themselves where Tk can't start. The macOS
backend is tested against stand-in modules (PyObjC only exists on a Mac), so those tests cover
parsing and the interface, not the real pasteboard or hotkey.

### Build the Windows executable

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name Open-Clipboard-Manager-x64 ^
  --icon assets/icon.ico --add-data "actions_windows.json;." --add-data "actions_macos.json;." ^
  --hidden-import pystray._win32 winclipman.py
```

The result is `dist/Open-Clipboard-Manager-x64.exe`.

### Regenerate the icons

```bash
python tools/make_assets.py     # writes assets/icon.png, assets/icon.ico, public/*.svg
```

## Releasing

1. Bump `APP_VERSION` in `platform_base.py` and add an entry to `CHANGELOG.md`.
2. Push a `v*` tag. `.github/workflows/release.yml` runs the tests, builds the Windows exe and
   attaches it, plus `SHA256SUMS.txt`, to a **draft** GitHub release. The exe is uploaded under a
   versionless name (`Open-Clipboard-Manager-x64.exe`), so the
   `releases/latest/download/…` link in this README always gives the newest version.
3. Publish the draft.

## Project structure

```
winclipman.py         The app: history, actions, settings logic, events, tray, startup
ui.py                 The window: theme, rounded widgets, pages (History, Images, Actions, Settings)
platform_base.py      App name/version and the interface every OS backend implements
platform_windows.py   Win32 clipboard, hotkey, paste, registry autostart
platform_macos.py     NSPasteboard, Carbon hotkey, paste, LaunchAgent autostart
actions_*.json        Default actions per OS
assets/, public/      Icon files and the logo (generated by tools/make_assets.py)
docs/                 README screenshots
tests/                unittest suite
.github/workflows/    release.yml (tests + Windows build + draft release)
```

## How it talks to the OS

The Tk thread polls the clipboard's change counter every 300 ms (`GetClipboardSequenceNumber` on
Windows, `NSPasteboard.changeCount` on macOS) and only reads the contents when it changes. The global
hotkey runs on its own thread on Windows (a message loop) and through the app's event loop on
macOS. Other threads (tray menu, hotkey, the image encoder) never touch the UI: they post an `Event`
to a queue that the Tk thread drains every 100 ms.

Images are hashed and saved as PNG files in the data folder on a worker thread, then added to the
history on the Tk thread. History is stored as JSON next to them: `%APPDATA%\winclipman` on Windows,
`~/Library/Application Support/winclipman` on macOS.

## Credits

The window design follows [Open Task Manager](https://github.com/sabaoongfx/Open-Task-Manager)'s
colours and layout. The idea and the actions feature come from Xfce's
[Clipman](https://gitlab.xfce.org/panel-plugins/xfce4-clipman-plugin); this is an independent
rewrite and contains none of its code.

## License

[MIT](LICENSE)
