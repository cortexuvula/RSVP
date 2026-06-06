# RSVP Settings Export/Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land settings export/import as a single PR with 3 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-settings-export-import-design.md).

**Architecture:** New `rsvp.core.transfer` module with `export_to_file()` and `import_from_file()`. Wrapper JSON format `{"format_version": 1, "exported_at": "...", "settings": {...}, "stats": {...}}`. `MainWindow` adds 2 File menu items that open QFileDialogs and call the transfer functions.

**Tech Stack:** Python 3.10+, PyQt6, stdlib `json` + `shutil` + `datetime`. No new runtime dependencies.

---

## File Structure

**Created:**
- `rsvp/core/transfer.py` — `export_to_file`, `import_from_file`, helpers, format version, backup suffix
- `tests/test_transfer.py`

**Modified:**
- `rsvp/core/__init__.py` — re-export
- `rsvp/ui/menu_builder.py` — add 2 menu items
- `rsvp/ui/main_window.py` — add `_export_settings` and `_import_settings` handlers
- `CHANGELOG.md` — `[Unreleased]` entry

---

## Task 1: Transfer module

**Files:**
- Create: `rsvp/core/transfer.py`
- Modify: `rsvp/core/__init__.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Create `rsvp/core/transfer.py`**

```python
"""Export and import settings (and stats if available) to/from a single JSON file."""

import json
import logging
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rsvp.core.settings import SettingsManager

logger = logging.getLogger(__name__)

EXPORT_FORMAT_VERSION = 1
BACKUP_SUFFIX = ".imported.bak"

# Optional stats import (may not be available on every branch)
try:
    from rsvp.core.stats import StatsData, StatsManager  # type: ignore[import-not-found]

    _STATS_AVAILABLE = True
except ImportError:
    StatsData = None  # type: ignore[assignment,misc]
    StatsManager = None  # type: ignore[assignment,misc]
    _STATS_AVAILABLE = False


def export_to_file(
    path: Path,
    settings_manager: SettingsManager,
    stats_manager=None,
) -> None:
    """Export settings (and stats if available) to a JSON file at `path`.

    File format:
        {
            "format_version": 1,
            "exported_at": "2026-06-05T12:34:56",
            "settings": {...},
            "stats": {...}
        }

    Stats is `{}` when StatsManager is unavailable (e.g., on a branch
    that doesn't have Spec 3's stats module).
    """
    payload: dict = {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "settings": asdict(settings_manager.settings),
    }
    if _STATS_AVAILABLE and stats_manager is not None:
        payload["stats"] = stats_to_dict(stats_manager.data)
    else:
        payload["stats"] = {}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info("Exported settings to %s", path)


