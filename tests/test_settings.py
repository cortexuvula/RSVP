"""Tests for settings module."""
import json
import sys
import pytest
from pathlib import Path
from rsvp.core.settings import RSVPSettings, SettingsManager


class TestRSVPSettings:
    """Tests for RSVPSettings defaults."""

    def test_default_wpm(self):
        s = RSVPSettings()
        assert s.wpm == 300

    def test_default_font(self):
        s = RSVPSettings()
        assert s.font_family == "Arial"
        assert s.font_size == 48

    def test_default_colors(self):
        s = RSVPSettings()
        assert s.text_color == "#FFFFFF"
        assert s.background_color == "#1E1E1E"
        assert s.orp_color == "#FF6B6B"

    def test_default_window(self):
        s = RSVPSettings()
        assert s.window_width == 800
        assert s.window_height == 600
        assert s.window_x is None
        assert s.window_y is None
        assert s.always_on_top is False

    def test_default_recent_files(self):
        s = RSVPSettings()
        assert s.recent_files == []
        assert s.max_recent_files == 10

    def test_default_bookmarks(self):
        s = RSVPSettings()
        assert s.bookmarks == {}

    def test_default_behavior(self):
        s = RSVPSettings()
        assert s.pause_at_paragraphs is True
        assert s.auto_save_position is True


class TestSettingsManager:
    """Tests for SettingsManager load/save and helpers."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a SettingsManager with a temp config path."""
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._config_path = tmp_path / "settings.json"
        return mgr

    def test_save_and_load(self, manager):
        manager.settings.wpm = 500
        manager.settings.font_size = 36
        manager.save()

        assert manager._config_path.exists()

        # Create a fresh manager pointing to the same file
        mgr2 = SettingsManager.__new__(SettingsManager)
        mgr2._settings = RSVPSettings()
        mgr2._config_path = manager._config_path
        mgr2.load()

        assert mgr2.settings.wpm == 500
        assert mgr2.settings.font_size == 36

    def test_load_nonexistent_file(self, manager):
        """Loading from a nonexistent file keeps defaults."""
        manager.load()
        assert manager.settings.wpm == 300

    def test_load_corrupted_json(self, manager):
        """Loading corrupted JSON keeps defaults."""
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.settings.wpm == 300

    def test_load_ignores_unknown_keys(self, manager):
        """Unknown keys in JSON are silently ignored."""
        manager._config_path.write_text(json.dumps({"wpm": 400, "unknown_key": "value"}))
        manager.load()
        assert manager.settings.wpm == 400
        assert not hasattr(manager.settings, "unknown_key")

    def test_save_creates_valid_json(self, manager):
        manager.save()
        data = json.loads(manager._config_path.read_text())
        assert "wpm" in data
        assert "font_family" in data

    # --- Recent files ---

    def test_add_recent_file(self, manager):
        manager.add_recent_file("/path/to/file.txt")
        assert manager.settings.recent_files == ["/path/to/file.txt"]

    def test_add_recent_file_deduplicates(self, manager):
        manager.add_recent_file("/a.txt")
        manager.add_recent_file("/b.txt")
        manager.add_recent_file("/a.txt")  # should move to front, not duplicate
        assert manager.settings.recent_files == ["/a.txt", "/b.txt"]

    def test_add_recent_file_trims_to_max(self, manager):
        manager.settings.max_recent_files = 3
        for i in range(5):
            manager.add_recent_file(f"/file{i}.txt")
        assert len(manager.settings.recent_files) == 3
        assert manager.settings.recent_files[0] == "/file4.txt"

    def test_add_recent_file_persists(self, manager):
        manager.add_recent_file("/a.txt")
        assert manager._config_path.exists()

    # --- Bookmarks ---

    def test_add_bookmark(self, manager):
        manager.add_bookmark("/file.txt", 42)
        assert manager.settings.bookmarks == {"/file.txt": [42]}

    def test_add_bookmark_sorted(self, manager):
        manager.add_bookmark("/file.txt", 50)
        manager.add_bookmark("/file.txt", 10)
        manager.add_bookmark("/file.txt", 30)
        assert manager.settings.bookmarks["/file.txt"] == [10, 30, 50]

    def test_add_bookmark_no_duplicates(self, manager):
        manager.add_bookmark("/file.txt", 10)
        manager.add_bookmark("/file.txt", 10)
        assert manager.settings.bookmarks["/file.txt"] == [10]

    def test_remove_bookmark(self, manager):
        manager.add_bookmark("/file.txt", 10)
        manager.add_bookmark("/file.txt", 20)
        manager.remove_bookmark("/file.txt", 10)
        assert manager.settings.bookmarks["/file.txt"] == [20]

    def test_remove_bookmark_nonexistent(self, manager):
        """Removing a bookmark that doesn't exist does nothing."""
        manager.remove_bookmark("/file.txt", 10)  # no crash
        manager.add_bookmark("/file.txt", 10)
        manager.remove_bookmark("/file.txt", 99)  # not in list
        assert manager.settings.bookmarks["/file.txt"] == [10]

    def test_get_bookmarks(self, manager):
        manager.add_bookmark("/file.txt", 5)
        assert manager.get_bookmarks("/file.txt") == [5]

    def test_get_bookmarks_unknown_file(self, manager):
        assert manager.get_bookmarks("/nonexistent.txt") == []

    def test_multiple_files_bookmarks(self, manager):
        manager.add_bookmark("/a.txt", 1)
        manager.add_bookmark("/b.txt", 2)
        assert manager.get_bookmarks("/a.txt") == [1]
        assert manager.get_bookmarks("/b.txt") == [2]


