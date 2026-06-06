"""Settings dialog."""

import logging
from dataclasses import asdict

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from rsvp.core.constants import FONT_SIZE_MAX, FONT_SIZE_MIN, WPM_MAX, WPM_MIN
from rsvp.core.settings import get_settings_manager
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    get_theme,
)

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ColorButton(QPushButton):
    """Button that shows and allows selection of a color."""

    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._update_style()
        self.clicked.connect(self._pick_color)

    def _update_style(self) -> None:
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"color: {'white' if self._color.lightness() < 128 else 'black'}; "
            f"min-width: 80px; min-height: 25px;"
        )
        self.setText(self._color.name())

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_style()

    def get_color(self) -> str:
        return self._color.name()

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self._update_style()


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, parent=None, settings: SettingsManager | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._load_settings()
        # Snapshot for rollback if user clicks Apply then Cancel
        self._original_settings = asdict(get_settings_manager().settings)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Display settings
        display_group = QGroupBox("Display")
        display_layout = QFormLayout()

        # Theme dropdown (applies to colors + font)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_NAMES)
        self.theme_combo.addItem(CUSTOM_THEME_SENTINEL)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        display_layout.addRow("Theme:", self.theme_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self._on_color_or_font_changed)
        display_layout.addRow("Font:", self.font_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(FONT_SIZE_MIN, FONT_SIZE_MAX)
        self.font_size_spin.setSuffix(" pt")
        display_layout.addRow("Font Size:", self.font_size_spin)

        self.text_color_btn = ColorButton("#FFFFFF")
        self.text_color_btn.clicked.connect(self._on_color_or_font_changed)
        display_layout.addRow("Text Color:", self.text_color_btn)

        self.orp_color_btn = ColorButton("#FF6B6B")
        self.orp_color_btn.clicked.connect(self._on_color_or_font_changed)
        display_layout.addRow("ORP Color:", self.orp_color_btn)

        self.bg_color_btn = ColorButton("#1E1E1E")
        self.bg_color_btn.clicked.connect(self._on_color_or_font_changed)
        display_layout.addRow("Background:", self.bg_color_btn)

        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Speed settings
        speed_group = QGroupBox("Speed")
        speed_layout = QFormLayout()

        self.default_wpm_spin = QSpinBox()
        self.default_wpm_spin.setRange(WPM_MIN, WPM_MAX)
        self.default_wpm_spin.setSuffix(" wpm")
        speed_layout.addRow("Default WPM:", self.default_wpm_spin)

        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)

        # Behavior settings
        behavior_group = QGroupBox("Behavior")
        behavior_layout = QFormLayout()

        self.always_on_top_check = QCheckBox()
        behavior_layout.addRow("Always on top:", self.always_on_top_check)

        self.pause_paragraphs_check = QCheckBox()
        behavior_layout.addRow("Pause at paragraph breaks:", self.pause_paragraphs_check)

        self.auto_save_check = QCheckBox()
        behavior_layout.addRow("Remember reading position:", self.auto_save_check)

        self.tts_check = QCheckBox()
        behavior_layout.addRow("Text-to-speech:", self.tts_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._save_and_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        layout.addWidget(button_box)

    def _load_settings(self) -> None:
        """Load current settings into the dialog."""
        settings = get_settings_manager().settings

        self.font_combo.setCurrentFont(QFont(settings.font_family))
        self.font_size_spin.setValue(settings.font_size)
        self.text_color_btn.set_color(settings.text_color)
        self.orp_color_btn.set_color(settings.orp_color)
        self.bg_color_btn.set_color(settings.background_color)
        self.default_wpm_spin.setValue(settings.wpm)
        self.always_on_top_check.setChecked(settings.always_on_top)
        self.pause_paragraphs_check.setChecked(settings.pause_at_paragraphs)
        self.auto_save_check.setChecked(settings.auto_save_position)
        self.tts_check.setChecked(settings.tts_enabled)

    def _apply(self) -> None:
        """Apply settings without closing."""
        manager = get_settings_manager()
        settings = manager.settings

        settings.font_family = self.font_combo.currentFont().family()
        settings.font_size = self.font_size_spin.value()
        settings.text_color = self.text_color_btn.get_color()
        settings.orp_color = self.orp_color_btn.get_color()
        settings.background_color = self.bg_color_btn.get_color()
        settings.wpm = self.default_wpm_spin.value()
        settings.always_on_top = self.always_on_top_check.isChecked()
        settings.pause_at_paragraphs = self.pause_paragraphs_check.isChecked()
        settings.auto_save_position = self.auto_save_check.isChecked()
        settings.tts_enabled = self.tts_check.isChecked()

        # Persist the active theme name (only if the dropdown shows a real theme;
        # "Custom" means the user kept their previous theme_name and tweaked values)
        current_dropdown = self.theme_combo.currentText()
        if current_dropdown in THEMES:
            settings.theme_name = current_dropdown
        # else: keep settings.theme_name as it was

        manager.save()
        logger.info("Settings applied")

    def _save_and_accept(self) -> None:
        """Save settings and close."""
        self._apply()
        self.accept()

    def reject(self) -> None:
        """Restore original settings on cancel (undoes any Apply clicks)."""
        manager = get_settings_manager()
        for key, value in self._original_settings.items():
            if hasattr(manager.settings, key):
                setattr(manager.settings, key, value)
        manager.save()
        super().reject()
