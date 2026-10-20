# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Open Clipboard Manager: a clipboard history manager (text + images) for Windows, Linux and macOS, written
in Python/Tk, with a window styled after Open Task Manager. Public repo:
`sabaoongfx/open-clipboard-manager`. The module is still called `winclipman` (see Conventions).
Latest release: **v0.3.1** (history: 0.1.0 Windows exe; 0.2.x Win+V everywhere, Linux, single instance, copy/trash
icons; 0.3.0 installer, .dmg, .deb, .rpm; 0.3.1 file properties). `CHANGELOG.md` has the details.

## Workflow rule: test only in GitHub Actions

The owner does not want tests, the app, built executables or screenshot scripts run on their own machine
(the app hooks the global Win+V key and opens windows). Verify every change by pushing and reading the CI run:
`ci.yml` runs the suite on Windows, Ubuntu and macOS, and `gh workflow run release.yml` builds and smoke-tests
all three packages without publishing. The commands below document what CI runs; they are not for local use.

## Commands

```bash
pip install -r requirements.txt                             # pystray, pillow (+ PyObjC on macOS, python-xlib on Linux)
python winclipman.py                                        # run the app (pythonw on Windows hides the console)
python winclipman.py --show                                 # open the window of the running copy (or start one and show)
python -m unittest discover -s tests -v                     # the whole suite (~9 s, 158 tests on Windows)
python -m unittest discover -s tests -p test_history.py     # one file (tests import `base` from tests/, so use discover)
python tools/make_assets.py                                 # regenerate assets/icon.{png,ico,icns}, icon-256.png, public/*.svg
python tools/make_version_file.py <out> <exe name>          # Windows version resource for PyInstaller
python tools/smoke_test.py <built exe> 15                   # start a built binary, check a second launch hands over
```

Windows build (what CI does; the `--add-data` separator is `;` on Windows and `:` elsewhere):

```bash
python tools/make_version_file.py build/version-portable.txt Open-Clipboard-Manager-x64.exe
pyinstaller --noconfirm --clean --onefile --windowed --name Open-Clipboard-Manager-x64 --icon assets/icon.ico \
  --version-file build/version-portable.txt \
  --add-data "actions_windows.json;." --add-data "actions_macos.json;." --add-data "actions_linux.json;." \
  --hidden-import pystray._win32 winclipman.py
```

There is no linter configured. The tests are the gate.

## Architecture

- `winclipman.py`: everything that isn't drawing. `History` (entries are dicts; images are PNG files named by
  a hash of their pixels), `Actions` (regex -> shell command templates), `App` (events, clipboard polling,
  settings, paste, tray, hotkey migration), `Event` (the message enum), `main(argv)` (command line +
  single-instance hand-over). Module-level `PLATFORM` is the OS backend.
- `ui.py`: `MainWindow` and its widgets. It never imports `winclipman`; it talks to the app object it is
  given (`app.history`, `app.use_item`, `app.save_settings`, ...). Colours mirror Open Task Manager's CSS
  variables (`LIGHT`/`DARK`). Rounded shapes are PIL-drawn images on Canvases, because Tk can't round
  corners; the card's corners are small images laid over square content. Icons are drawn by the small
  functions in `ICON_DRAWERS`. The History table is a ttk Treeview, which can't hold widgets, so the per-row copy
  and trash icons are `RowActions` frames laid over each visible row's last cell (`_layout_row_buttons`, a
  reused pool, re-placed after refresh, scroll, resize and selection changes). The scrollbar is grid-managed and
  hidden by `_on_yscroll` while every row fits. `App.copy_item` (Copy button) differs from `App.use_item`
  (Enter / double-click): it neither hides the window, pastes, nor reorders the history.
- `platform_base.py`: `APP_NAME`, `APP_VERSION`, `ENTRY_SCRIPT` and the abstract `PlatformBase` every
  backend implements. A backend missing a method fails when it is created.
  - `platform_windows.py`: ctypes/Win32 (clipboard, `RegisterHotKey`, keyboard hook, registry autostart).
  - `platform_linux.py`: `xclip` or `wl-clipboard`, `xdotool`/`wtype`/`ydotool`, python-xlib for the X11
    hotkey, an XDG autostart entry. Linux has no clipboard change counter, so `clipboard_token()` reads the
    clipboard and hashes it (and caches that read for `get_text`/`get_image`).
  - `platform_macos.py`: PyObjC `NSPasteboard`, Carbon `RegisterEventHotKey` through ctypes, osascript paste,
    a LaunchAgent.
- `appicon.py`: `make_icon()`, the app icon drawn with Pillow. It imports nothing else on purpose:
  `tools/make_assets.py` runs in CI on machines without a display, and importing `winclipman` there fails on
  Linux (pystray opens an X display at import).
