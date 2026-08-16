# TermFrame

TermFrame is not a terminal emulator or terminal multiplexer. It launches and manages
standard Windows Terminal windows and adds a visual focus and organization layer around
them.

## Why it exists

Windows Terminal is an excellent terminal emulator but offers little help distinguishing
several open windows from each other (e.g. `DEV`, `PROD`, `AWS`, `CMD`) or making it obvious
which one currently has focus. TermFrame launches ordinary Windows Terminal windows, tracks
them, and draws a colored border around whichever managed window is focused — without
touching how Windows Terminal itself works.

## Architecture

```text
TermFrame.exe
    └── wt.exe
          └── pwsh.exe / powershell.exe / cmd.exe
```

TermFrame never renders terminal content, parses ANSI/VT sequences, or proxies shell I/O.
It operates entirely on window metadata:

- `termframe/win32.py` — thin ctypes wrapper around the Win32 APIs used (window
  enumeration, geometry, focus, WinEvent hooks). All raw Win32 access is isolated here.
- `termframe/launcher.py` — builds the `wt.exe` command line and launches it.
- `termframe/session_manager.py` — launches sessions, discovers their HWND, tracks
  status, and exposes focus/close operations.
- `termframe/window_watcher.py` — event-driven foreground/move/destroy notifications via
  `SetWinEventHook`, bridged into Qt signals.
- `termframe/overlay.py` — the click-through, non-activating border overlay window, plus
  `OverlayManager`, which owns the single shared overlay and tracks which HWND it's on.
- `termframe/models.py` — the `TerminalSession` data model.
- `termframe/manager_window.py` — the PySide6 session list (name, shell, status, working
  directory), with double-click/context-menu focus and close, and a "+ New Terminal" button.
- `termframe/new_session_dialog.py` — the new-session dialog (name, shell, working
  directory, color).
- `termframe/app.py` — `AppController`, which wires the manager window's user actions to
  `SessionManager`/`WindowWatcher`/`OverlayManager`/`config`; `main()` is the real entry point.
- `termframe/config.py` — loads/saves `%APPDATA%\TermFrame\config.yaml` (border thickness,
  default shell, session presets/colors).
- `termframe/settings_dialog.py` — the Settings dialog (border thickness, default shell).

## Requirements

- Windows 11
- Python 3.11+
- Windows Terminal (`wt.exe` on `PATH`)
- PySide6
- PyYAML

## Install

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

## Run

```powershell
.venv\Scripts\python -m termframe
```

This opens the TermFrame manager window. Use "+ New Terminal" to launch a session; double-click
or right-click > Focus on a row to bring that terminal forward; right-click > Close to close it.
Use "Settings" to change the border thickness or default shell. Every launched session is
remembered as a reusable preset in the New Terminal dialog. Closing the manager window exits
TermFrame (launched terminal windows are left open).

The Milestone 1-4 console prototype (launch/discover/focus/overlay/multi-session, without the
GUI) is still available for reference:

```powershell
.venv\Scripts\python prototype.py
```

## Configuration

Persisted at `%APPDATA%\TermFrame\config.yaml`, created on first save (Settings change or
terminal launch) rather than on startup. Example:

```yaml
application:
  border_thickness: 6
  default_shell: pwsh.exe
  show_tray_icon: true

sessions:
  - name: DEV
    shell: pwsh.exe
    cwd: C:\Repos\App
    color: '#3B82F6'
```

`show_tray_icon` is persisted (per the brief's schema) but not yet wired to anything — there's
no tray icon yet (Milestone-6-adjacent, tray itself is a "desirable but not required" feature).
An unreadable or corrupt config file is logged and treated as defaults rather than crashing the
app.

## Known limitations

- `show_tray_icon` in the config has no effect yet — no system tray icon exists.
- If a shell's prompt integration (e.g. certain oh-my-posh/starship themes) issues its own
  OSC window-title sequences, the terminal's visible title can change after launch. This
  does not affect tracking: the HWND is discovered once via `--title` matching and then
  used directly for all further identification, without rechecking the title.
- If Windows Terminal enters fullscreen mode, the overlay is expected to hide rather than
  interfere (not yet exercised — see Milestone 3 acceptance criteria).
- DPI/multi-monitor behavior (including negative coordinates on secondary monitors) relies
  on `win32.set_process_dpi_awareness()` being called before any window is created; overlay
  geometry is always re-asserted with direct Win32 calls against physical-pixel rects rather
  than through Qt's own geometry APIs, to avoid Qt's DPI scaling interfering with alignment.

## Security model

TermFrame requires no administrator privileges. It does not inject DLLs, hook keyboard
input, capture shell content, intercept credentials, proxy shell traffic, alter or patch
Windows Terminal, install drivers, or use kernel APIs. It operates only on window metadata,
window position, window focus, window lifecycle, and normal process launching.

## Packaging

Not implemented yet (planned: Milestone 7, via PyInstaller, one-folder distribution first).

## Development notes

```powershell
.venv\Scripts\pytest
```

Project status: Milestones 1–6 (launch + HWND discovery, focus detection, border overlay,
multiple simultaneous managed sessions, PySide6 manager UI, persisted configuration) are
implemented. Packaging (Milestone 7) is not yet built.
