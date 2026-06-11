"""Smoke tests for the SettingsDialog theme integration."""

import pytest

from rsvp.core.settings import RSVPSettings, SettingsManager
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    get_theme,
)
from rsvp.ui.settings_dialog import SettingsDialog


@pytest.fixture
def isolated_settings(tmp_path):
    """Create an isolated SettingsManager backed by a tmp config path."""
    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    return mgr


@pytest.fixture
def make_dialog_with_settings(qapp, tmp_path):
    """Factory fixture for tests that need a dialog with a custom RSVPSettings."""

    def _make(settings: RSVPSettings | None = None):
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = settings or RSVPSettings()
        mgr._settings_were_reset = False
        mgr._save_failed = False
        mgr._config_path = tmp_path / "settings.json"
        return SettingsDialog(settings=mgr), mgr

    return _make


class TestSettingsDialogTheme:
    def test_dialog_has_theme_dropdown(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        assert hasattr(dlg, "theme_combo")
        assert dlg.theme_combo.count() == len(THEME_NAMES) + 1  # +1 for Custom

    def test_theme_dropdown_populated_with_4_themes(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        for name in THEME_NAMES:
            assert dlg.theme_combo.findText(name) >= 0
        assert dlg.theme_combo.findText(CUSTOM_THEME_SENTINEL) >= 0

    def test_selecting_theme_updates_colors(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        dlg.theme_combo.setCurrentText("Light")
        light = get_theme("Light")
        assert dlg.text_color_btn.get_color().lower() == light.text_color.lower()
        assert dlg.orp_color_btn.get_color().lower() == light.orp_color.lower()
        assert dlg.bg_color_btn.get_color().lower() == light.background_color.lower()

    def test_selecting_theme_updates_font(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        dlg.theme_combo.setCurrentText("Sepia")
        sepia = get_theme("Sepia")
        assert dlg.font_combo.currentFont().family() == sepia.font_family

    def test_manual_color_edit_shows_custom(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        dlg.theme_combo.setCurrentText("Dark")
        # Simulate a manual change to the text color
        dlg.text_color_btn.set_color("#FF00FF")
        dlg._on_color_or_font_changed()
        assert dlg.theme_combo.currentText() == CUSTOM_THEME_SENTINEL

    def test_apply_persists_theme_name(self, qapp, isolated_settings):
        dlg = SettingsDialog(settings=isolated_settings)
        dlg.theme_combo.setCurrentText("Light")
        dlg._apply()
        assert isolated_settings.settings.theme_name == "Light"

    def test_invalid_stored_theme_falls_back_to_default(self, qapp, make_dialog_with_settings):
        dlg, _ = make_dialog_with_settings(RSVPSettings(theme_name="NonexistentTheme"))
        # The dropdown should fall back to the default theme
        assert dlg.theme_combo.currentText() == DEFAULT_THEME_NAME
        assert dlg._theme_active == DEFAULT_THEME_NAME

    def test_custom_dropdown_preserves_theme_name_on_apply(self, qapp, isolated_settings):
        """When the user is on 'Custom', Apply keeps the prior theme_name."""
        dlg = SettingsDialog(settings=isolated_settings)
        # Pick Light first
        dlg.theme_combo.setCurrentText("Light")
        dlg._apply()
        assert isolated_settings.settings.theme_name == "Light"
        # Now manually edit a color — dropdown switches to Custom
        dlg.text_color_btn.set_color("#FF00FF")
        dlg._on_color_or_font_changed()
        assert dlg.theme_combo.currentText() == CUSTOM_THEME_SENTINEL
        # Re-open the dialog and apply
        dlg._apply()
        # theme_name should still be Light, not "Custom"
        assert isolated_settings.settings.theme_name == "Light"
