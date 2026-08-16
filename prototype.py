"""Milestone 1-4 console prototype.

Demonstrates, end to end:
    - launching Windows Terminal windows (Milestone 1)
    - reliably discovering their HWNDs (Milestone 1)
    - event-driven foreground focus detection (Milestone 2)
    - a non-activating, click-through 6px border overlay that follows
      move/resize and hides on minimize (Milestone 3)
    - tracking multiple managed sessions simultaneously, with the border
      following focus between them (Milestone 4)

Run:
    python prototype.py

Press Ctrl+C to exit.
"""

from __future__ import annotations

import logging
import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from termframe import win32
from termframe.overlay import BorderOverlay
from termframe.session_manager import SessionManager
from termframe.window_watcher import WindowWatcher

log = logging.getLogger("prototype")

SESSIONS_TO_LAUNCH = [
    {"name": "DEV", "shell": "pwsh.exe", "color": "#3B82F6"},
    {"name": "PROD", "shell": "pwsh.exe", "color": "#EF4444"},
    {"name": "AWS", "shell": "pwsh.exe", "color": "#F59E0B"},
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Must happen before QApplication is constructed.
    win32.set_process_dpi_awareness()

    app = QApplication(sys.argv)

    manager = SessionManager()
    watcher = WindowWatcher()
    # A single shared overlay is enough: only one window can be OS-foreground
    # at a time, so the border just needs to move to whichever managed
    # session is currently focused, per the "unfocused = no overlay" default
    # in the brief's Focus Behavior section.
    overlay = BorderOverlay(thickness=6)

    for config in SESSIONS_TO_LAUNCH:
        log.info("Launching %s...", config["name"])
        try:
            session = manager.launch_session(**config)
        except TimeoutError as exc:
            log.error("%s", exc)
            return 1
        log.info("Found HWND: %#010x", session.hwnd)
        log.info("Title: %s", win32.get_window_text(session.hwnd))

    # The HWND the overlay is currently attached to, if any managed session
    # is focused.
    focused_hwnd: int | None = None

    def on_foreground_changed(hwnd: int) -> None:
        nonlocal focused_hwnd
        session = manager.find_by_hwnd(hwnd)
        if session is not None and session.status == "running":
            focused_hwnd = hwnd
            log.info("FOCUS: %s", session.name)
            overlay.set_color(session.color)
            overlay.align_to(hwnd)
            overlay.show()
        else:
            focused_hwnd = None
            log.info("FOCUS: unmanaged window")
            overlay.hide()

    def on_window_moved(hwnd: int) -> None:
        if hwnd != focused_hwnd or not overlay.isVisible():
            return
        if win32.is_iconic(hwnd):
            overlay.hide()
        else:
            overlay.align_to(hwnd)

    def on_window_destroyed(hwnd: int) -> None:
        nonlocal focused_hwnd
        session = manager.find_by_hwnd(hwnd)
        if session is None:
            return
        log.info("%s closed", session.name)
        session.status = "closed"
        if hwnd == focused_hwnd:
            focused_hwnd = None
            overlay.hide()

    watcher.foreground_changed.connect(on_foreground_changed)
    watcher.window_moved.connect(on_window_moved)
    watcher.window_destroyed.connect(on_window_destroyed)

    # Periodic low-frequency reconciliation as a fallback for any missed
    # WinEvent (brief section 5 explicitly allows this alongside the
    # event-driven path, rather than continuous polling).
    reconcile_timer = QTimer()
    reconcile_timer.setInterval(2000)
    reconcile_timer.timeout.connect(manager.reconcile_sessions)
    reconcile_timer.start()

    # A Python-level SIGINT handler alone won't fire while Qt blocks inside
    # its native message loop; this timer just gives the interpreter a
    # regular chance to notice and act on the signal.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    wakeup_timer = QTimer()
    wakeup_timer.setInterval(200)
    wakeup_timer.timeout.connect(lambda: None)
    wakeup_timer.start()

    names = ", ".join(config["name"] for config in SESSIONS_TO_LAUNCH)
    log.info("Watching for focus changes across %s. Switch between them. Ctrl+C to exit.", names)
    exit_code = app.exec()

    watcher.stop()
    log.info("Leaving managed terminal windows open (not closing them on exit).")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
