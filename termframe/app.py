"""Application entry point: wires the manager window to session/window/overlay logic."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import config as config_module
from . import win32
from .config import AppSettings, SessionPreset
from .manager_window import ManagerWindow
from .overlay import OverlayManager
from .session_manager import SessionManager
from .window_watcher import WindowWatcher

log = logging.getLogger(__name__)

RECONCILE_INTERVAL_MS = 2000


class AppController:
    """Owns the core objects and connects UI actions to session/overlay logic.

    Kept separate from ManagerWindow so the UI stays free of win32/session
    plumbing (see the brief's "keep Win32 code separate from UI code").
    """

    def __init__(self) -> None:
        self.config = config_module.load_config()

        self.manager = SessionManager()
        self.watcher = WindowWatcher()
        self.overlay = OverlayManager(thickness=self.config.application.border_thickness)
        self.window = ManagerWindow()
        self.window.set_settings(self.config.application)
        self.window.set_presets(self.config.sessions)

        self.window.new_terminal_requested.connect(self._on_new_terminal_requested)
        self.window.focus_requested.connect(self._on_focus_requested)
        self.window.close_requested.connect(self._on_close_requested)
        self.window.settings_changed.connect(self._on_settings_changed)

        self.watcher.foreground_changed.connect(self._on_foreground_changed)
        self.watcher.window_moved.connect(self._on_window_moved)
        self.watcher.window_destroyed.connect(self._on_window_destroyed)

        # Low-frequency reconciliation fallback for any missed WinEvent,
        # alongside the event-driven path (brief section 5).
        self._reconcile_timer = QTimer()
        self._reconcile_timer.setInterval(RECONCILE_INTERVAL_MS)
        self._reconcile_timer.timeout.connect(self._on_reconcile_tick)
        self._reconcile_timer.start()

    def show(self) -> None:
        self.window.show()
        self._refresh()

    def stop(self) -> None:
        self._reconcile_timer.stop()
        self.watcher.stop()

    def _refresh(self) -> None:
        self.window.set_sessions(self.manager.sessions, win32.get_foreground_window())

    def _on_new_terminal_requested(self, session_config: dict) -> None:
        self._upsert_preset(session_config)
        config_module.save_config(self.config)
        self.window.set_presets(self.config.sessions)

        try:
            self.manager.launch_session(**session_config)
        except TimeoutError as exc:
            QMessageBox.critical(self.window, "Launch failed", str(exc))
        self._refresh()

    def _upsert_preset(self, session_config: dict) -> None:
        preset = SessionPreset(**session_config)
        self.config.sessions = [p for p in self.config.sessions if p.name != preset.name]
        self.config.sessions.append(preset)

    def _on_focus_requested(self, session_id: str) -> None:
        self.manager.focus_session(session_id)

    def _on_close_requested(self, session_id: str) -> None:
        self.manager.close_session(session_id)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self.config.application = settings
        self.overlay.set_thickness(settings.border_thickness)
        config_module.save_config(self.config)

    def _on_foreground_changed(self, hwnd: int) -> None:
        session = self.manager.find_by_hwnd(hwnd)
        if session is not None and session.status == "running":
            self.overlay.highlight(hwnd, session.color)
        else:
            self.overlay.hide()
        self._refresh()

    def _on_window_moved(self, hwnd: int) -> None:
        self.overlay.update_bounds(hwnd)

    def _on_window_destroyed(self, hwnd: int) -> None:
        session = self.manager.find_by_hwnd(hwnd)
        if session is None:
            return
        log.info("%s closed", session.name)
        session.status = "closed"
        if self.overlay.current_hwnd == hwnd:
            self.overlay.hide()
        self._refresh()

    def _on_reconcile_tick(self) -> None:
        self.manager.reconcile_sessions()
        self._refresh()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Must happen before QApplication is constructed.
    win32.set_process_dpi_awareness()

    app = QApplication(sys.argv)
    # The overlay is a top-level window too; relying on Qt's implicit
    # "quit when last window closes" could keep the app alive if the
    # overlay happens to be visible when the manager window closes.
    app.setQuitOnLastWindowClosed(False)

    controller = AppController()
    controller.window.closed.connect(app.quit)
    controller.show()

    exit_code = app.exec()
    controller.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