class TestSettingsErrorRecovery:
    """Tests for corrupted settings recovery."""

    @pytest.fixture
    def manager(self, tmp_path):
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._settings_were_reset = False
        mgr._config_path = tmp_path / "settings.json"
        return mgr

    def test_corrupted_json_creates_backup(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        backup = manager._config_path.parent / "settings.json.bak"
        assert backup.exists()
        assert backup.read_text() == "not json{{{"

    def test_corrupted_json_sets_reset_flag(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.was_reset() is True

    def test_was_reset_clears_after_read(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.was_reset() is True
        assert manager.was_reset() is False

    def test_was_reset_false_on_clean_load(self, manager):
        manager._config_path.write_text(json.dumps({"wpm": 400}))
        manager.load()
        assert manager.was_reset() is False

    def test_corrupted_json_logs_to_stderr(self, manager, capsys):
        manager._config_path.write_text("not json{{{")
        manager.load()
        captured = capsys.readouterr()
        assert "corrupted" in captured.err.lower() or "reset" in captured.err.lower()

    def test_corrupted_json_uses_defaults(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.settings.wpm == 300


class TestSettingsPositionTracking:
    """Tests for save/get/clear position methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._settings_were_reset = False
        mgr._config_path = tmp_path / "settings.json"
        return mgr

    def test_save_and_get_position(self, manager):
        manager.save_position("/file.txt", 42)
        assert manager.get_position("/file.txt") == 42

    def test_get_position_unknown_source(self, manager):
        assert manager.get_position("/nonexistent.txt") is None

    def test_save_position_overwrites(self, manager):
        manager.save_position("/file.txt", 10)
        manager.save_position("/file.txt", 50)
        assert manager.get_position("/file.txt") == 50

    def test_clear_position(self, manager):
        manager.save_position("/file.txt", 42)
        manager.clear_position("/file.txt")
        assert manager.get_position("/file.txt") is None

    def test_clear_position_nonexistent(self, manager):
        manager.clear_position("/nonexistent.txt")  # should not crash

    def test_save_position_persists(self, manager):
        manager.save_position("/file.txt", 42)
        assert manager._config_path.exists()
        data = json.loads(manager._config_path.read_text())
        assert data["saved_positions"] == {"/file.txt": 42}

    def test_multiple_sources(self, manager):
        manager.save_position("/a.txt", 10)
        manager.save_position("/b.txt", 20)
        assert manager.get_position("/a.txt") == 10
        assert manager.get_position("/b.txt") == 20

    def test_default_saved_positions_empty(self):
        s = RSVPSettings()
        assert s.saved_positions == {}
