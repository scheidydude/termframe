# Terminal Window Manager — Implementation Brief for Claude Code

## Objective

Build a lightweight Windows desktop utility in Python that makes multiple Windows Terminal windows easier to identify, organize, and switch between.

The application should **not** implement a terminal multiplexer and should **not** replace Windows Terminal in the first version.

Instead, it should:

1. Launch normal Windows Terminal windows.
2. Associate each terminal window with a logical name such as `DEV`, `PROD`, `AWS`, or `CMD`.
3. Track the corresponding Windows HWND for each launched terminal window.
4. Draw a highly visible configurable border around managed terminal windows.
5. Make the focused terminal visually obvious.
6. Provide a small manager UI for launching, listing, focusing, and closing managed terminals.
7. Preserve normal Windows Terminal behavior, security context, shell behavior, clipboard support, fonts, ANSI handling, SSH, PowerShell, etc.

The primary use case is managing several separate **Windows Terminal windows**, not tabs.

---

# Important Design Constraints

## Do not build a terminal emulator

Do not implement ConPTY, ANSI rendering, terminal escape handling, PTY emulation, scrollback, VT parsing, or a terminal rendering widget in Phase 1.

Windows Terminal already does this extremely well.

The application should act as a **window/session manager around Windows Terminal**.

---

## Do not use terminal multiplexers

Do not introduce tmux-like, SSH multiplexing, remote shell, proxy shell, PTY multiplexer, or session multiplexing components.

Managed shell processes should remain normal Windows Terminal sessions.

Typical process structure should remain approximately:

```text
TerminalManager.exe
    └── wt.exe
          └── pwsh.exe
```

or:

```text
TerminalManager.exe
    └── wt.exe
          └── cmd.exe
```

---

# Target Environment

Primary platform:

```text
Windows 11
Python 3.11+
Windows Terminal
PowerShell 7 and/or Windows PowerShell
```

Preferred GUI framework:

```text
PySide6
```

Preferred Win32 integration:

```text
ctypes
```

Use `pywin32` only if there is a strong implementation reason.

Avoid unnecessary dependencies.

The final application should be capable of being packaged into a standalone Windows executable later using PyInstaller.

---

# Proposed Application Name

Working name:

```text
TermFrame
```

Other acceptable internal names:

```text
TerminalManager
FocusTerminal
TermManager
```

Use `TermFrame` unless there is a compelling technical reason not to.

---

# High-Level Architecture

```text
┌─────────────────────────────────────────────┐
│                 TermFrame                   │
│                                             │
│  PySide6 Manager UI                         │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ Managed Terminals                   │    │
│  │                                     │    │
│  │ ● DEV     PowerShell     Running    │    │
│  │ ○ PROD    PowerShell     Running    │    │
│  │ ○ AWS     PowerShell     Running    │    │
│  │ ○ CMD     cmd.exe        Running    │    │
│  │                                     │    │
│  │ [+ New Terminal]                    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Session Manager                            │
│       │                                     │
│       ├── launches wt.exe                   │
│       ├── discovers HWND                    │
│       ├── tracks process/window state       │
│       └── activates/closes windows          │
│                                             │
│  Win32 Window Watcher                       │
│       │                                     │
│       ├── foreground window events          │
│       ├── move/resize events                │
│       └── destruction events                │
│                                             │
│  Overlay Manager                            │
│       │                                     │
│       └── thick click-through border        │
│           around Terminal HWND              │
│                                             │
└─────────────────────────────────────────────┘

                     │

       ┌─────────────┴─────────────┐
       │                           │

┌───────────────┐           ┌───────────────┐
│ Windows       │           │ Windows       │
│ Terminal      │           │ Terminal      │
│ DEV           │           │ PROD          │
│               │           │               │
│ pwsh.exe      │           │ pwsh.exe      │
└───────────────┘           └───────────────┘
```

---

# Core User Experience

The user launches TermFrame.

The manager window displays managed terminal sessions.

Example:

```text
┌──────────────────────────────────────────────────┐
│ TermFrame                                        │
├──────────────────────────────────────────────────┤
│                                                  │
│ ● DEV        PowerShell      C:\Repos\App        │
│ ○ PROD       PowerShell      C:\Repos\Infra      │
│ ○ AWS        PowerShell      C:\Repos\AWS        │
│ ○ CMD        Command Prompt  C:\                 │
│                                                  │
│ [+ New Terminal]                  [Settings]      │
│                                                  │
└──────────────────────────────────────────────────┘
```

