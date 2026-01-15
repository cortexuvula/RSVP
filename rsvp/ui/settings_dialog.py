"""Settings dialog."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QSpinBox, QLineEdit, QPushButton,
    QColorDialog, QFontComboBox, QCheckBox, QLabel,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from rsvp.core.settings import get_settings_manager


class ColorButton(QPushButton):
    """Button that shows and allows selection of a color."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self):
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"color: {'white' if self._color.lightness() < 128 else 'black'}; "
            f"min-width: 80px; min-height: 25px;"
        )
        self.setText(self._color.name())

    def _pick_color(self):
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_style()

    def get_color(self) -> str:
        return self._color.name()

    def set_color(self, color: str):
        self._color = QColor(color)
        self._update_style()


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Display settings
        display_group = QGroupBox("Display")
        display_layout = QFormLayout()

        self.font_combo = QFontComboBox()
        display_layout.addRow("Font:", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 120)
        self.font_size_spin.setSuffix(" pt")
        display_layout.addRow("Font Size:", self.font_size_spin)

        self.text_color_btn = ColorButton("#FFFFFF")
        display_layout.addRow("Text Color:", self.text_color_btn)

        self.orp_color_btn = ColorButton("#FF6B6B")
        display_layout.addRow("ORP Color:", self.orp_color_btn)

        self.bg_color_btn = ColorButton("#1E1E1E")
        display_layout.addRow("Background:", self.bg_color_btn)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Speed settings
        speed_group = QGroupBox("Speed")
        speed_layout = QFormLayout()

        self.default_wpm_spin = QSpinBox()
        self.default_wpm_spin.setRange(50, 2000)
        self.default_wpm_spin.setSuffix(" wpm")
        speed_layout.addRow("Default WPM:", self.default_wpm_spin)

        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)

        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QFormLayout()

        self.pause_paragraphs_check = QCheckBox()
        behavior_layout.addRow("Pause at paragraphs:", self.pause_paragraphs_check)

        self.auto_save_check = QCheckBox()
        behavior_layout.addRow("Auto-save position:", self.auto_save_check)

        self.always_on_top_check = QCheckBox()
        behavior_layout.addRow("Always on top:", self.always_on_top_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        layout.addWidget(button_box)

    def _load_settings(self):
        """Load current settings into the dialog."""
        settings = get_settings_manager().settings

        self.font_combo.setCurrentFont(QFont(settings.font_family))
        self.font_size_spin.setValue(settings.font_size)
        self.text_color_btn.set_color(settings.text_color)
        self.orp_color_btn.set_color(settings.orp_color)
        self.bg_color_btn.set_color(settings.background_color)
        self.default_wpm_spin.setValue(settings.wpm)
        self.pause_paragraphs_check.setChecked(settings.pause_at_paragraphs)
        self.auto_save_check.setChecked(settings.auto_save_position)
        self.always_on_top_check.setChecked(settings.always_on_top)

    def _apply(self):
        """Apply settings without closing."""
        manager = get_settings_manager()
        settings = manager.settings

        settings.font_family = self.font_combo.currentFont().family()
        settings.font_size = self.font_size_spin.value()
        settings.text_color = self.text_color_btn.get_color()
        settings.orp_color = self.orp_color_btn.get_color()
        settings.background_color = self.bg_color_btn.get_color()
        settings.wpm = self.default_wpm_spin.value()
        settings.pause_at_paragraphs = self.pause_paragraphs_check.isChecked()
        settings.auto_save_position = self.auto_save_check.isChecked()
        settings.always_on_top = self.always_on_top_check.isChecked()

        manager.save()

    def _save_and_accept(self):
        """Save settings and close."""
        self._apply()
        self.accept()
