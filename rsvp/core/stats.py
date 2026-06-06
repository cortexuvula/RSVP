"""Reading statistics: per-session, per-document, and all-time tracking."""

import json
import logging
import os
import platform
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    """A single reading session, from load_text to pause/stop/finish."""

    source: str | None
    source_type: str
    started_at: datetime
    ended_at: datetime
    words_read: int
    avg_wpm: float
    peak_wpm: int
    finished: bool


@dataclass
class DocumentStats:
    """Aggregated stats for a single source (file/URL)."""

    source: str
    source_type: str
    words_read: int
    total_time_seconds: float
    sessions_count: int
    last_read: datetime


@dataclass
class AllTimeStats:
    """Totals across all time."""

    total_words_read: int = 0
    total_time_seconds: float = 0.0
    sessions_count: int = 0

    @property
    def lifetime_avg_wpm(self) -> float:
        if self.total_time_seconds <= 0:
            return 0.0
        return self.total_words_read / (self.total_time_seconds / 60.0)


@dataclass
class StatsData:
    """Top-level container persisted to stats.json."""

    all_time: AllTimeStats = field(default_factory=AllTimeStats)
    per_document: dict[str, DocumentStats] = field(default_factory=dict)
    recent_sessions: list[SessionRecord] = field(default_factory=list)


class StatsManager:
    """Loads, saves, and accumulates reading statistics."""

    MAX_RECENT_SESSIONS = 30

    def __init__(self) -> None:
        self._data = StatsData()
        self._config_path = self._get_config_path()
        self._was_reset = False
        self.load()

    @property
    def data(self) -> StatsData:
        return self._data

    def _get_config_path(self) -> Path:
        """Get the path to the stats file."""
        system = platform.system()
        if system == "Windows":
            base = Path.home() / "AppData" / "Local" / "RSVP"
        elif system == "Darwin":
            base = Path.home() / "Library" / "Application Support" / "RSVP"
        else:
            xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            base = xdg_config / "rsvp"
        base.mkdir(parents=True, exist_ok=True)
        return base / "stats.json"

    def load(self) -> None:
        """Load stats from file. Resets to defaults on corruption."""
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, encoding="utf-8") as f:
                raw = json.load(f)
            self._data = self._from_dict(raw)
        except (OSError, json.JSONDecodeError):
            backup_path = self._config_path.with_suffix(".json.bak")
            try:
                shutil.copy2(self._config_path, backup_path)
            except OSError as copy_err:
                logger.warning("Could not back up corrupted stats file: %s", copy_err)
            logger.warning("Stats file corrupted, reset to defaults. Backup: %s", backup_path)
            self._data = StatsData()
            self._was_reset = True

    def save(self) -> None:
        """Persist stats to disk."""
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._to_dict(self._data), f, indent=2)
        except OSError as e:
            logger.warning("Failed to save stats to %s: %s", self._config_path, e)

    def was_reset(self) -> bool:
        """Check if stats were reset due to corruption. Clears the flag after reading."""
        result = self._was_reset
        self._was_reset = False
        return result

    def reset(self) -> None:
        """Clear all stats and persist."""
        self._data = StatsData()
        self.save()

    def record_session(self, record: SessionRecord) -> None:
        """Append a session: update all-time, per-doc, recent; persist."""
        duration = (record.ended_at - record.started_at).total_seconds()
        self._data.all_time.total_words_read += record.words_read
        self._data.all_time.total_time_seconds += duration
        self._data.all_time.sessions_count += 1

        if record.source:
            doc = self._data.per_document.get(record.source)
            if doc is None:
                doc = DocumentStats(
                    source=record.source,
                    source_type=record.source_type,
                    words_read=0,
                    total_time_seconds=0.0,
                    sessions_count=0,
                    last_read=record.ended_at,
                )
                self._data.per_document[record.source] = doc
            doc.words_read += record.words_read
            doc.total_time_seconds += duration
            doc.sessions_count += 1
            doc.last_read = record.ended_at

        self._data.recent_sessions.insert(0, record)
        self._data.recent_sessions = self._data.recent_sessions[: self.MAX_RECENT_SESSIONS]
        self.save()

    @staticmethod
    def _to_dict(data: StatsData) -> dict:
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

    @staticmethod
    def _from_dict(raw: dict) -> StatsData:
        all_time = AllTimeStats(**raw.get("all_time", {}))
        per_document = {
            src: DocumentStats(
                **{k: v for k, v in d.items() if k != "last_read"},
                last_read=datetime.fromisoformat(d["last_read"]),
            )
            for src, d in raw.get("per_document", {}).items()
        }
        recent = [
            SessionRecord(
                **{k: v for k, v in s.items() if k not in ("started_at", "ended_at")},
                started_at=datetime.fromisoformat(s["started_at"]),
                ended_at=datetime.fromisoformat(s["ended_at"]),
            )
            for s in raw.get("recent_sessions", [])
        ]
        return StatsData(
            all_time=all_time,
            per_document=per_document,
            recent_sessions=recent,
        )
