"""Tests for the transfer (export/import) module."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rsvp.core.settings import RSVPSettings, SettingsManager
from rsvp.core.transfer import (
    BACKUP_SUFFIX,
    EXPORT_FORMAT_VERSION,
    export_to_file,
    import_from_file,
)


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Construct a SettingsManager with an isolated config path."""
    from rsvp.core import settings as settings_mod

    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "get_settings_manager", lambda: mgr)
    return mgr


class TestExport:
    def test_export_creates_file(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        assert path.exists()

    def test_export_payload_has_required_keys(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        with open(path) as f:
            data = json.load(f)
        assert "format_version" in data
        assert data["format_version"] == EXPORT_FORMAT_VERSION
        assert "exported_at" in data
        assert "settings" in data
        assert "stats" in data

    def test_export_settings_keys_present(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        with open(path) as f:
            data = json.load(f)
        s = data["settings"]
        assert "wpm" in s
        assert "font_family" in s
        assert "text_color" in s

    def test_export_stats_is_empty_dict_when_no_stats_manager(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings, stats_manager=None)
        with open(path) as f:
            data = json.load(f)
        assert data["stats"] == {}


class TestImport:
    def test_round_trip_preserves_settings(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        isolated_settings.settings.wpm = 500
        isolated_settings.settings.font_family = "Georgia"
        export_to_file(path, isolated_settings)
        # Reset to defaults
        isolated_settings.settings.wpm = 300
        isolated_settings.settings.font_family = "Arial"
        # Import
        summary = import_from_file(path, isolated_settings)
        assert summary["settings_applied"] >= 2
        assert isolated_settings.settings.wpm == 500
        assert isolated_settings.settings.font_family == "Georgia"

    def test_import_returns_summary(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        summary = import_from_file(path, isolated_settings)
        assert "settings_applied" in summary
        assert "stats_applied" in summary
        assert "format_version" in summary
        assert "warnings" in summary
        assert summary["format_version"] == EXPORT_FORMAT_VERSION

    def test_import_legacy_settings_json(self, tmp_path, isolated_settings):
        """A plain settings.json (no wrapper) should still import."""
        legacy_path = tmp_path / "legacy.json"
        legacy_data = {"wpm": 750, "font_family": "Georgia", "font_size": 72}
        legacy_path.write_text(json.dumps(legacy_data))
        summary = import_from_file(legacy_path, isolated_settings)
        assert isolated_settings.settings.wpm == 750
        assert isolated_settings.settings.font_family == "Georgia"
        assert isolated_settings.settings.font_size == 72
        assert summary["settings_applied"] == 3

    def test_unknown_setting_key_skipped_with_warning(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        path.write_text(
            json.dumps(
                {
                    "format_version": 1,
                    "settings": {"wpm": 400, "unknown_future_setting": "blah"},
                    "stats": {},
                }
            )
        )
        summary = import_from_file(path, isolated_settings)
        assert isolated_settings.settings.wpm == 400
        assert any("unknown_future_setting" in w for w in summary["warnings"])


class TestImportBackup:
    def test_creates_backup_when_settings_file_exists(self, tmp_path, isolated_settings):
        # Save initial state
        isolated_settings.save()
        # Create an import file with different content
        import_path = tmp_path / "import.json"
        import_path.write_text(json.dumps({"wpm": 999}))
        # Import
        import_from_file(import_path, isolated_settings)
        backup_path = Path(str(isolated_settings._config_path) + BACKUP_SUFFIX)
        assert backup_path.exists()

    def test_no_backup_when_no_existing_file(self, tmp_path, isolated_settings):
        # Don't save; config_path doesn't exist
        if isolated_settings._config_path.exists():
            isolated_settings._config_path.unlink()
        import_path = tmp_path / "import.json"
        import_path.write_text(json.dumps({"wpm": 999}))
        import_from_file(import_path, isolated_settings)
        backup_path = Path(str(isolated_settings._config_path) + BACKUP_SUFFIX)
        assert not backup_path.exists()

    def test_backup_suffix_is_deterministic(self):
        """Backup naming must be stable across runs."""
        assert BACKUP_SUFFIX == ".imported.bak"


class TestImportErrors:
    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises((OSError, FileNotFoundError)):
            import_from_file(tmp_path / "nonexistent.json", MagicMock())

    def test_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {")
        with pytest.raises(json.JSONDecodeError):
            import_from_file(path, MagicMock())
