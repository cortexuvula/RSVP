"""Smoke tests for MainWindow and its helpers."""

from unittest.mock import patch

import pytest

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import SettingsManager

pytest.importorskip("pytestqt", reason="pytest-qt required for UI tests")


@pytest.fixture
def isolated_settings(tmp_path):
    """Create an isolated SettingsManager pointing at a temp config path."""
    from rsvp.core.settings import RSVPSettings

    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    return mgr


@pytest.fixture
def main_window(qtbot, isolated_settings):
    from rsvp.ui.main_window import MainWindow

    w = MainWindow(settings=isolated_settings)
    qtbot.addWidget(w)
    return w


class TestMainWindowSmoke:
    def test_instantiates(self, main_window):
        assert main_window is not None
        assert main_window.windowTitle() == "RSVP Reader"

    def test_has_components(self, main_window):
        assert main_window.word_display is not None
        assert main_window.speed_control is not None
        assert main_window.playback_controls is not None
        assert main_window.progress_widget is not None
        assert main_window.status_label is not None

    def test_has_engine(self, main_window):
        assert main_window.engine is not None
        assert isinstance(main_window.engine, RSVPEngine)

    def test_menus_built(self, main_window):
        menubar = main_window.menuBar()
        titles = [a.text() for a in menubar.actions()]
        assert "&File" in titles
        assert "&Edit" in titles
        assert "&View" in titles
        assert "&Playback" in titles
        assert "&Bookmarks" in titles
        assert "&Help" in titles

    def test_recent_menu_empty_placeholder(self, main_window):
        actions = main_window.recent_menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "No recent files"
        assert not actions[0].isEnabled()

    def test_bookmarks_submenu_empty_placeholder(self, main_window):
        actions = main_window.bookmarks_submenu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "No bookmarks"

    def test_speed_up_changes_wpm(self, main_window):
        initial = main_window.engine.wpm
        main_window._speed_up()
        assert main_window.engine.wpm > initial

    def test_speed_down_changes_wpm(self, main_window):
        main_window.speed_control.set_wpm(500)
        main_window._speed_down()
        assert main_window.engine.wpm < 500

    def test_paste_and_read_loads_clipboard_text(self, main_window):
        with patch.object(
            main_window._documents,
            "_read_clipboard",
            return_value="Hello world from clipboard.",
        ):
            main_window._paste_and_read()
        assert main_window.engine.word_count == 4
        assert main_window.windowTitle() == "RSVP Reader - Clipboard"

    def test_load_file_via_document_loader(self, main_window, tmp_path):
        path = tmp_path / "sample.txt"
        path.write_text("one two three four five")
        main_window._load_file(str(path))
        assert main_window.engine.word_count == 5
        assert main_window._current_file == str(path)

    def test_load_file_updates_recent_menu(self, main_window, tmp_path):
        path = tmp_path / "sample.txt"
        path.write_text("one two three")
        main_window._load_file(str(path))
        labels = [a.text() for a in main_window.recent_menu.actions() if a.isEnabled()]
        assert str(path) in labels

    def test_finished_clears_saved_position(self, main_window, tmp_path, isolated_settings):
        path = tmp_path / "doc.txt"
        path.write_text("one two three")
        main_window._load_file(str(path))
        isolated_settings.save_position(str(path), 2)
        main_window._on_finished()
        assert isolated_settings.get_position(str(path)) is None


class TestBookmarkController:
    def test_add_without_file_shows_info(self, main_window):
        with patch("rsvp.ui.bookmark_controller.QMessageBox.information") as mock_info:
            main_window._add_bookmark()
        mock_info.assert_called_once()

    def test_add_and_appears_in_menu(self, main_window, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("one two three four five")
        main_window._load_file(str(path))
        main_window.engine.seek(2)
        main_window._add_bookmark()
        labels = [a.text() for a in main_window.bookmarks_submenu.actions()]
        assert any("Word 2" in label for label in labels)

    def test_remove_existing_bookmark(self, main_window, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("one two three four five")
        main_window._load_file(str(path))
        main_window.engine.seek(2)
        main_window._add_bookmark()
        main_window._remove_bookmark()
        labels = [a.text() for a in main_window.bookmarks_submenu.actions()]
        assert any("No bookmarks" in label for label in labels)
