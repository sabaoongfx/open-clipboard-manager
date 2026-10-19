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
  A backend missing a method fails when it is created. `platform_windows.py` (ctypes/Win32),
  `platform_linux.py` (xclip/wl-clipboard/xdotool + python-xlib) and `platform_macos.py` (PyObjC + Carbon)
  implement it.

- `instance.py`: a loopback port in the data folder. `main()` asks a running copy to open its window and
  exits; `--show` / `--settings` use it too (the only way to open the window on Wayland, which has no global
  hotkeys).

### Hotkeys

- Default is Win+V everywhere: `win+v` (Windows), `super+v` (Linux/X11), `ctrl+cmd+v` (macOS; plain Cmd+V
  is refused because it is Paste). Windows owns Win+<key>, so those combinations use a low-level keyboard
  hook (`_on_key`) that swallows the key and injects a tap of VK 0xE8 so releasing Win doesn't open the
  Start menu. Keys we inject carry `INJECT_MARK` so the hook ignores them.
- Never test two instances at once: their hooks chain and the older one reacts first. Kill stray processes
  between checks.
- Old config files holding the previous default (`ctrl+alt+h`) are migrated once (`hotkey_migrated`).

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

- CI (`.github/workflows/ci.yml`) runs the suite on Windows, Ubuntu (under xvfb) and macOS; the release
  workflow also builds each package and runs `tools/smoke_test.py` against it. Run a release build without
  publishing via the workflow's manual trigger.
- Schedule Tk timers on the root, not on a window that may be rebuilt (see `MainWindow.show`).

- The macOS backend can't be imported on Windows (PyObjC), so its tests import it against `MagicMock`
  stand-ins (see `tests/test_platforms.py`). CI runs the whole suite on a real Mac, but nothing has exercised
  the real clipboard, hotkey or paste there; the same goes for `platform_linux.py` (its helper programs are
  mocked in `tests/test_linux_backend.py`).
- `tests/test_window_smoke.py` builds the real window and skips itself without a display.
- The frozen exe takes ~3 s to start (onefile unpack); an automated hotkey check must wait for that.

## Releasing

1. Bump `APP_VERSION` in `platform_base.py` and add a `CHANGELOG.md` entry.
2. Push a `v*` tag. `.github/workflows/release.yml` runs the tests on three OSes, builds the Windows exe,
   Linux binary and macOS app with PyInstaller, smoke-tests each, and attaches them (plus `SHA256SUMS.txt`)
   to a **draft** release.
3. Publish the draft.

Assets are versionless (`Open-Clipboard-Manager-x64.exe`, `-x86_64`, `-macos-arm64.zip`) so
`releases/latest/download/<name>` always works; don't rename them without updating the README.

Do not pin the Windows exe's start-up behaviour to a fixed delay in tests or docs, and keep
`--add-data` entries for all three `actions_*.json` files in the PyInstaller commands: the
frozen app reads them from its unpack folder.
