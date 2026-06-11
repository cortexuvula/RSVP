"""Reading statistics: per-session, per-document, and all-time tracking."""

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime

from rsvp.core.config import get_config_dir

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
        self._config_path = get_config_dir() / "stats.json"
        self._was_reset = False
        self._save_failed = False
        self.load()

    @property
    def data(self) -> StatsData:
        return self._data

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
        """Persist stats to disk atomically.

        Writes to a temp file first, then uses os.replace() for an atomic
        rename so that a crash mid-write never leaves a truncated file.
        """
        config_dir = self._config_path.parent
        tmp_fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(self._to_dict(self._data), f, indent=2)
            os.replace(tmp_path, self._config_path)
        except OSError as e:
            self._save_failed = True
            logger.warning("Failed to save stats to %s: %s", self._config_path, e)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def was_reset(self) -> bool:
        """Check if stats were reset due to corruption. Clears the flag after reading."""
        result = self._was_reset
        self._was_reset = False
        return result

    def save_failed(self) -> bool:
        """Check if the last save attempt failed. Clears the flag after reading."""
        result = self._save_failed
        self._save_failed = False
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
        # Validate AllTimeStats keys against its dataclass fields
        all_time_valid = {f.name for f in fields(AllTimeStats)}
        all_time_filtered = {k: v for k, v in raw.get("all_time", {}).items() if k in all_time_valid}
        all_time = AllTimeStats(**all_time_filtered)

        # Validate DocumentStats keys
        doc_valid = {f.name for f in fields(DocumentStats)}
        per_document = {}
        for src, d in raw.get("per_document", {}).items():
            filtered = {k: v for k, v in d.items() if k in doc_valid and k != "last_read"}
            filtered["last_read"] = datetime.fromisoformat(d["last_read"])
            per_document[src] = DocumentStats(**filtered)

        # Validate SessionRecord keys
        session_valid = {f.name for f in fields(SessionRecord)}
        recent = []
        for s in raw.get("recent_sessions", []):
            filtered = {
                k: v for k, v in s.items() if k in session_valid and k not in ("started_at", "ended_at")
            }
            filtered["started_at"] = datetime.fromisoformat(s["started_at"])
            filtered["ended_at"] = datetime.fromisoformat(s["ended_at"])
            recent.append(SessionRecord(**filtered))

        return StatsData(
            all_time=all_time,
            per_document=per_document,
            recent_sessions=recent,
        )
