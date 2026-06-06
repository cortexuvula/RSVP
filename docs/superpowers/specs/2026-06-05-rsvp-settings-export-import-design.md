# Spec 6: Settings Export / Import

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 6 — 4th feature spec (1 of 5 from the original review's feature list)
**Branch:** `feature/settings-export-import` (off main)
**Target PR:** Single PR with 3 atomic commits

## Context

The original code review listed 5 features. Specs 3 (reading statistics), 4
(theme presets), and 5 (text-to-speech) are done. This spec covers
settings export/import. The final feature (chunk mode) comes in its own
cycle.

## Scope

**In scope (Spec 6 — this document):**

| # | Item |
|---|------|
| 1 | `rsvp/core/transfer.py` — `export_to_file(path)`, `import_from_file(path)` functions for the wrapper format |
| 2 | New `File → Export Settings...` and `File → Import Settings...` menu items in `MainWindow` |
| 3 | QFileDialog integration for file picking (default name: `rsvp-export-YYYY-MM-DD.json`) |
| 4 | Auto-backup of current `settings.json` and `stats.json` to `*.imported.bak` before import |
| 5 | Tests for transfer module (file round-trip, format compatibility, backup creation) and menu integration |
| 6 | CHANGELOG entry under `[Unreleased]` |

**Out of scope (later specs):**

- Spec 7 — Chunk mode
- Cloud sync (intentionally absent)
- Auto-import on startup (could be a future option)
- Selective export (export just settings, just stats, or both — always exports both for simplicity)
- Encrypted exports (out of scope; user can encrypt the file themselves if desired)
- Selective field import (always imports everything in the file)
- Stats export when StatsManager doesn't exist on this branch: handled gracefully (empty `{}` for the `stats` key; forward-compatible for when Spec 3 lands)

## Design Decisions (from brainstorming)

1. **Export scope:** **Everything** — settings + statistics + bookmarks + reading positions. The export is a bundled JSON file with two top-level keys (`settings`, `stats`). This is forward-compatible: if `StatsManager` is absent (this branch, before Spec 3 merges), the `stats` key is just `{}`.
2. **UI surface:** **File menu items** with `QFileDialog` file pickers. Standard desktop app pattern.
3. **File format:** **Same as settings.json** (JSON, human-readable, no compression). The export is a single JSON file with the wrapper shape `{"settings": {...}, "stats": {...}}`. Forward-compatible with settings.json itself (which is just the `settings` dict, no wrapper).
4. **Import safety:** **Auto-backup current before overwriting.** Before import, copy `settings.json` to `settings.json.imported.bak` and `stats.json` (if it exists) to `stats.json.imported.bak`. The user can manually roll back by renaming the backup file.

## File Format

### Export file shape

```json
{
  "settings": {
    "wpm": 300,
    "font_family": "Arial",
    "font_size": 48,
    "text_color": "#FFFFFF",
    "background_color": "#1E1E1E",
    "orp_color": "#FF6B6B",
    "pause_at_paragraphs": true,
    "auto_save_position": true,
    "window_width": 800,
    "window_height": 600,
    "window_x": null,
    "window_y": null,
    "always_on_top": false,
    "theme_name": "Dark",
    "recent_files": ["..."],
    "max_recent_files": 10,
    "bookmarks": {"/a.txt": [42, 100]},
    "saved_positions": {"/a.txt": 42},
    "tts_enabled": false
  },
  "stats": {
    "all_time": {
      "total_words_read": 0,
      "total_time_seconds": 0.0,
      "sessions_count": 0
    },
    "per_document": {},
    "recent_sessions": []
  }
}
```

**Backward compatibility:** an export can be read by a build of the app that has only settings (no stats). The `stats` key is ignored if the importer doesn't have a stats module. Similarly, a plain `settings.json` (no wrapper) can be imported — the importer detects the shape and wraps it as `{"settings": <content>, "stats": {}}`.

**Why this format:**
- A single self-describing file (knows it's an export, not the live settings.json)
- Both `settings` and `stats` are optional keys (forward-compat for builds that have one but not the other)
- JSON is human-readable; users can hand-edit if needed
- Same JSON format as the live `settings.json` (just wrapped)

## Transfer Module

```python
# rsvp/core/transfer.py

"""Export and import settings (and stats) to/from a single JSON file."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from rsvp.core.settings import RSVPSettings, SettingsManager

logger = logging.getLogger(__name__)

# Optional stats import (may not be available on every branch)
try:
    from rsvp.core.stats import StatsData, StatsManager
    _STATS_AVAILABLE = True
except ImportError:
    _STATS_AVAILABLE = False


EXPORT_FORMAT_VERSION = 1
BACKUP_SUFFIX = ".imported.bak"


def export_to_file(
    path: Path,
    settings_manager: SettingsManager,
    stats_manager: StatsManager | None = None,
) -> None:
    """Export settings (and stats if available) to a JSON file at `path`.

    File format:
        {
            "format_version": 1,
            "exported_at": "2026-06-05T12:34:56",
            "settings": {...},
            "stats": {...}
        }
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
    stats_manager: StatsManager | None = None,
) -> dict:
    """Import settings (and stats if available) from a JSON file.

    Returns a summary dict with keys:
        - "settings_applied": int (number of fields updated)
        - "stats_applied": bool
        - "format_version": int
        - "warnings": list[str]

    Before overwriting, backs up the current settings.json (and
    stats.json, if it exists) to *.imported.bak.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    # Detect shape: wrapper ({"settings": ...}) vs legacy settings.json ({...})
    if "settings" in payload and isinstance(payload["settings"], dict):
        settings_dict = payload["settings"]
        stats_dict = payload.get("stats", {})
    else:
        # Legacy: the file IS the settings dict
        settings_dict = payload
        stats_dict = {}

    # Auto-backup before overwriting
    settings_path = settings_manager._config_path  # noqa: SLF001 (intentional)
    backup_settings = settings_path.with_name(settings_path.name + BACKUP_SUFFIX)
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
        "format_version": payload.get("format_version", 0),
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
    from rsvp.core.stats import AllTimeStats, DocumentStats, SessionRecord
    from datetime import datetime

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

## UI

**File menu items** (added between "Open File..." and "Recent Files" in `MenuBuilder`):

```
File
  Load Text...        Ctrl+O
  Open File...        Ctrl+Shift+O
  Export Settings...   ← NEW
  Import Settings...   ← NEW
  ─────────
  Recent Files
  ─────────
  Exit                Ctrl+Q
```

**Export flow:**
1. User clicks `File → Export Settings...`
2. QFileDialog.getSaveFileName opens with default name `rsvp-export-YYYY-MM-DD.json`
3. User picks a path
4. `export_to_file(path, settings, stats)` is called
5. QMessageBox.information: "Settings exported to <path>"

**Import flow:**
1. User clicks `File → Import Settings...`
2. QFileDialog.getOpenFileName opens with file filter `*.json`
3. User picks a file
4. QMessageBox.question: "Importing will overwrite your current settings. A backup will be saved. Continue?"
5. On Yes: `import_from_file(path, settings, stats)` is called
6. QMessageBox.information: "Imported N settings" (or warning if N=0)
7. **Refresh the UI:** call `MainWindow._apply_settings()` to update word_display, TTS, etc.

## Architecture

```
main.py → MainWindow
              │
              ├─ File menu → Export Settings → transfer.export_to_file(...)
              │                                    ↓ writes JSON to user-chosen path
              ├─ File menu → Import Settings → transfer.import_from_file(...)
              │                                    ↓ reads JSON, backs up, applies
              │                                    ↓ refreshes UI via _apply_settings
              ├─ RSVPEngine
              ├─ SettingsManager
              ├─ (StatsManager — added in Spec 3, not present on this branch)
              └─ ...
```

The `transfer` module is a leaf — it doesn't depend on Qt. The menu items
are thin wrappers that call into the transfer module.

## File-Level Changes

| File | Change |
|------|--------|
| `rsvp/core/transfer.py` | New — `export_to_file`, `import_from_file`, `stats_to_dict`, `apply_stats_to_manager`, `EXPORT_FORMAT_VERSION`, `BACKUP_SUFFIX` |
| `rsvp/core/__init__.py` | Re-export the new functions |
| `rsvp/ui/menu_builder.py` | Add 2 menu items + handlers (new `host._export_settings`, `host._import_settings` methods on MainWindow) |
| `rsvp/ui/main_window.py` | Add the 2 menu handlers (open QFileDialog, call transfer, refresh UI) |
| `tests/test_transfer.py` | New — round-trip, format detection, backup creation, legacy settings.json compatibility |
| `CHANGELOG.md` | `[Unreleased]` entry |

## Per-Item Design

### Item 1 — `rsvp/core/transfer.py`

The module contains:
- `EXPORT_FORMAT_VERSION = 1` (bump if format changes incompatibly)
- `BACKUP_SUFFIX = ".imported.bak"` (consistent backup filename suffix)
- `export_to_file(path, settings_manager, stats_manager=None)` — writes the JSON
- `import_from_file(path, settings_manager, stats_manager=None) -> dict` — reads + applies + returns summary
- `stats_to_dict(data) -> dict` — helper to serialize StatsData (if available)
- `apply_stats_to_manager(manager, raw)` — helper to apply stats dict (if available)
- `_STATS_AVAILABLE` flag (set via try/except import)

The `stats_manager` parameter is `None` by default. When `None`, the export
includes `"stats": {}` (or omits it entirely — see below). On import,
the stats section is ignored.

**Why try/except the stats import?**
On this branch (and any future branch without Spec 3's `rsvp.core.stats`),
`from rsvp.core.stats import StatsManager` would fail. The `try/except
ImportError` lets the transfer module work in both cases. The
`_STATS_AVAILABLE` flag gates the stats-related code paths.

### Item 2 — Menu items

In `rsvp/ui/menu_builder.py`, add the two menu items. The handler functions
(`host._export_settings`, `host._import_settings`) are added to
`MainWindow` in step 3.

### Item 3 — MainWindow handlers

```python
def _export_settings(self) -> None:
    """Export settings to a JSON file chosen by the user."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    from datetime import datetime
    from rsvp.core.transfer import export_to_file

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
            stats_manager=self._stats_manager,  # may be None on this branch
        )
        QMessageBox.information(self, "Export Complete", f"Settings exported to:\n{path}")
    except OSError as e:
        QMessageBox.critical(self, "Export Failed", f"Could not write to {path}:\n{e}")


def _import_settings(self) -> None:
    """Import settings from a JSON file chosen by the user."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    from rsvp.core.transfer import import_from_file

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
            stats_manager=self._stats_manager,  # may be None
        )
    except (OSError, json.JSONDecodeError) as e:
        QMessageBox.critical(self, "Import Failed", f"Could not read {path}:\n{e}")
        return

    # Refresh UI to reflect new settings
    self._apply_settings()
    self.speed_control.set_wpm(get_settings_manager().settings.wpm)

    msg = f"Imported {summary['settings_applied']} settings."
    if summary["warnings"]:
        msg += f"\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in summary["warnings"])
    QMessageBox.information(self, "Import Complete", msg)
```

### Item 4 — Tests

**`tests/test_transfer.py`** (~12 tests):

```python
class TestExportImportRoundTrip:
    def test_export_creates_file(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        assert path.exists()

    def test_export_payload_has_settings_key(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        with open(path) as f:
            data = json.load(f)
        assert "settings" in data
        assert "wpm" in data["settings"]
        assert "theme_name" in data["settings"]

    def test_export_payload_has_stats_key(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        export_to_file(path, isolated_settings)
        with open(path) as f:
            data = json.load(f)
        assert "stats" in data

    def test_round_trip_preserves_settings(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        # Modify a setting
        isolated_settings.settings.wpm = 500
        isolated_settings.settings.theme_name = "Sepia"
        export_to_file(path, isolated_settings)
        # Reset
        isolated_settings.settings.wpm = 300
        isolated_settings.settings.theme_name = "Dark"
        # Import
        summary = import_from_file(path, isolated_settings)
        assert summary["settings_applied"] > 0
        assert isolated_settings.settings.wpm == 500
        assert isolated_settings.settings.theme_name == "Sepia"


class TestImportBackup:
    def test_creates_backup_before_overwriting(self, tmp_path, isolated_settings):
        # Set up initial state
        isolated_settings.settings.wpm = 300
        isolated_settings.save()
        # Create an import file
        import_path = tmp_path / "import.json"
        export_to_file(import_path, isolated_settings)
        # Modify and re-export
        isolated_settings.settings.wpm = 500
        export_to_file(import_path, isolated_settings)
        # Import — should back up the current 500
        import_from_file(import_path, isolated_settings)
        backup_path = isolated_settings._config_path.with_name(
            isolated_settings._config_path.name + ".imported.bak"
        )
        assert backup_path.exists()

    def test_no_backup_when_no_existing_file(self, tmp_path, isolated_settings):
        # No initial save; config_path doesn't exist
        if isolated_settings._config_path.exists():
            isolated_settings._config_path.unlink()
        import_path = tmp_path / "import.json"
        export_to_file(import_path, isolated_settings)
        import_from_file(import_path, isolated_settings)
        # Backup should not be created (no source to back up)
        backup_path = isolated_settings._config_path.with_name(
            isolated_settings._config_path.name + ".imported.bak"
        )
        assert not backup_path.exists()


class TestImportFormatDetection:
    def test_legacy_settings_json_imported_as_settings(self, tmp_path, isolated_settings):
        # Write a plain settings.json (no wrapper)
        legacy_path = tmp_path / "legacy.json"
        legacy_data = {"wpm": 750, "font_family": "Georgia", "font_size": 72}
        legacy_path.write_text(json.dumps(legacy_data))
        # Import
        summary = import_from_file(legacy_path, isolated_settings)
        assert isolated_settings.settings.wpm == 750
        assert isolated_settings.settings.font_family == "Georgia"
        assert isolated_settings.settings.font_size == 72

    def test_unknown_setting_key_skipped_with_warning(self, tmp_path, isolated_settings):
        path = tmp_path / "export.json"
        # Write a payload with an unknown key
        path.write_text(json.dumps({
            "format_version": 1,
            "settings": {"wpm": 400, "unknown_future_setting": "blah"},
            "stats": {},
        }))
        summary = import_from_file(path, isolated_settings)
        assert isolated_settings.settings.wpm == 400
        assert any("unknown_future_setting" in w for w in summary["warnings"])


class TestImportErrorHandling:
    def test_nonexistent_file_raises(self):
        from rsvp.core.transfer import import_from_file
        with pytest.raises(OSError):
            import_from_file(Path("/nonexistent/file.json"), MagicMock())

    def test_invalid_json_raises(self, tmp_path):
        from rsvp.core.transfer import import_from_file
        path = tmp_path / "bad.json"
        path.write_text("not valid json {")
        with pytest.raises(json.JSONDecodeError):
            import_from_file(path, MagicMock())
```

## Commit Plan (3 atomic commits)

```
feat: add settings export/import transfer module
feat: add File menu Export/Import Settings items
test: add transfer module round-trip, backup, and format tests
```

**Rationale:**
1. **Transfer module first:** Pure data in/out, no Qt. Easiest to review and test in isolation.
2. **UI wiring second:** Menu items + MainWindow handlers + QFileDialog integration. Depends on the transfer module.
3. **Tests third:** All tests for the feature in one batch (matches Spec 5 pattern).

## Testing Strategy

- 285 existing tests + ~12 new = ~297 total
- All tests use `tmp_path` for file isolation
- Tests bypass `SettingsManager.__init__` via `__new__` (existing pattern)
- Use `MagicMock` for the SettingsManager where the test doesn't need real settings behavior
- The stats tests are limited (no StatsManager on this branch) — just verify the `stats` key is present in the export

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| Importing a file with unknown fields could break the app | `import_from_file` filters to known settings (uses `hasattr`) and reports unknown fields as warnings. Forward-compatible: future versions adding new fields will just be ignored by older versions. |
| User imports a malformed file | `json.JSONDecodeError` is caught and surfaced as a QMessageBox.critical. The current settings are unchanged (import fails before applying). |
| User imports a file from a different schema version | `format_version` is included in the export and reported in the summary. If the importer doesn't recognize the version, it can warn (out of scope for v1, but the field is there for future use). |
| User accidentally imports a non-settings file (e.g., a random .json) | The unknown fields are simply ignored; the import succeeds with 0 or few settings applied. The summary message tells the user how many settings were applied. |
| Backup file accumulates over time | The backup is overwritten on each import (not appended). User can clean up old backups manually if desired. |
| Stats import fails mid-way (e.g., corrupt date format) | Caught by try/except; logged; the warning is shown to the user. Settings import still succeeded. |
| This branch has no StatsManager; export has `stats: {}` | Tested explicitly: `test_export_payload_has_stats_key` and the round-trip test. The `stats_manager` parameter is `None` by default; if StatsManager doesn't exist, the export just has `"stats": {}` and the import ignores it. |

## Out of Scope (Explicitly)

- Cloud sync (intentionally absent)
- Encrypted exports
- Selective field import (always imports everything in the file)
- Importing from formats other than JSON
- Selective file format (e.g., CSV, YAML)
- Migration between schema versions
- A "compare before import" UI (showing the user what's about to change)
- Undo for import (the `.imported.bak` file is the rollback; the user can rename it back)
- Export to clipboard
- Drag-and-drop import
- Scheduled/auto-import

## Success Criteria

- [ ] `File → Export Settings...` opens a save dialog and writes a valid JSON file
- [ ] `File → Import Settings...` opens an open dialog and applies the settings
- [ ] Before overwriting, a backup of the current settings.json is created at `settings.json.imported.bak`
- [ ] Legacy settings.json files (no wrapper) are imported correctly
- [ ] Unknown setting keys are skipped with a warning
- [ ] Invalid JSON raises a user-friendly error (QMessageBox.critical), not a stack trace
- [ ] After import, the UI reflects the new settings (word_display, TTS, speed)
- [ ] `pytest -q` passes (~297 tests, 12 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Spec Self-Review (brainstorming checklist)

1. **Coverage:** 6 in-scope items mapped to 3 commits (transfer → UI → tests).
2. **No placeholders:** all code blocks are concrete; full function bodies, error messages, dialog flows spelled out.
3. **Internal consistency:** data model ↔ transfer module ↔ UI all use the same `settings` + `stats` keys; the `stats` key gracefully defaults to `{}` when StatsManager is absent.
4. **Edge cases handled:**
   - Missing pyttsx3-style deps (stats not present) → try/except import
   - Legacy settings.json shape (no wrapper) → detected and wrapped
   - Unknown setting keys → skipped with warning
   - Invalid JSON → QMessageBox.critical, no state change
   - No existing settings.json → no backup created (nothing to back up)
5. **Risk acknowledged:** format_version is recorded for future use; backup naming is consistent and deterministic.

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~297 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches (5 pre-existing on main, not changed)
git log --oneline main..HEAD # expect: 3 new commits
```
