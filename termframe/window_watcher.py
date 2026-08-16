"""Event-driven foreground/move/destroy tracking via WinEvent hooks.

Out-of-context WinEvent hooks deliver their callback on the same thread
that registered them, during that thread's normal Windows message pump.
Since these hooks are always set from the Qt main thread (which pumps
native messages as part of QApplication.exec()), the callback below runs
on the GUI thread and can emit Qt signals directly — no cross-thread
marshaling required.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from . import win32

log = logging.getLogger(__name__)


class WindowWatcher(QObject):
    foreground_changed = Signal(int)
    window_moved = Signal(int)
    window_destroyed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hooks: list[int] = []
        # Keep a reference to the ctypes callback trampoline alive for the
        # life of the watcher — otherwise it can be garbage collected while
        # Windows still holds a pointer to it.
        self._proc = win32.WINEVENTPROC(self._on_event)
        self._install_hooks()

    def _install_hooks(self) -> None:
        self._hooks.append(
            win32.set_win_event_hook(win32.EVENT_SYSTEM_FOREGROUND, win32.EVENT_SYSTEM_FOREGROUND, self._proc)
        )
        self._hooks.append(
            win32.set_win_event_hook(
                win32.EVENT_OBJECT_LOCATIONCHANGE, win32.EVENT_OBJECT_LOCATIONCHANGE, self._proc
            )
        )
        self._hooks.append(
            win32.set_win_event_hook(win32.EVENT_OBJECT_DESTROY, win32.EVENT_OBJECT_DESTROY, self._proc)
        )

    def _on_event(
        self,
        _hook: int,
        event: int,
        hwnd: int,
        id_object: int,
        _id_child: int,
        _id_event_thread: int,
        _event_time: int,
    ) -> None:
        # OBJID_WINDOW filters LOCATIONCHANGE down to whole-window moves;
        # without it this fires for every child control, scrollbar, etc.
        if hwnd == 0 or id_object != win32.OBJID_WINDOW:
            return
        if event == win32.EVENT_SYSTEM_FOREGROUND:
            self.foreground_changed.emit(hwnd)
        elif event == win32.EVENT_OBJECT_LOCATIONCHANGE:
            self.window_moved.emit(hwnd)
        elif event == win32.EVENT_OBJECT_DESTROY:
            self.window_destroyed.emit(hwnd)

    def stop(self) -> None:
        for hook in self._hooks:
            win32.unhook_win_event(hook)
        self._hooks.clear()
