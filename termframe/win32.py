"""Thin ctypes wrapper around the Win32 APIs TermFrame needs.

Only window metadata, position, focus, and lifecycle APIs are used here —
no hooking, no injection, no kernel APIs. See the Security Requirements
section of the implementation brief.

UI code must not reach into ctypes directly; it should call these
helpers instead, so all raw Win32 definitions stay in one place.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass

if sys.platform != "win32":
    raise RuntimeError("termframe.win32 can only be imported on Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SW_RESTORE = 9

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080  # excluded from Alt+Tab
WS_EX_TRANSPARENT = 0x00000020  # click-through
WS_EX_NOACTIVATE = 0x08000000  # never becomes the foreground/active window

SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

WM_CLOSE = 0x0010

DWMWA_EXTENDED_FRAME_BOUNDS = 9

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
EVENT_OBJECT_DESTROY = 0x8001
OBJID_WINDOW = 0

WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# The window class Windows Terminal registers for its top-level host window.
# wt.exe itself is only a launcher stub — the actual window (and, after the
# first window, the actual process) is hosted by WindowsTerminal.exe under
# this class name. See "Windows Terminal HWND behavior" in the brief.
WINDOWS_TERMINAL_WINDOW_CLASS = "CASCADIA_HOSTING_WINDOW_CLASS"
WINDOWS_TERMINAL_PROCESS_NAME = "WindowsTerminal.exe"


# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,  # hWinEventHook
    wintypes.DWORD,  # event
    wintypes.HWND,  # hwnd
    wintypes.LONG,  # idObject
    wintypes.LONG,  # idChild
    wintypes.DWORD,  # idEventThread
    wintypes.DWORD,  # dwmsEventTime
)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

user32.SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL

# GetWindowLongPtrW/SetWindowLongPtrW are the pointer-width-safe variants;
# only present on 64-bit user32, which is what Windows 11 ships.
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

user32.SetWinEventHook.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    wintypes.HMODULE,
    WINEVENTPROC,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.UINT,
]
user32.SetWinEventHook.restype = wintypes.HANDLE

user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
user32.UnhookWinEvent.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long  # HRESULT


# ---------------------------------------------------------------------------
# DPI awareness
# ---------------------------------------------------------------------------


def set_process_dpi_awareness() -> None:
    """Opt in to per-monitor DPI awareness.

    Must be called before any window (including the Qt QApplication) is
    created, or overlay alignment will drift on mixed-DPI multi-monitor
    setups. Tries the modern API first and falls back for older systems.
    """
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
    try:
        user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        return
    except (AttributeError, OSError):
        pass
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        PROCESS_PER_MONITOR_DPI_AWARE = 2
        shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------------------
# Window rectangles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def get_frame_rect(hwnd: int) -> Rect:
    """Return the visible window frame in physical (virtual-desktop) pixels.

    Prefers DWM's extended frame bounds, which exclude the invisible resize
    padding Windows 10/11 puts around top-level windows, so the overlay
    tracks what the user actually sees. Falls back to GetWindowRect.
    """
    rect = wintypes.RECT()
    hresult = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if hresult != 0:
        if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
            raise OSError(f"GetWindowRect failed for hwnd={hwnd:#x}")
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


# ---------------------------------------------------------------------------
# Window enumeration / metadata
# ---------------------------------------------------------------------------


def enumerate_top_level_windows() -> list[int]:
    hwnds: list[int] = []

    def _callback(hwnd: int, _lparam: int) -> bool:
        hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(_callback), 0)
    return hwnds


def get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, length + 1)
    return buf.value


def get_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def get_window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return pid.value


def get_process_image_name(pid: int) -> str | None:
    """Return the basename of the executable hosting the given PID, if known."""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return None
    finally:
        kernel32.CloseHandle(handle)


def is_window(hwnd: int) -> bool:
    return bool(user32.IsWindow(wintypes.HWND(hwnd)))


def is_window_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))


def is_iconic(hwnd: int) -> bool:
    return bool(user32.IsIconic(wintypes.HWND(hwnd)))


# ---------------------------------------------------------------------------
# Focus / lifecycle
# ---------------------------------------------------------------------------


def get_foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


def set_foreground_window(hwnd: int) -> bool:
    return bool(user32.SetForegroundWindow(wintypes.HWND(hwnd)))


def show_window(hwnd: int, cmd: int) -> None:
    user32.ShowWindow(wintypes.HWND(hwnd), cmd)


def post_close(hwnd: int) -> None:
    """Ask the window to close normally (WM_CLOSE), not TerminateProcess."""
    user32.PostMessageW(wintypes.HWND(hwnd), WM_CLOSE, 0, 0)


# ---------------------------------------------------------------------------
# Overlay positioning / styling
# ---------------------------------------------------------------------------


def set_window_pos(hwnd: int, x: int, y: int, cx: int, cy: int, *, topmost: bool = False) -> None:
    insert_after = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    user32.SetWindowPos(wintypes.HWND(hwnd), insert_after, x, y, cx, cy, SWP_NOACTIVATE)


def apply_non_activating_overlay_styles(hwnd: int) -> None:
    """Make hwnd click-through, non-activating, and hidden from Alt+Tab.

    Deliberately does not touch WS_EX_LAYERED: Qt's WA_TranslucentBackground
    already gets per-pixel alpha from DWM composition, and forcing the legacy
    GDI layered-window style on top of that can make the window render blank
    unless SetLayeredWindowAttributes/UpdateLayeredWindow is also called.
    """
    hwnd_t = wintypes.HWND(hwnd)
    ex_style = user32.GetWindowLongPtrW(hwnd_t, GWL_EXSTYLE)
    ex_style |= WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
    user32.SetWindowLongPtrW(hwnd_t, GWL_EXSTYLE, ex_style)


# ---------------------------------------------------------------------------
# WinEvent hooks
# ---------------------------------------------------------------------------


def set_win_event_hook(event_min: int, event_max: int, callback) -> int:
    """Register an out-of-context WinEvent hook.

    WINEVENT_SKIPOWNPROCESS excludes events from our own windows (e.g. the
    overlay itself, or the manager window), avoiding feedback loops.
    Requires the calling thread to pump Windows messages, which the Qt
    event loop already does.
    """
    hook = user32.SetWinEventHook(
        event_min,
        event_max,
        None,
        callback,
        0,
        0,
        WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
    )
    if not hook:
        raise OSError("SetWinEventHook failed")
    return hook


def unhook_win_event(hook: int) -> None:
    user32.UnhookWinEvent(hook)
