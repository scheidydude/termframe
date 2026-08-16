"""Main window: lists managed sessions, and lets the user launch/focus/close them."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .config import AppSettings, SessionPreset
from .models import TerminalSession
from .new_session_dialog import NewSessionDialog
from .settings_dialog import SettingsDialog

COLUMN_FOCUS = 0
COLUMN_NAME = 1
COLUMN_SHELL = 2
COLUMN_STATUS = 3
COLUMN_DIRECTORY = 4

_STATUS_LABELS = {
    "starting": "Starting",
    "running": "Running",
    "closed": "Closed",
    "error": "Error",
}

_FOCUSED_DOT = "●"
_UNFOCUSED_DOT = "○"
_UNFOCUSED_DOT_COLOR = "#9CA3AF"


class ManagerWindow(QWidget):
    new_terminal_requested = Signal(dict)
    focus_requested = Signal(str)
    close_requested = Signal(str)
    settings_changed = Signal(object)  # AppSettings
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TermFrame")
        self.resize(640, 320)
        self._settings = AppSettings()
        self._presets: list[SessionPreset] = []

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(["", "Name", "Shell", "Status", "Working Directory"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)

        header = self._table.horizontalHeader()
        for column in (COLUMN_FOCUS, COLUMN_NAME, COLUMN_SHELL, COLUMN_STATUS):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(COLUMN_DIRECTORY, QHeaderView.Stretch)

        new_button = QPushButton("+ New Terminal", self)
        new_button.clicked.connect(self._on_new_terminal_clicked)

        settings_button = QPushButton("Settings", self)
        settings_button.clicked.connect(self._on_settings_clicked)

        button_row = QHBoxLayout()
        button_row.addWidget(new_button)
        button_row.addStretch(1)
        button_row.addWidget(settings_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(button_row)

    def set_sessions(self, sessions: list[TerminalSession], focused_hwnd: int | None) -> None:
        previously_selected = self._selected_session_id()

        self._table.setRowCount(len(sessions))
        for row, session in enumerate(sessions):
            focused = session.status == "running" and session.hwnd is not None and session.hwnd == focused_hwnd

            dot = QTableWidgetItem(_FOCUSED_DOT if focused else _UNFOCUSED_DOT)
            dot.setForeground(QColor(session.color) if focused else QColor(_UNFOCUSED_DOT_COLOR))
            dot.setTextAlignment(Qt.AlignCenter)
            dot.setData(Qt.UserRole, session.id)

            self._table.setItem(row, COLUMN_FOCUS, dot)
            self._table.setItem(row, COLUMN_NAME, QTableWidgetItem(session.name))
            self._table.setItem(row, COLUMN_SHELL, QTableWidgetItem(session.shell))
            self._table.setItem(
                row, COLUMN_STATUS, QTableWidgetItem(_STATUS_LABELS.get(session.status, session.status))
            )
            self._table.setItem(row, COLUMN_DIRECTORY, QTableWidgetItem(session.cwd or ""))

        if previously_selected is not None:
            self._select_session(previously_selected)

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings

    def set_presets(self, presets: list[SessionPreset]) -> None:
        self._presets = presets

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().closeEvent(event)
        self.closed.emit()

    def _selected_session_id(self) -> str | None:
        selection_model = self._table.selectionModel()
        rows = selection_model.selectedRows() if selection_model else []
        if not rows:
            return None
        return self._session_id_at_row(rows[0].row())

    def _select_session(self, session_id: str) -> None:
        for row in range(self._table.rowCount()):
            if self._session_id_at_row(row) == session_id:
                self._table.selectRow(row)
                return

    def _session_id_at_row(self, row: int) -> str | None:
        item = self._table.item(row, COLUMN_FOCUS)
        return item.data(Qt.UserRole) if item else None

    def _on_row_double_clicked(self, row: int, _column: int) -> None:
        session_id = self._session_id_at_row(row)
        if session_id is not None:
            self.focus_requested.emit(session_id)

    def _show_context_menu(self, pos: QPoint) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        session_id = self._session_id_at_row(row)
        if session_id is None:
            return

        self._table.selectRow(row)
        menu = QMenu(self)
        menu.addAction("Focus", lambda: self.focus_requested.emit(session_id))
        menu.addAction("Close", lambda: self.close_requested.emit(session_id))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_new_terminal_clicked(self) -> None:
        dialog = NewSessionDialog(self, presets=self._presets, default_shell_override=self._settings.default_shell)
        if dialog.exec():
            self.new_terminal_requested.emit(dialog.result_config())

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec():
            settings = dialog.result_settings()
            self._settings = settings
            self.settings_changed.emit(settings)
