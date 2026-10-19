# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt          # pystray, pillow (+ PyObjC on macOS)
python winclipman.py                     # run the app (pythonw on Windows hides the console)
python -m unittest discover -s tests -v  # the whole suite (~7s)
python -m unittest tests.test_history    # one file
python tools/make_assets.py              # regenerate assets/icon.* and public/*.svg
```

There is no linter configured. The tests are the gate.

## Architecture

- `winclipman.py`: everything that isn't drawing. `History` (entries are dicts, images are PNG files named
  by a hash), `Actions` (regex -> shell command templates), `App` (events, clipboard polling, settings,
  paste, tray). Module-level `PLATFORM` is the OS backend.
- `ui.py`: `MainWindow` and its widgets. It never imports `winclipman`; it talks to the app object it is
  given (`app.history`, `app.use_item`, `app.save_settings`, ...). Colours mirror Open Task Manager's CSS
  variables (`LIGHT`/`DARK`). Rounded shapes are PIL-drawn images on Canvases, because Tk can't round
  corners; the card's corners are small images laid over square content.
- `platform_base.py`: `APP_NAME`, `APP_VERSION` and the abstract `PlatformBase` every backend implements.
  A backend missing a method fails when it is created. `platform_windows.py` (ctypes/Win32) and
  `platform_macos.py` (PyObjC + Carbon) implement it.

### Threads

Only the Tk thread touches widgets or the history. Other threads (tray menu, hotkey, the image worker)
call `App.post(Event.X, payload)`; `App.pump()` drains the queue every 100 ms. Large images are hashed
and encoded on a worker (`History.store_image`) and added on the Tk thread (`History.add_item`).
`poll_clipboard` must always reschedule itself (try/finally): if it ever stops, watching stops for good.

### Conventions

- Entry identity is `(type, text-or-file)` (`item_key`), never just the text.
- Settings validation lives in `App.save_settings`, which returns `(saved, message)`.
- User-visible name is `APP_NAME`; the data folder is still `winclipman` so existing history keeps loading.
- Clipboard text goes into shell commands only through `PLATFORM.sanitize_arg`.
- Tests must not touch real user data: subclass `tests/base.py::IsolatedDataTestCase`.

## Testing notes

- The macOS backend can't be imported on Windows (PyObjC), so its tests import it against `MagicMock`
  stand-ins (see `tests/test_platforms.py`). Nothing has run it on a real Mac.
- `tests/test_window_smoke.py` builds the real window and skips itself without a display.
- The frozen exe takes ~3 s to start (onefile unpack); an automated hotkey check must wait for that.

## Releasing

1. Bump `APP_VERSION` in `platform_base.py` and add a `CHANGELOG.md` entry.
2. Push a `v*` tag. `.github/workflows/release.yml` runs the tests, builds the Windows exe with PyInstaller
   and attaches it (plus `SHA256SUMS.txt`) to a **draft** release.
3. Publish the draft.

The exe is uploaded as `Open-Clipboard-Manager-x64.exe` (versionless) so
`releases/latest/download/Open-Clipboard-Manager-x64.exe` always works; don't rename it without updating
the README.

Do not pin the Windows exe's start-up behaviour to a fixed delay in tests or docs, and keep
`--add-data` entries for `actions_windows.json` / `actions_macos.json` in the PyInstaller command: the
frozen app reads them from its unpack folder.