Clicking a managed session should bring that Windows Terminal window to the foreground.

The active Terminal window should receive a strong frame such as:

```text
████████████████████████████████████████████████
██                                            ██
██              Windows Terminal              ██
██                                            ██
██  PS C:\Repos\App>                          ██
██                                            ██
████████████████████████████████████████████████
```

The border should be approximately:

```text
6 px
```

by default.

Allow configuration between approximately:

```text
2–12 px
```

---

# Phase 1 Scope

Implement the following.

## 1. Manager UI

Create a small PySide6 desktop window.

Minimum functionality:

- Display all managed terminal sessions.
- Show:
  - logical name
  - shell
  - status
  - working directory if known
- Double-click or button click should focus the terminal.
- Button to create a new terminal.
- Button or context menu to close a managed terminal.
- Refresh status automatically.
- Allow minimizing TermFrame without affecting terminals.

Do not overdesign the UI.

Functional and clean is more important than visually elaborate.

---

# 2. Session Definition

Represent a terminal session using a Python data model.

Example:

```python
@dataclass
class TerminalSession:
    id: str
    name: str
    shell: str
    cwd: str | None
    color: str
    process_id: int | None
    hwnd: int | None
    status: str
```

Possible status values:

```text
starting
running
closed
error
```

---

# 3. Launch Windows Terminal

Use `subprocess.Popen()` to launch `wt.exe`.

Example conceptual command:

```text
wt.exe -w new --title DEV -d C:\Repos\App pwsh.exe
```

or equivalent supported Windows Terminal syntax.

Support at minimum:

```text
pwsh.exe
powershell.exe
cmd.exe
```

Allow shell executable to be configurable.

The command construction should be isolated in a dedicated module.

Suggested module:

```text
termframe/launcher.py
```

---

# 4. Reliable HWND Discovery

After launching Windows Terminal, identify the correct top-level Windows Terminal HWND.

This is one of the most important parts of the implementation.

Do not rely solely on `subprocess.Popen().pid` because `wt.exe` may delegate window/session creation to an existing Windows Terminal process.

Use a combination of:

- unique terminal title
- top-level window enumeration
- process executable identification
- launch timestamp
- HWND discovery retries

Suggested flow:

```text
Generate unique internal launch title

Example:

TERMFRAME-DEV-550e8400

Launch wt.exe with that title

Enumerate top-level windows

Find Windows Terminal window with matching title

Store HWND

Optionally replace visible title afterward if feasible
```

The internal unique identifier may remain in the title if necessary.

Prefer a visible title like:

```text
DEV — TermFrame
```

while retaining enough uniqueness to reliably associate the HWND.

---

# 5. Win32 Functions

Create a dedicated Win32 abstraction module.

Suggested:

```text
termframe/win32.py
```

Likely APIs include:

```text
EnumWindows
IsWindow
IsWindowVisible
GetWindowTextW
GetWindowThreadProcessId
GetForegroundWindow
SetForegroundWindow
ShowWindow
GetWindowRect
DwmGetWindowAttribute
SetWinEventHook
UnhookWinEvent
```

Potential event constants:

```text
EVENT_SYSTEM_FOREGROUND
EVENT_OBJECT_LOCATIONCHANGE
EVENT_OBJECT_DESTROY
```

Use out-of-context WinEvent hooks where appropriate.

Do not poll foreground focus continuously if WinEventHook provides a reliable event-driven mechanism.

Periodic low-frequency reconciliation is acceptable as a fallback.

---

# 6. Window Bounds

Use DWM extended frame bounds if available.

Preferred:

```text
DwmGetWindowAttribute
DWMWA_EXTENDED_FRAME_BOUNDS
```

Fallback:

```text
GetWindowRect
```

The overlay should track the actual visible Windows Terminal frame.

---

# 7. Focus Border Overlay

Create a separate transparent PySide6 window for each highlighted frame, or a reusable overlay if simpler.

Requirements:

