"""Dialog for editing persisted application settings."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QVBoxLayout, QWidget

from .config import MAX_THICKNESS, MIN_THICKNESS, AppSettings
from .launcher import SUPPORTED_SHELLS


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self._original = settings

        self._thickness_spin = QSpinBox(self)
        self._thickness_spin.setRange(MIN_THICKNESS, MAX_THICKNESS)
        self._thickness_spin.setSuffix(" px")
        self._thickness_spin.setValue(settings.border_thickness)

        self._shell_combo = QComboBox(self)
        self._shell_combo.setEditable(True)
        self._shell_combo.addItems(SUPPORTED_SHELLS)
        self._shell_combo.setCurrentText(settings.default_shell)

        form = QFormLayout()
        form.addRow("Border thickness:", self._thickness_spin)
        form.addRow("Default shell:", self._shell_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def result_settings(self) -> AppSettings:
        return AppSettings(
            border_thickness=self._thickness_spin.value(),
            default_shell=self._shell_combo.currentText().strip() or SUPPORTED_SHELLS[0],
            show_tray_icon=self._original.show_tray_icon,
        )
