"""Session lifecycle: launch, HWND discovery, focus, close, reconcile."""

from __future__ import annotations

import logging
import time
import uuid

from . import launcher, win32
from .models import TerminalSession

log = logging.getLogger(__name__)

DEFAULT_DISCOVERY_TIMEOUT = 10.0
DISCOVERY_POLL_INTERVAL = 0.15


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, TerminalSession] = {}

    @property
    def sessions(self) -> list[TerminalSession]:
        return list(self._sessions.values())

    def get(self, session_id: str) -> TerminalSession | None:
        return self._sessions.get(session_id)

    def find_by_hwnd(self, hwnd: int) -> TerminalSession | None:
        for session in self._sessions.values():
            if session.hwnd == hwnd:
                return session
        return None

    def launch_session(
        self,
        name: str,
        shell: str = "pwsh.exe",
        cwd: str | None = None,
        color: str = "#3B82F6",
    ) -> TerminalSession:
        session = TerminalSession(id=str(uuid.uuid4()), name=name, shell=shell, cwd=cwd, color=color)
        self._sessions[session.id] = session

        log.info("Launching terminal %s", name)
        title = launcher.generate_launch_title(name)
        process = launcher.launch_windows_terminal(title=title, shell=shell, cwd=cwd)
        session.process_id = process.pid

        try:
            session.hwnd = self._discover_hwnd(title)
        except TimeoutError:
            session.status = "error"
            log.error("Timed out discovering HWND for %s", name)
            raise

        session.status = "running"
        log.info("Matched HWND %#010x for %s", session.hwnd, name)
        return session

    def _discover_hwnd(self, title: str, timeout: float = DEFAULT_DISCOVERY_TIMEOUT) -> int:
        """Poll for a visible top-level Windows Terminal window with this title.

        wt.exe frequently exits immediately after handing off to an existing
        WindowsTerminal.exe process (the "monarch/peasant" model), so the
        launched PID cannot be trusted to identify the window — the window
        must be found by class name + title instead. Once found, the HWND is
        used for all further identification; the title is never rechecked,
        so later title changes (e.g. from shell prompt integrations) don't
        break tracking.
        """
        log.debug("Searching for HWND with title %r", title)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for hwnd in win32.enumerate_top_level_windows():
                if not win32.is_window_visible(hwnd):
                    continue
                if win32.get_class_name(hwnd) != win32.WINDOWS_TERMINAL_WINDOW_CLASS:
                    continue
                if win32.get_window_text(hwnd) != title:
                    continue
                return hwnd
            time.sleep(DISCOVERY_POLL_INTERVAL)
        raise TimeoutError(f"Timed out waiting for Windows Terminal window titled {title!r}")

    def focus_session(self, session_id: str) -> None:
        session = self._sessions[session_id]
        if session.hwnd is None or not win32.is_window(session.hwnd):
            session.status = "closed"
            return
        if win32.is_iconic(session.hwnd):
            win32.show_window(session.hwnd, win32.SW_RESTORE)
        win32.set_foreground_window(session.hwnd)

    def close_session(self, session_id: str) -> None:
        session = self._sessions[session_id]
        if session.hwnd is not None and win32.is_window(session.hwnd):
            log.info("Closing %s", session.name)
            win32.post_close(session.hwnd)

    def reconcile_sessions(self) -> None:
        """Low-frequency fallback for missed EVENT_OBJECT_DESTROY events."""
        for session in self._sessions.values():
            if session.status == "closed" or session.hwnd is None:
                continue
            if not win32.is_window(session.hwnd):
                log.info("%s closed", session.name)
                session.status = "closed"