- frameless
- transparent background
- always above the target Terminal
- click-through
- does not take keyboard focus
- does not appear in Alt+Tab
- does not activate when clicked
- does not interfere with resizing Terminal
- follows Terminal when moved
- follows Terminal when resized
- hides when the Terminal is minimized
- destroys or hides when Terminal closes

The overlay should draw only the border region.

Conceptually:

```text
outer rect = terminal rect expanded by border thickness
inner rect = terminal rect

paint:

outer rectangle = focus color
inner rectangle = transparent
```

Alternatively position four narrow border windows if that is more reliable.

A four-window approach is acceptable:

```text
top
bottom
left
right
```

This may simplify click-through transparency and resizing behavior.

Choose whichever implementation is more robust.

---

# 8. Overlay Window Styles

Use appropriate Win32 extended styles.

Likely:

```text
WS_EX_TOOLWINDOW
WS_EX_TRANSPARENT
WS_EX_NOACTIVATE
WS_EX_LAYERED
```

The overlay must never become the foreground application.

Verify this carefully.

---

# 9. Focus Behavior

When a managed Terminal gains focus:

```text
focused border:
    visible
    bright
    configured thickness
```

When it loses focus:

Either:

```text
hide border
```

or:

```text
show a thin/dim border
```

Default behavior:

```text
focused = 6 px bright color
unfocused = no overlay
```

Later we may support persistent environment-colored borders.

---

# 10. Session Colors

Each session may have an associated color.

Default suggestions:

```text
DEV     blue
PROD    red
AWS     orange
CMD     gray
```

Do not hard-code these names as required session types.

They are examples.

Configuration should support arbitrary session names and colors.

When focused:

```text
frame color = session color
```

This provides both focus visibility and environment identification.

---

# 11. Bring Terminal to Foreground

When clicking a session in TermFrame:

1. Check that HWND still exists.
2. Restore it if minimized.
3. Bring it to foreground.
4. Update session state.

Potential APIs:

```text
ShowWindow(hwnd, SW_RESTORE)
SetForegroundWindow(hwnd)
```

Windows foreground activation restrictions may occasionally prevent direct focus changes.

If necessary, investigate appropriate supported Win32 handling.

Do not use unsafe hacks unless required.

---

# 12. Closing Sessions

When the user chooses Close Terminal:

Prefer requesting a normal window close.

Example:

```text
PostMessage(hwnd, WM_CLOSE, 0, 0)
```

Do not force-kill the process unless the user explicitly chooses a future "Force Close" feature.

Allow Terminal/PowerShell to handle its normal shutdown behavior.

---

# 13. Detect Closed Windows

If:

```python
IsWindow(hwnd) == False
```

mark the session:

```text
closed
```

Remove its overlay.

Optionally keep it in the UI temporarily as closed.

For MVP, removing it from the active list is acceptable.

---

# 14. New Terminal Dialog

Add a simple dialog.

Fields:

```text
Name
Shell
Working Directory
Color
```

Example:

```text
Name:              PROD

Shell:
    PowerShell 7
    Windows PowerShell
    Command Prompt
    Custom

Working Directory:
    C:\Repos\Infrastructure

Color:
    Red
```

Then:

```text
[Launch]
```

---

# Configuration

Use a user-editable configuration file.

Preferred format:

```text
YAML
```

Fallback:

```text
JSON
```

If YAML adds an unnecessary dependency, JSON is acceptable for MVP.

Example:

```yaml
application:
  border_thickness: 6
  show_tray_icon: true

sessions:
  - name: DEV
    shell: pwsh.exe
    cwd: C:\Repos\App
    color: "#3B82F6"

  - name: PROD
    shell: pwsh.exe
    cwd: C:\Repos\Infrastructure
    color: "#EF4444"

  - name: AWS
    shell: pwsh.exe
    cwd: C:\Repos\AWS
    color: "#F59E0B"
```

Suggested config location:

```text
%APPDATA%\TermFrame\config.json
```

or:

```text
%APPDATA%\TermFrame\config.yaml
```

---

# Suggested Project Structure

```text
termframe/
│
├── pyproject.toml
├── README.md
├── LICENSE
│
├── termframe/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py
│   ├── config.py
│   ├── models.py
│   ├── launcher.py
│   ├── session_manager.py
│   ├── win32.py
│   ├── window_watcher.py
│   ├── overlay.py
│   ├── manager_window.py
│   └── new_session_dialog.py
│
└── tests/
    ├── test_config.py
    ├── test_launcher.py
    └── test_models.py
```