- `instance.py`: a loopback port written to `<data dir>/instance.port`. `main()` asks a running copy to open
  its window and exits; `--show` / `--settings` use it too, which is the only way to open the window on
  Wayland (no global hotkeys there). Only the commands in `instance.COMMANDS` are accepted.
- `actions_<os>.json`: default actions per OS. The user's copy lives in the data folder as `actions.json`.
- Data folder (`PLATFORM.data_dir`): `%APPDATA%\winclipman`, `~/Library/Application Support/winclipman`,
  `$XDG_DATA_HOME` or `~/.local/share` + `/winclipman`. Holds `config.json`, `history.json`, `images/`,
  `actions.json`, `instance.port`.

### Hotkeys

- Default is Win+V everywhere: `win+v` (Windows), `super+v` (Linux/X11), `ctrl+cmd+v` (macOS; plain Cmd+V
  is refused because it is the system Paste shortcut).
- Windows owns Win+<key>, so those combinations use a low-level keyboard hook (`_on_key`) that swallows the
  key and injects a tap of VK 0xE8 so releasing Win doesn't open the Start menu. Keys we inject carry
  `INJECT_MARK` so the hook ignores them. Other combinations use `RegisterHotKey`.
- Never test two instances at once: their hooks chain and the older one reacts first. Kill stray processes
  between manual checks (a onefile exe leaves a child process if only the parent is killed; use
  `taskkill /F /T`).
- Old config files holding the previous default (`ctrl+alt+h`, `OLD_DEFAULT_HOTKEY`) are migrated once,
  tracked by the `hotkey_migrated` config key.

### Threads

Only the Tk thread touches widgets or the history. Other threads (tray menu, hotkey, the image worker, the
single-instance listener) call `App.post(Event.X, payload)`; `App.pump()` drains the queue every 100 ms.
Large images are hashed and encoded on a worker (`History.store_image`) and added on the Tk thread
(`History.add_item`). `poll_clipboard` must always reschedule itself (try/finally): if it ever stops,
watching stops for good. Schedule Tk timers on the root, not on a window that may be rebuilt
(see `MainWindow.show`): a callback registered on a destroyed window raises "invalid command name".

### Conventions

- Entry identity is `(type, text-or-file)` (`item_key`), never just the text.
- Settings validation lives in `App.save_settings`, which returns `(saved, message)`; a message with
  `saved=True` is a warning.
- Use `APP_NAME` for anything user-visible. The code, data folder and autostart paths still say
  `winclipman` so existing history keeps loading; don't rename the data folder without a migration.
- Clipboard text goes into shell commands only through `PLATFORM.sanitize_arg`.
- Tests must not touch real user data: subclass `tests/base.py::IsolatedDataTestCase`.
- Python files are edited with CRLF line endings on Windows in places; when scripting multi-line
  replacements use a regex with `\r?\n` rather than a literal newline.

## Testing notes

- CI (`.github/workflows/ci.yml`) runs the suite on Windows, Ubuntu (under xvfb) and macOS on every push.
  Check a run with `gh run list -R sabaoongfx/open-clipboard-manager` (pass `-R` and make sure `git` is on
  PATH, or `gh` fails with "unable to find git executable").
- The macOS backend can't be imported on Windows (PyObjC), so its tests import it against `MagicMock`
  stand-ins (see `tests/test_platforms.py`). CI runs the whole suite on a real Mac, but nothing has exercised
  the real clipboard, hotkey or paste there. The same goes for `platform_linux.py`, whose helper programs
  are mocked in `tests/test_linux_backend.py`. Only Windows has been used by hand.
- `tests/test_window_smoke.py` builds the real window and skips itself without a display.
- Windows-only hook tests (`tests/test_hotkeys.py`) feed fake key events to `_on_key`; the live Win+V check
  was done by injecting keys with `keybd_event` against a running build.
- The frozen Windows exe takes ~3 s to start (onefile unpack); an automated hotkey check must wait for the
  hotkey to be registered, not use a fixed short delay.

## Packaging (all built and tested by `release.yml`)

| Output | Built from | Notes |
| --- | --- | --- |
| `Open-Clipboard-Manager-x64.exe` | PyInstaller `--onefile` | portable; ~3 s start (unpacks on every launch) |
| `Open-Clipboard-Manager-x64-setup.exe` | PyInstaller `--onedir` + Inno Setup (`installer/open-clipboard-manager.iss`) | per-user by default; CI installs it silently, smoke-tests the installed app, uninstalls |
| `Open-Clipboard-Manager-x86_64` | PyInstaller `--onefile` on Ubuntu 22.04 | |
| `Open-Clipboard-Manager-amd64.deb` | `--onedir` into `/opt` via `packaging/linux/build-deb.sh` | CI installs it with apt, validates the desktop file, runs it, removes it |
| `Open-Clipboard-Manager-x86_64.rpm` | same folder via `packaging/linux/build-rpm.sh` (`rpmbuild` on Ubuntu) | CI installs it in a **Fedora container** |
| `Open-Clipboard-Manager-aarch64.dmg` / `-x64.dmg` | `Open Clipboard Manager.app` on `macos-latest` (arm64) / `macos-15-intel` | CI mounts the image and runs the app from it |

