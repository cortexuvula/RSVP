"""Export and import settings (and stats if available) to/from a single JSON file."""

import importlib.util
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

# Optional stats module (may not be available on every branch).
# We use importlib.util.find_spec to detect availability without
# actually importing the module — this keeps the import cheap and
# avoids spurious F401 lint errors when stats isn't used.
_STATS_AVAILABLE = importlib.util.find_spec("rsvp.core.stats") is not None


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
    if (
        isinstance(payload, dict)
        and "settings" in payload
        and isinstance(payload["settings"], dict)
    ):
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
        "format_version": (
            payload.get("format_version", 0) if isinstance(payload, dict) else 0
        ),
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