Keep Win32 code separate from UI code.

---

# Suggested Classes

## TerminalSession

```python
@dataclass
class TerminalSession:
    id: str
    name: str
    shell: str
    cwd: str | None
    color: str
    hwnd: int | None = None
    status: str = "starting"
```

---

## SessionManager

Responsibilities:

```text
launch terminal
discover HWND
maintain session registry
focus terminal
close terminal
remove dead sessions
```

Example interface:

```python
class SessionManager:
    def launch_session(self, config) -> TerminalSession:
        ...

    def focus_session(self, session_id: str) -> None:
        ...

    def close_session(self, session_id: str) -> None:
        ...

    def reconcile_sessions(self) -> None:
        ...
```

---

## WindowWatcher

Responsibilities:

```text
WinEvent hooks
foreground changes
window movement
window resizing
window destruction
```

Example signals:

```python
foreground_changed(hwnd)
window_changed(hwnd)
window_destroyed(hwnd)
```

Bridge Win32 callback events safely into Qt signals.

Do not directly manipulate Qt widgets from arbitrary Win32 callback threads.

---

## OverlayManager

Responsibilities:

```text
create overlay
position overlay
show overlay
hide overlay
destroy overlay
change border color
change thickness
```

Possible interface:

```python
class OverlayManager:
    def highlight(self, hwnd: int, color: str) -> None:
        ...

    def hide(self) -> None:
        ...

    def update_bounds(self, hwnd: int) -> None:
        ...
```

---

# Event Flow

Example:

```text
User launches PROD

        │
        ▼

SessionManager.launch_session()

        │
        ▼

launcher launches:

wt.exe ... --title "PROD — TermFrame"

        │
        ▼

HWND discovery

        │
        ▼

session.hwnd assigned

        │
        ▼

WindowWatcher receives:

EVENT_SYSTEM_FOREGROUND

        │
        ▼

Is HWND managed?

        │
       YES
        │
        ▼

OverlayManager.highlight()

        │
        ▼

Get terminal frame bounds

        │
        ▼

Draw 6 px PROD border
```

---

# Manager UI Behavior

For each managed session show something like:

```text
● DEV
  PowerShell 7
  C:\Repos\App
```

Focused session indicator:

```text
●
```

Unfocused:

```text
○
```

Closed sessions should not show as active.

Double-click:

```text
bring window to foreground
```

Right-click context menu:

```text
Focus
Close
Remove
```

For MVP only Focus and Close are required.

---

# System Tray

This is desirable but not required for the first working implementation.

Eventually support:

```text
TermFrame tray icon

Right-click:

DEV
PROD
AWS
----------------
New Terminal
Show Manager
Exit
```

Clicking a session should activate it.

---

# Startup Behavior

Eventually support:

```text
Start TermFrame with Windows
```

Do not implement registry modification until the core application works.

A later implementation may use:

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

or a Startup-folder shortcut.

Do not require administrator rights.

---

# Security Requirements

Important.

The application should require no administrator privileges for normal operation.

Do not:

- inject DLLs
- hook keyboard input globally
- capture shell content
- intercept passwords
- proxy shell traffic
- run a terminal multiplexer
- alter Windows Terminal binaries
- patch Windows Terminal
- install drivers
- use kernel APIs
- require services
- modify system security policies

The utility should operate only on:

```text
window metadata
window position
window focus
window lifecycle
```

and normal process launching.

---

# Logging

Use Python `logging`.

Default:

```text
INFO
```

Debug mode:

```text
DEBUG
```

Useful entries:

```text
Launching terminal DEV
wt.exe launched
Searching for HWND
Matched HWND 0x00012345
DEV gained foreground focus
Updating DEV overlay
DEV moved
DEV closed
```

Avoid excessive high-frequency logs for every move event unless DEBUG is enabled.

---

# Development Strategy

Implement incrementally.

Do not attempt all functionality at once.

---

# Milestone 1 — Launch and Discover

Goal:

Launch a Windows Terminal window and reliably obtain its HWND.

Build a console prototype before building the full GUI.