Linux packages use a `/usr/bin/open-clipboard-manager` symlink into `/opt/open-clipboard-manager` and a
desktop entry whose `Exec` is `open-clipboard-manager --show`. The macOS app is named with spaces
(`Open Clipboard Manager`), unlike the other binaries. `tools/make_assets.py` generates `icon.ico`,
`icon.icns` and `icon-256.png`; the release jobs run it before packaging.

Windows file properties: `tools/make_version_file.py` writes PyInstaller's version resource (product name, company,
version and original file name, all from `platform_base`) and the Inno script sets the matching `VersionInfo*`
directives. The release workflow checks the portable exe, the installed app's exe and the installer. Inno pads
the installer's version strings with spaces and leaves its original file name empty, so the check trims them.
Code-signing services (SignPath) require product name and version to be set consistently.

CI notes: `hdiutil create` fails now and then with `Resource busy` on macOS runners (the disk image step retries up
to five times; it did need a retry on the Intel runner).
When editing the workflow with scripts, normalise to LF first (the file can end up with mixed line endings).

## Releasing

1. Move the `## Unreleased` entries in `CHANGELOG.md` under a new `## X.Y.Z` heading, and bump `APP_VERSION` in
   `platform_base.py`. If asset names or install steps changed, update the README's Install section in the same
   commit (its links are `releases/latest/download/<name>`, so they only work once the new assets exist).
2. Push to `main` and wait for `ci.yml` to pass on Windows, Ubuntu and macOS.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. `.github/workflows/release.yml` runs the tests on three
   OSes, builds every package in the Packaging table, installs/mounts and smoke-tests each (`tools/smoke_test.py`),
   and the `publish` job attaches them, plus `SHA256SUMS.txt`, to a **draft** release.
4. Check the draft has all 8 assets (`gh release view vX.Y.Z --json assets`), then publish it with notes:
   `gh release edit vX.Y.Z --draft=false --latest --notes-file <file>`. The notes follow the earlier releases: a
   bold one-line summary, what changed, a downloads table, and an honest "how well each package is tested" paragraph
   (CI tested everything; only Windows used by hand; nothing signed).
5. Verify every `releases/latest/download/<name>` link answers HTTP 200.

Run the workflow without a tag (`gh workflow run release.yml`) to test the builds without publishing. Pass `-R
sabaoongfx/open-clipboard-manager` to every `gh` command and put `C:\Program Files\Git\cmd` on PATH first. When
reading `gh ... --json` output saved with PowerShell's `Out-File -Encoding utf8`, open it as `utf-8-sig` (it has a BOM).

Assets are versionless (the files in the Packaging table above, plus `SHA256SUMS.txt`) so
`releases/latest/download/<name>` always works; don't rename them without updating the README. Keep `--add-data`
entries for all three `actions_*.json` files in the PyInstaller commands: the frozen app reads them from its
unpack folder.
## Known gaps and follow-ups

- Linux and macOS have never been used on a real desktop; Wayland has no global hotkey; GNOME needs the
  AppIndicator extension for the tray icon.
- Nothing is code-signed (SmartScreen / Gatekeeper warn). Free Windows signing via **SignPath Foundation** was
  researched but not applied for: only the owner can apply (https://signpath.org/apply), with MFA on GitHub and
  SignPath. Their terms also want a verifiable project reputation, a "Code signing policy" section in the README
  (add it only after acceptance, with the line "Free code signing provided by SignPath.io, certificate by SignPath
  Foundation"), manual approval of every release, and the product name/version metadata that `make_version_file.py`
  and the Inno script now set. Signing would go in the Windows job via `signpath/github-action-submit-signing-request`
  after `actions/upload-artifact`; the PyInstaller exe probably needs signing before it goes into the installer, so
  two signing requests per release. Unknown: whether a single maintainer may hold all roles, and PyInstaller caveats.
- Not built yet: AppImage, MSI, an apt/pacman repository (Open Task Manager has them), ARM Linux.
- The table rows, scrollbar, checkboxes and thumbnails are square (the Tk table can't round them); the
  window isn't DPI-aware, so text may look soft on high-DPI screens.
- Actions are edited as JSON in a text editor.