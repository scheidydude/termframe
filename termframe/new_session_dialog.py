"""Dialog for configuring and launching a new managed terminal session."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import SessionPreset
from .launcher import SUPPORTED_SHELLS, default_shell

_COLOR_PRESETS = [
    ("Blue", "#3B82F6"),
    ("Red", "#EF4444"),
    ("Orange", "#F59E0B"),
    ("Green", "#10B981"),
    ("Purple", "#8B5CF6"),
    ("Gray", "#6B7280"),
]

_CUSTOM_PRESET_LABEL = "(Custom)"


class NewSessionDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        presets: list[SessionPreset] | None = None,
        default_shell_override: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Terminal")
        self.setModal(True)
        self._presets = {preset.name: preset for preset in (presets or [])}
        self._hex_to_color_label = {color_hex: label for label, color_hex in _COLOR_PRESETS}

        self._preset_combo = QComboBox(self)
        self._preset_combo.addItem(_CUSTOM_PRESET_LABEL)
        self._preset_combo.addItems(sorted(self._presets))
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)

        self._name_edit = QLineEdit(self)

        self._shell_combo = QComboBox(self)
        self._shell_combo.setEditable(True)
        self._shell_combo.addItems(SUPPORTED_SHELLS)
        self._shell_combo.setCurrentText(default_shell_override or default_shell())

        self._cwd_edit = QLineEdit(self)
        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._browse_for_directory)
        cwd_row = QHBoxLayout()
        cwd_row.setContentsMargins(0, 0, 0, 0)
        cwd_row.addWidget(self._cwd_edit)
        cwd_row.addWidget(browse_button)

        self._color_combo = QComboBox(self)
        for label, _hex in _COLOR_PRESETS:
            self._color_combo.addItem(label)

        form = QFormLayout()
        if self._presets:
            form.addRow("Preset:", self._preset_combo)
        form.addRow("Name:", self._name_edit)
        form.addRow("Shell:", self._shell_combo)
        form.addRow("Working Directory:", cwd_row)
        form.addRow("Color:", self._color_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, self)
        launch_button = buttons.addButton("Launch", QDialogButtonBox.AcceptRole)
        launch_button.setDefault(True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_preset_selected(self, name: str) -> None:
        preset = self._presets.get(name)
        if preset is None:
            return
        self._name_edit.setText(preset.name)
        self._shell_combo.setCurrentText(preset.shell)
        self._cwd_edit.setText(preset.cwd or "")
        color_label = self._hex_to_color_label.get(preset.color)
        if color_label is not None:
            self._color_combo.setCurrentText(color_label)

    def _browse_for_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose Working Directory", self._cwd_edit.text())
        if directory:
            self._cwd_edit.setText(directory)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Name required", "Enter a name for the terminal session.")
            return
        self.accept()

    def result_config(self) -> dict:
        return {
            "name": self._name_edit.text().strip(),
            "shell": self._shell_combo.currentText().strip(),
            "cwd": self._cwd_edit.text().strip() or None,
            "color": dict(_COLOR_PRESETS)[self._color_combo.currentText()],
        }