Example:

```text
python prototype.py

Launching DEV...
Found HWND: 0x000C12FE
Title: DEV — TermFrame
```

Acceptance criteria:

- launches a new Windows Terminal window
- runs PowerShell
- reliably discovers correct HWND
- works repeatedly

Stop and solve HWND association reliability before proceeding.

---

# Milestone 2 — Focus Detection

Create foreground-window event monitoring.

Print:

```text
FOCUS: DEV
FOCUS: unmanaged window
FOCUS: PROD
```

Acceptance criteria:

- event-driven
- low CPU usage
- reliably detects switching between separate Windows Terminal windows

---

# Milestone 3 — Border Overlay

Draw a border around one known Terminal HWND.

Acceptance criteria:

- 6 px border
- click-through
- Terminal retains keyboard focus
- border follows move
- border follows resize
- border disappears when minimized
- border does not appear in Alt+Tab
- border does not steal focus

This milestone is critical.

---

# Milestone 4 — Multiple Managed Sessions

Track multiple terminal HWNDs.

Acceptance criteria:

```text
DEV
PROD
AWS
```

can all be open simultaneously.

Switching focus causes the appropriate border to move to the focused managed Terminal.

---

# Milestone 5 — PySide6 Manager UI

Build session list.

Acceptance criteria:

- list managed terminals
- indicate active session
- double-click activates terminal
- new terminal button
- close terminal action

---

# Milestone 6 — Configuration

Persist settings.

At minimum:

```text
border thickness
default shell
session presets
session colors
```

---

# Milestone 7 — Packaging

Create PyInstaller configuration.

Target:

```text
TermFrame.exe
```

Ideally:

```text
one-folder distribution
```

before attempting:

```text
one-file
```

A one-folder build is easier to debug and often creates fewer security-tool false positives.

Document packaging steps in README.

---

# Acceptance Criteria for MVP

The MVP is successful when all of the following work:

1. Launch `TermFrame`.
2. Click `New Terminal`.
3. Create a session named `DEV`.
4. A new Windows Terminal window opens running PowerShell.
5. TermFrame identifies and tracks that exact window.
6. Create another named `PROD`.
7. Both are visible as separate Windows Terminal windows.
8. Clicking DEV in TermFrame brings DEV forward.
9. Clicking PROD brings PROD forward.
10. Switching directly between terminal windows updates focus detection.
11. The focused managed Terminal receives a clearly visible 6 px colored border.
12. The overlay never steals keyboard or mouse focus.
13. Moving or resizing Terminal moves/resizes the border correctly.
14. Closing Terminal removes or marks the session closed.
15. Normal Windows Terminal behavior remains unchanged.
16. PowerShell, cmd, SSH, git, editors, and other normal console programs continue working normally because Windows Terminal remains the actual terminal emulator.

---

# Important Technical Investigation Areas

Claude Code should explicitly investigate and document any issues discovered in these areas.

## Windows Terminal HWND behavior

Windows Terminal may reuse an existing process.

Do not assume:

```text
Popen PID == terminal window PID
```

Use HWND/title discovery.

---

## Windows Terminal window targeting

Investigate `wt.exe` window selection syntax.

Prefer creating a genuinely separate window rather than a new tab.

The desired behavior is:

```text
DEV = Windows window #1
PROD = Windows window #2
AWS = Windows window #3
```

not:

```text
one window
    DEV tab
    PROD tab
    AWS tab
```

---

## Focus restrictions

Windows may restrict foreground activation.

Use supported Win32 behavior first.

Document any limitation.

---

## DPI Awareness

This application must work correctly with:

```text
100%
125%
150%
200%
```

Windows display scaling.

Make the application per-monitor DPI aware if necessary.

This is especially important for overlay alignment.

---

## Multiple Monitors

Support terminals moving between monitors.

Overlay coordinates must use Windows virtual desktop coordinates.

Do not assume:

```text
x >= 0
y >= 0
```

because secondary monitors may have negative coordinates.

---

## Maximized Windows

Border must work when Terminal is maximized.

If expanding outside the screen is impossible, render the border inside the visible window bounds instead.

---

## Fullscreen Terminal

If Windows Terminal enters fullscreen mode, hiding the overlay is acceptable for MVP.