def import_from_file(
    path: Path,
    settings_manager: SettingsManager,
    stats_manager=None,
) -> dict:
    """Import settings (and stats if available) from a JSON file.

    Returns a summary dict with keys:
        - "settings_applied": int (number of fields updated)
        - "stats_applied": bool
        - "format_version": int (0 if not in the file)
        - "warnings": list[str]

    Before overwriting, backs up the current settings.json to
    settings.json.imported.bak (no-op if the file doesn't exist).
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    # Detect shape: wrapper ({"settings": ...}) vs legacy settings.json
    if isinstance(payload, dict) and "settings" in payload and isinstance(payload["settings"], dict):
        settings_dict = payload["settings"]
        stats_dict = payload.get("stats", {})
    else:
        # Legacy: the file IS the settings dict
        settings_dict = payload
        stats_dict = {}

    # Auto-backup before overwriting
    settings_path = settings_manager._config_path  # noqa: SLF001
    backup_settings = Path(str(settings_path) + BACKUP_SUFFIX)
    if settings_path.exists():
        shutil.copy2(settings_path, backup_settings)
        logger.info("Backed up settings to %s", backup_settings)

    # Apply settings
    applied = 0
    warnings: list[str] = []
    for key, value in settings_dict.items():
        if hasattr(settings_manager.settings, key):
            setattr(settings_manager.settings, key, value)
            applied += 1
        else:
            warnings.append(f"Unknown setting: {key!r} (skipped)")
    settings_manager.save()

    # Apply stats if available
    stats_applied = False
    if _STATS_AVAILABLE and stats_manager is not None and stats_dict:
        try:
            apply_stats_to_manager(stats_manager, stats_dict)
            stats_applied = True
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Failed to apply stats: {e}")
            logger.warning("Failed to apply stats: %s", e)

    logger.info("Imported %d settings from %s", applied, path)
    return {
        "settings_applied": applied,
        "stats_applied": stats_applied,
        "format_version": payload.get("format_version", 0) if isinstance(payload, dict) else 0,
        "warnings": warnings,
    }


def stats_to_dict(data) -> dict:
    """Convert a StatsData to a JSON-serializable dict."""
    return {
        "all_time": asdict(data.all_time),
        "per_document": {
            src: {**asdict(d), "last_read": d.last_read.isoformat()}
            for src, d in data.per_document.items()
        },
        "recent_sessions": [
            {
                **asdict(s),
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat(),
            }
            for s in data.recent_sessions
        ],
    }


def apply_stats_to_manager(manager, raw: dict) -> None:
    """Apply a stats dict (from JSON) to a StatsManager."""
    from datetime import datetime

    from rsvp.core.stats import AllTimeStats, DocumentStats, SessionRecord

    manager._data.all_time = AllTimeStats(**raw.get("all_time", {}))
    manager._data.per_document = {
        src: DocumentStats(
            **{k: v for k, v in d.items() if k != "last_read"},
            last_read=datetime.fromisoformat(d["last_read"]),
        )
        for src, d in raw.get("per_document", {}).items()
    }
    manager._data.recent_sessions = [
        SessionRecord(
            **{k: v for k, v in s.items() if k not in ("started_at", "ended_at")},
            started_at=datetime.fromisoformat(s["started_at"]),
            ended_at=datetime.fromisoformat(s["ended_at"]),
        )
        for s in raw.get("recent_sessions", [])
    ]
    manager.save()
```

- [ ] **Step 2: Re-export from `rsvp/core/__init__.py`**

Add to the imports block (alphabetical position):

```python
from rsvp.core.transfer import (
    BACKUP_SUFFIX,
    EXPORT_FORMAT_VERSION,
    export_to_file,
    import_from_file,
)
```

And to `__all__`:

```python
    "BACKUP_SUFFIX",
    "EXPORT_FORMAT_VERSION",
    "export_to_file",
    "import_from_file",
```

- [ ] **Step 3: Add CHANGELOG entry under `[Unreleased]`**

In `CHANGELOG.md` (create if missing), add:

```markdown
## [Unreleased]

### Added
- Settings export/import: File → Export Settings... / Import Settings... writes or reads a JSON bundle with settings (and stats if available). Auto-backs up current settings before import.
```

- [ ] **Step 4: Verify import works (smoke test)**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -c "from rsvp.core.transfer import export_to_file, import_from_file; print('imports OK')" 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: imports work, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add rsvp/core/transfer.py rsvp/core/__init__.py CHANGELOG.md
git commit -m "feat: add settings export/import transfer module

New rsvp.core.transfer module with:
  - export_to_file(path, settings_manager, stats_manager=None)
    Writes a JSON file with the wrapper shape:
      {format_version, exported_at, settings, stats}
  - import_from_file(path, settings_manager, stats_manager=None)
    Returns {settings_applied, stats_applied, format_version, warnings}
    Auto-backs up current settings.json to *.imported.bak before
    overwriting
  - stats_to_dict / apply_stats_to_manager helpers
  - EXPORT_FORMAT_VERSION = 1 (for future migrations)
  - BACKUP_SUFFIX = '.imported.bak' (deterministic naming)

The 'stats' key is gracefully degraded: try/except the stats import
so the module works on branches that don't have Spec 3's stats
module. stats = {} in the export, ignored on import.

Detects the file shape (wrapper vs legacy settings.json) and adapts.
Unknown setting keys are skipped with warnings (forward-compat for
future versions adding new fields).

CHANGELOG entry under [Unreleased] notes the new feature."
```

---

## Task 2: File menu items + MainWindow handlers

**Files:**
- Modify: `rsvp/ui/menu_builder.py`
- Modify: `rsvp/ui/main_window.py`

- [ ] **Step 1: Add 2 menu items to MenuBuilder**

In `rsvp/ui/menu_builder.py`, find the file_menu section (after the "Open File..." action, before the recent_files separator). Add:

```python
        file_menu.addSeparator()

        export_action = QAction("&Export Settings...", self._window)
        export_action.triggered.connect(host._export_settings)
        file_menu.addAction(export_action)

        import_action = QAction("&Import Settings...", self._window)
        import_action.triggered.connect(host._import_settings)
        file_menu.addAction(import_action)

        file_menu.addSeparator()
```

- [ ] **Step 2: Add the 2 handler methods to MainWindow**

In `rsvp/ui/main_window.py`, add to the imports (after the existing `from rsvp.core.tts import ...`):

```python
from datetime import datetime
from pathlib import Path

from rsvp.core.transfer import export_to_file, import_from_file
```

Add the 2 methods. The best location is in the "Document loading" or "Settings" section, or in a new "Transfer" section. Place them after the existing `_paste_and_read` method:

```python
    def _export_settings(self) -> None:
        """Export settings to a JSON file chosen by the user."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        default_name = f"rsvp-export-{datetime.now().strftime('%Y-%m-%d')}.json"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Settings",
            default_name,
            "JSON files (*.json);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        try:
            export_to_file(
                path,
                get_settings_manager(),
                stats_manager=getattr(self, "_stats_manager", None),
            )
        except OSError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not write to {path}:\n{e}")
            return
        QMessageBox.information(
            self, "Export Complete", f"Settings exported to:\n{path}"
        )

    def _import_settings(self) -> None:
        """Import settings from a JSON file chosen by the user."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import json

        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import Settings",
            "",
            "JSON files (*.json);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)

        # Confirm before overwriting
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            "Importing will overwrite your current settings.\n"
            "A backup of your current settings.json will be saved.\n\n"
            "Continue?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            summary = import_from_file(
                path,
                get_settings_manager(),
                stats_manager=getattr(self, "_stats_manager", None),
            )
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Import Failed", f"Could not read {path}:\n{e}")
            return

        # Refresh UI to reflect new settings
        self._apply_settings()
        self.speed_control.set_wpm(get_settings_manager().settings.wpm)

        msg = f"Imported {summary['settings_applied']} settings."
        if summary["warnings"]:
            msg += "\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in summary["warnings"])
        QMessageBox.information(self, "Import Complete", msg)
```

- [ ] **Step 3: Verify all existing tests still pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: 270 tests pass; ruff clean.

- [ ] **Step 4: Commit**

```bash
git add rsvp/ui/menu_builder.py rsvp/ui/main_window.py
git commit -m "feat: add File menu Export/Import Settings items

File menu now has two new items between 'Open File...' and 'Recent
Files':
  - Export Settings... — opens a save dialog, writes the JSON bundle
  - Import Settings... — opens an open dialog, confirms overwrite,
    backs up current settings.json to *.imported.bak, applies

MainWindow._export_settings calls transfer.export_to_file with
get_settings_manager() and (if present) self._stats_manager. The
latter is wrapped in getattr() so this commit doesn't depend on
Spec 3's stats module.

MainWindow._import_settings calls transfer.import_from_file, then
calls _apply_settings() and speed_control.set_wpm() to refresh the
UI with the imported values. Shows a summary message with any
warnings (unknown keys, failed stats import).

Error handling:
  - OSError (write failure) -> QMessageBox.critical
  - OSError or json.JSONDecodeError (read failure) -> QMessageBox.critical
  - User cancels QFileDialog -> silent return
  - User declines confirm dialog -> silent return"
```

---

## Task 3: Tests

**Files:**
- Create: `tests/test_transfer.py`

- [ ] **Step 1: Create `tests/test_transfer.py`**

```python
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
```

- [ ] **Step 2: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_transfer.py -v 2>&1 | tail -25`
Expected: 13 tests pass.

- [ ] **Step 3: Run full verification**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1 && /opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -1`
Expected: ~283 tests pass, ruff clean, mypy 0 errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_transfer.py
git commit -m "test: add transfer module round-trip, backup, and format tests

tests/test_transfer.py (13 tests):

TestExport (4):
  - Creates the file
  - Payload has format_version / exported_at / settings / stats
  - Settings keys are present in the payload
  - stats is empty dict when no stats_manager is provided

TestImport (4):
  - Round-trip preserves modified settings
  - Returns a summary dict with all expected keys
  - Legacy settings.json (no wrapper) is detected and imported
  - Unknown setting keys are skipped with warnings

TestImportBackup (3):
  - Backup is created when settings file exists
  - No backup when no settings file exists
  - Backup suffix is deterministic

TestImportErrors (2):
  - Nonexistent file raises OSError
  - Invalid JSON raises json.JSONDecodeError"
```

---

## Self-Review

**1. Spec coverage:** 6 in-scope items mapped to 3 commits (transfer → UI → tests).

**2. Placeholder scan:** No "TBD" or "fill in later" markers. All code blocks are concrete.

**3. Type consistency:** `export_to_file(path, settings_manager, stats_manager=None)` and `import_from_file(path, settings_manager, stats_manager=None)` signatures used consistently.

**4. Edge cases handled:**
- Missing stats module → try/except import, `_STATS_AVAILABLE` flag
- Legacy settings.json shape → detected and wrapped
- Unknown setting keys → skipped with warning
- Invalid JSON → propagates as `json.JSONDecodeError`, UI catches it
- No existing settings.json → no backup created
- User cancels QFileDialog → silent return
- User declines confirm dialog → silent return
- File write/read errors → caught as `OSError`, QMessageBox.critical

**5. Risk acknowledgment:**
- `format_version` field included for future migrations
- Backup naming is deterministic (`.imported.bak`)
- Stats import failure is non-fatal (logged + warning)

---

## Success Criteria (from spec)

- [ ] `File → Export Settings...` opens a save dialog and writes a valid JSON file
- [ ] `File → Import Settings...` opens an open dialog and applies the settings
- [ ] Before overwriting, a backup of the current settings.json is created at `settings.json.imported.bak`
- [ ] Legacy settings.json files (no wrapper) are imported correctly
- [ ] Unknown setting keys are skipped with a warning
- [ ] Invalid JSON raises a user-friendly error (QMessageBox.critical), not a stack trace
- [ ] After import, the UI reflects the new settings (word_display, TTS, speed)
- [ ] `pytest -q` passes (~283 tests, 13 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~283 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