Do not allow the overlay to interfere with fullscreen applications.

---

# Non-Goals for Phase 1

Do not implement:

```text
terminal tabs
terminal panes
ConPTY
terminal rendering
ANSI parsing
shell output capture
command history
session persistence after reboot
remote terminal hosting
SSH management
tmux-like sessions
terminal recording
command interception
AI shell assistance
```

Those can be considered separately later.

---

# Possible Phase 2

After the MVP is stable, consider adding richer terminal management.

Potential additions:

```text
session presets
hotkeys
terminal search
window tiling
snap layouts
workspace groups
restore workspace
tray menu
auto-launch preset terminals
environment banners
custom title templates
```

Example workspace:

```yaml
workspace: Infrastructure

sessions:

  - name: DEV
    shell: pwsh.exe
    cwd: C:\Repos\App
    color: blue

  - name: AWS-DEV
    shell: pwsh.exe
    cwd: C:\Repos\Infrastructure
    color: green

  - name: AWS-PROD
    shell: pwsh.exe
    cwd: C:\Repos\Infrastructure
    color: red
```

Then:

```text
Launch Workspace
```

creates all three.

---

# Possible Phase 3 — Window Layout Management

Later support layouts such as:

```text
┌──────────────────┬──────────────────┐
│                  │                  │
│       DEV        │       PROD       │
│                  │                  │
├──────────────────┴──────────────────┤
│                                     │
│                AWS                  │
│                                     │
└─────────────────────────────────────┘
```

This can use normal Win32:

```text
SetWindowPos
MoveWindow
```

No multiplexer is required.

---

# Possible Phase 4 — Native Terminal Host

Only consider this if managing Windows Terminal proves insufficient.

Potential architecture:

```text
PySide6
    │
terminal rendering component
    │
ConPTY
    │
pwsh.exe
```

This is explicitly not part of the initial implementation because terminal emulation involves substantial complexity including:

```text
ANSI / VT parsing
cursor movement
alternate screen
scrollback
Unicode
mouse reporting
PSReadLine
Ctrl+C
Ctrl+Break
resize signaling
256-color
truecolor
OSC sequences
clipboard
vim
less
SSH
interactive applications
```

Do not begin this work unless specifically requested later.

---

# Coding Standards

Use:

```text
Python type hints
dataclasses where appropriate
clear module boundaries
logging instead of print
pytest for logic that can be tested
small focused classes
```

Avoid:

```text
giant app.py
global mutable state
UI code containing raw ctypes definitions
Win32 code spread across modules
busy polling loops
unnecessary threading
```

Use Qt signals/slots to safely move events into the GUI thread.

---

# README Requirements

Create a README containing:

```text
What TermFrame is
Why it exists
Architecture
Requirements
Install instructions
Run instructions
Configuration
Known limitations
Security model
Packaging instructions
Development notes
```

Include a short explanation:

> TermFrame is not a terminal emulator or terminal multiplexer. It launches and manages standard Windows Terminal windows and adds a visual focus and organization layer around them.

---

# Initial Implementation Request

Begin by implementing Milestones 1–3 before expanding the GUI.

Specifically:

1. Create the project structure.
2. Create `pyproject.toml`.
3. Implement the Win32 abstraction.
4. Implement Windows Terminal launching.
5. Reliably discover the Terminal HWND.
6. Implement foreground focus detection.
7. Implement the non-activating border overlay.
8. Create a minimal prototype demonstrating:
   - launch DEV
   - find DEV HWND
   - detect DEV focus
   - draw a 6 px border
   - follow move/resize
   - never steal focus
9. Run lint/tests.
10. Document any Windows-specific problems encountered.

Once that prototype works reliably, proceed with the PySide6 manager UI.

Do not prematurely build the full interface before HWND discovery and overlay behavior are proven.

---

# Desired End State

The resulting workflow should feel like this:

```text
TermFrame
   │
   ├── DEV
   ├── PROD
   ├── AWS
   └── CMD
```

Each item corresponds to an ordinary, independent Windows Terminal window.

When the user switches between them, the currently active terminal becomes unmistakable because it receives a strong, environment-specific frame.

The application should make managing several terminal windows simpler while preserving the reliability, compatibility, and security characteristics of using Windows Terminal directly.
