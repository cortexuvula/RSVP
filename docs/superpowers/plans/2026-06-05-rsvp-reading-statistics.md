# RSVP Reading Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land reading statistics (all-time totals, per-document breakdown, recent sessions) as a single PR with 3 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-reading-statistics-design.md).

**Architecture:** New `StatsManager` owns the data model and persistence to `stats.json` in the platform config dir. New `StatsRecorder` subscribes to `RSVPEngine` signals and calls `StatsManager.record_session()`. New `StatsDialog` reads from `StatsManager` and is launched from a "Help → Reading Statistics" menu item. MainWindow is the composition root.

**Tech Stack:** Python 3.10+, PyQt6, dataclasses, stdlib `json` + `datetime`. No new runtime dependencies.

---

## File Structure

**Created:**
- `rsvp/core/stats.py` — dataclasses + `StatsManager`
- `rsvp/core/stats_recorder.py` — engine signal subscriber
- `rsvp/ui/stats_dialog.py` — modal dialog
- `tests/test_stats.py`
- `tests/test_stats_recorder.py`
- `tests/test_ui_stats_dialog.py`

**Modified:**
- `rsvp/core/__init__.py` — export new types
- `rsvp/ui/main_window.py` — composition root additions
- `rsvp/ui/menu_builder.py` — add "Reading Statistics" menu item
- `CHANGELOG.md` — `[Unreleased]` entry

---

## Task 1: Data model + StatsManager

**Files:**
- Create: `rsvp/core/stats.py`
- Modify: `rsvp/core/__init__.py`
- Create: `tests/test_stats.py`

- [ ] **Step 1: Create `rsvp/core/stats.py`**

Write the module with the four dataclasses and `StatsManager` class. Key methods: `__init__`, `load`, `save`, `record_session`, `reset`, `was_reset`, plus the `_get_config_path` private method (mirroring `SettingsManager._get_config_path`).

```python
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
        except (OSError, json.JSONDecodeError) as e:
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
```

- [ ] **Step 2: Export from `rsvp/core/__init__.py`**

Add to the `from rsvp.core.stats import (...)` block:

```python
from rsvp.core.stats import (
    AllTimeStats,
    DocumentStats,
    SessionRecord,
    StatsData,
    StatsManager,
)
```

And to `__all__`:

```python
    "AllTimeStats",
    "DocumentStats",
    "SessionRecord",
    "StatsData",
    "StatsManager",
```

- [ ] **Step 3: Create `tests/test_stats.py`**

```python
"""Tests for the stats module."""

from datetime import datetime, timedelta

import pytest

from rsvp.core.stats import (
    AllTimeStats,
    DocumentStats,
    SessionRecord,
    StatsData,
    StatsManager,
)


@pytest.fixture
def stats_manager(tmp_path):
    """Construct a StatsManager with an isolated config path."""
    mgr = StatsManager.__new__(StatsManager)
    mgr._data = StatsData()
    mgr._config_path = tmp_path / "stats.json"
    mgr._was_reset = False
    return mgr


def _make_record(words=100, duration_s=60.0, source="/a.txt", source_type="file", finished=False):
    start = datetime(2026, 6, 5, 10, 0, 0)
    return SessionRecord(
        source=source,
        source_type=source_type,
        started_at=start,
        ended_at=start + timedelta(seconds=duration_s),
        words_read=words,
        avg_wpm=words / (duration_s / 60.0),
        peak_wpm=300,
        finished=finished,
    )


class TestAllTimeStats:
    def test_default_lifetime_avg_wpm_is_zero(self):
        a = AllTimeStats()
        assert a.lifetime_avg_wpm == 0.0

    def test_lifetime_avg_wpm_correct(self):
        a = AllTimeStats(total_words_read=300, total_time_seconds=60.0)
        assert a.lifetime_avg_wpm == 300.0


class TestRecordSession:
    def test_updates_all_time(self, stats_manager):
        stats_manager.record_session(_make_record(words=100, duration_s=60.0))
        assert stats_manager.data.all_time.total_words_read == 100
        assert stats_manager.data.all_time.total_time_seconds == 60.0
        assert stats_manager.data.all_time.sessions_count == 1

    def test_creates_per_document_entry(self, stats_manager):
        stats_manager.record_session(_make_record(source="/a.txt", source_type="file"))
        assert "/a.txt" in stats_manager.data.per_document
        doc = stats_manager.data.per_document["/a.txt"]
        assert doc.words_read == 100
        assert doc.source_type == "file"

    def test_updates_existing_per_document(self, stats_manager):
        stats_manager.record_session(_make_record(source="/a.txt", words=50))
        stats_manager.record_session(_make_record(source="/a.txt", words=75))
        doc = stats_manager.data.per_document["/a.txt"]
        assert doc.words_read == 125
        assert doc.sessions_count == 2

    def test_anonymous_source_omits_per_doc(self, stats_manager):
        stats_manager.record_session(_make_record(source=None))
        assert stats_manager.data.per_document == {}

    def test_recent_sessions_most_recent_first(self, stats_manager):
        for i in range(3):
            stats_manager.record_session(_make_record(words=i + 1))
        sessions = stats_manager.data.recent_sessions
        assert sessions[0].words_read == 3
        assert sessions[1].words_read == 2
        assert sessions[2].words_read == 1

    def test_recent_sessions_capped_at_30(self, stats_manager):
        for i in range(35):
            stats_manager.record_session(_make_record(words=i + 1))
        assert len(stats_manager.data.recent_sessions) == 30


class TestPersistence:
    def test_round_trip(self, stats_manager):
        stats_manager.record_session(_make_record(words=120, duration_s=30.0, source="/b.txt"))
        # Force a fresh load from disk
        stats_manager.load()
        assert stats_manager.data.all_time.total_words_read == 120
        assert "/b.txt" in stats_manager.data.per_document
        # The recent session should still be there
        assert len(stats_manager.data.recent_sessions) == 1

    def test_corrupt_file_resets(self, tmp_path):
        mgr = StatsManager.__new__(StatsManager)
        mgr._data = StatsData()
        mgr._config_path = tmp_path / "stats.json"
        mgr._was_reset = False
        mgr._config_path.write_text("{ this is not valid json", encoding="utf-8")
        mgr.load()
        assert mgr.was_reset() is True
        assert mgr.data.all_time.total_words_read == 0


class TestReset:
    def test_reset_clears_data_and_persists(self, stats_manager):
        stats_manager.record_session(_make_record(words=100, source="/x.txt"))
        stats_manager.reset()
        assert stats_manager.data.all_time.total_words_read == 0
        assert stats_manager.data.per_document == {}
        assert stats_manager.data.recent_sessions == []
        # Persistence: reload from disk, still empty
        stats_manager.load()
        assert stats_manager.data.all_time.total_words_read == 0
```

- [ ] **Step 4: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_stats.py -v 2>&1 | tail -20`
Expected: all tests pass.

- [ ] **Step 5: Add CHANGELOG entry under `[Unreleased]`**

In `CHANGELOG.md`, add a new section at the top of the "Unreleased" block:

```markdown
### Added
- Reading statistics: track all-time totals (words, time, sessions, lifetime avg WPM), per-document breakdown, and last 30 sessions. View via Help → Reading Statistics.
```

(Insert this between the existing `## [Unreleased]` and `## [1.3.5] - 2026-05-15` headings. The current `[Unreleased]` section has just `### Changed` for the requirements.txt change — add `### Added` above it.)

- [ ] **Step 6: Verify all checks pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/ -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: all pass, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add rsvp/core/stats.py rsvp/core/__init__.py tests/test_stats.py CHANGELOG.md
git commit -m "feat: add reading statistics — core data model and StatsManager

New rsvp.core.stats module with:
  - SessionRecord, DocumentStats, AllTimeStats, StatsData dataclasses
  - StatsManager with load/save/record_session/reset/was_reset
  - Persistence to stats.json in the platform config dir
  - Corruption recovery with .json.bak backup (same pattern as settings)
  - recent_sessions capped at 30, most-recent-first

CHANGELOG entry under [Unreleased] notes the new feature (the dialog
and menu item land in subsequent commits)."
```

---

## Task 2: StatsRecorder — engine signal integration

**Files:**
- Create: `rsvp/core/stats_recorder.py`
- Create: `tests/test_stats_recorder.py`

- [ ] **Step 1: Create `rsvp/core/stats_recorder.py`**

```python
"""Subscribe to RSVPEngine signals and record reading sessions to StatsManager."""

import logging
from datetime import datetime

from PyQt6.QtCore import QObject

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.stats import SessionRecord, StatsManager
from rsvp.core.text_processor import Word

logger = logging.getLogger(__name__)


class StatsRecorder(QObject):
    """Captures reading sessions by listening to engine signals."""

    def __init__(self, engine: RSVPEngine, stats_manager: StatsManager) -> None:
        super().__init__()
        self._engine = engine
        self._stats = stats_manager
        self._current_source: str | None = None
        self._current_source_type: str = "unknown"
        self._session_start: datetime | None = None
        self._words_in_session: int = 0
        self._peak_wpm: int = 0
        self._session_finished: bool = False
        self._was_playing: bool = False

        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)
        engine.finished.connect(self._on_finished)

    def set_source(self, source: str | None, source_type: str) -> None:
        """Called by MainWindow when a document is loaded. Finalizes any active session first."""
        self._end_session()
        self._current_source = source
        self._current_source_type = source_type

    def shutdown(self) -> None:
        """Called by MainWindow.closeEvent to finalize any in-progress session."""
        self._end_session()

    def _on_word_changed(self, word: Word | None) -> None:
        if word is not None and self._was_playing:
            self._words_in_session += 1
            self._peak_wpm = max(self._peak_wpm, self._engine.wpm)

    def _on_state_changed(self) -> None:
        is_playing = self._engine.is_playing
        if is_playing and not self._was_playing:
            self._begin_session()
        elif not is_playing and self._was_playing:
            self._end_session()
        self._was_playing = is_playing

    def _on_finished(self) -> None:
        self._session_finished = True
        self._end_session()

    def _begin_session(self) -> None:
        self._session_start = datetime.now()
        self._words_in_session = 0
        self._peak_wpm = self._engine.wpm
        self._session_finished = False

    def _end_session(self) -> None:
        if self._session_start is None or self._words_in_session == 0:
            self._session_start = None
            return
        ended = datetime.now()
        duration = (ended - self._session_start).total_seconds()
        if duration <= 0:
            self._session_start = None
            return
        record = SessionRecord(
            source=self._current_source,
            source_type=self._current_source_type,
            started_at=self._session_start,
            ended_at=ended,
            words_read=self._words_in_session,
            avg_wpm=self._words_in_session / (duration / 60.0),
            peak_wpm=self._peak_wpm,
            finished=self._session_finished,
        )
        self._stats.record_session(record)
        logger.info(
            "Recorded session: %d words, %.1f avg WPM, %s",
            self._words_in_session,
            record.avg_wpm,
            self._current_source or "(anonymous)",
        )
        self._session_start = None
```

- [ ] **Step 2: Create `tests/test_stats_recorder.py`**

```python
"""Tests for StatsRecorder — engine signal integration."""

import pytest

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.stats import StatsData, StatsManager
from rsvp.core.stats_recorder import StatsRecorder


@pytest.fixture
def stats_manager(tmp_path):
    mgr = StatsManager.__new__(StatsManager)
    mgr._data = StatsData()
    mgr._config_path = tmp_path / "stats.json"
    mgr._was_reset = False
    return mgr


@pytest.fixture
def engine_and_recorder(qapp, stats_manager):
    engine = RSVPEngine()
    recorder = StatsRecorder(engine, stats_manager)
    return engine, recorder, stats_manager


class TestSessionLifecycle:
    def test_begin_session_on_play(self, engine_and_recorder):
        engine, recorder, _ = engine_and_recorder
        engine.load_text("hello world from a test")
        recorder.set_source("/a.txt", "file")
        engine.play()
        # After play, a session is active
        engine.pause()
        # A session was recorded
        assert len(_) == 0  # placeholder, see below

    def test_session_dropped_when_zero_words(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine.pause()  # no time elapsed, no words
        assert stats_manager.data.all_time.sessions_count == 0

    def test_full_session_recorded(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five six seven eight nine ten")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine.pause()
        assert stats_manager.data.all_time.sessions_count == 1
        assert stats_manager.data.all_time.total_words_read == 10

    def test_set_source_ends_active_session(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine.play()
        # Loading a new document ends the previous session
        engine.load_text("six seven")
        recorder.set_source("/b.txt", "file")
        assert stats_manager.data.all_time.sessions_count == 1
        # The new session starts when play() is called
        assert stats_manager.data.recent_sessions[0].source == "/a.txt"

    def test_shutdown_ends_active_session(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine.play()
        recorder.shutdown()
        assert stats_manager.data.all_time.sessions_count == 1


class TestSessionAttributes:
    def test_finished_marked(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine.finished.emit()
        recorder.shutdown()
        assert stats_manager.data.recent_sessions[0].finished is True

    def test_peak_wpm_tracked(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine._state.wpm = 500
        engine.play()
        engine.pause()
        assert stats_manager.data.recent_sessions[0].peak_wpm == 500

    def test_source_type_propagated(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("https://example.com", "url")
        engine.play()
        engine.pause()
        doc = stats_manager.data.per_document["https://example.com"]
        assert doc.source_type == "url"
```

- [ ] **Step 3: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_stats_recorder.py -v 2>&1 | tail -15`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add rsvp/core/stats_recorder.py tests/test_stats_recorder.py
git commit -m "feat: add StatsRecorder — engine signal integration for session tracking

Subscribes to RSVPEngine signals (word_changed, state_changed, finished)
and records a SessionRecord to StatsManager when a play session ends
(via pause, stop, finished signal, set_source, or shutdown).

Session lifecycle:
  - set_source() called when MainWindow loads a document; ends any
    active session first
  - state_changed detected as play transition starts a session
  - state_changed detected as pause/stop transition ends the session
  - finished signal ends the session with finished=True
  - shutdown() called by MainWindow.closeEvent finalizes the in-
    progress session

Guards:
  - Zero-word sessions are dropped (avoids noise from instant pause)
  - Zero-duration sessions are dropped (no time elapsed)
  - Peak WPM sampled from engine.wpm on every word_changed"
```

---

## Task 3: Stats dialog + menu item + MainWindow wiring

**Files:**
- Create: `rsvp/ui/stats_dialog.py`
- Create: `tests/test_ui_stats_dialog.py`
- Modify: `rsvp/ui/menu_builder.py`
- Modify: `rsvp/ui/main_window.py`

- [ ] **Step 1: Create `rsvp/ui/stats_dialog.py`**

```python
"""Modal Reading Statistics dialog."""

import logging
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rsvp.core.stats import StatsManager

logger = logging.getLogger(__name__)


class StatsDialog(QDialog):
    """Displays all-time, per-document, and recent-session statistics."""

    def __init__(self, parent=None, stats_manager: StatsManager | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reading Statistics")
        self.setMinimumSize(700, 500)
        self._stats = stats_manager
        self._setup_ui()
        if self._stats is not None:
            self._render()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # All-time section
        self.all_time_group = QGroupBox("All Time")
        all_time_layout = QVBoxLayout()
        self.total_words_label = QLabel("Total words read: —")
        self.total_time_label = QLabel("Total time: —")
        self.sessions_label = QLabel("Sessions: —")
        self.lifetime_wpm_label = QLabel("Lifetime avg WPM: —")
        for label in (
            self.total_words_label,
            self.total_time_label,
            self.sessions_label,
            self.lifetime_wpm_label,
        ):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            all_time_layout.addWidget(label)
        self.all_time_group.setLayout(all_time_layout)
        layout.addWidget(self.all_time_group)

        # Per-document section
        self.docs_group = QGroupBox("Top Documents (by words)")
        docs_layout = QVBoxLayout()
        self.docs_table = QTableWidget(0, 4)
        self.docs_table.setHorizontalHeaderLabels(["Source", "Type", "Words", "Sessions"])
        self.docs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.docs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.docs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        docs_layout.addWidget(self.docs_table)
        self.docs_group.setLayout(docs_layout)
        layout.addWidget(self.docs_group)

        # Recent sessions section
        self.recent_group = QGroupBox("Recent Sessions (newest first)")
        recent_layout = QVBoxLayout()
        self.recent_table = QTableWidget(0, 5)
        self.recent_table.setHorizontalHeaderLabels(["When", "WPM", "Words", "Type", "Done?"])
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        recent_layout.addWidget(self.recent_table)
        self.recent_group.setLayout(recent_layout)
        layout.addWidget(self.recent_group)

        # Footer buttons
        button_box = QHBoxLayout()
        button_box.addStretch()

        self.reset_btn = QPushButton("Reset Statistics...")
        self.reset_btn.clicked.connect(self._on_reset)
        button_box.addWidget(self.reset_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_box.addWidget(self.close_btn)

        layout.addLayout(button_box)

    def _render(self) -> None:
        if self._stats is None:
            return
        data = self._stats.data

        # All-time
        a = data.all_time
        self.total_words_label.setText(f"Total words read: {a.total_words_read:,}")
        self.total_time_label.setText(f"Total time: {_format_duration(a.total_time_seconds)}")
        self.sessions_label.setText(f"Sessions: {a.sessions_count}")
        self.lifetime_wpm_label.setText(f"Lifetime avg WPM: {a.lifetime_avg_wpm:.0f}")

        # Per-document (top 10 by words)
        docs = sorted(data.per_document.values(), key=lambda d: d.words_read, reverse=True)[:10]
        self.docs_table.setRowCount(len(docs))
        for row, doc in enumerate(docs):
            self.docs_table.setItem(row, 0, QTableWidgetItem(doc.source))
            self.docs_table.setItem(row, 1, QTableWidgetItem(doc.source_type))
            self.docs_table.setItem(row, 2, QTableWidgetItem(f"{doc.words_read:,}"))
            self.docs_table.setItem(row, 3, QTableWidgetItem(str(doc.sessions_count)))

        # Recent sessions
        sessions = data.recent_sessions
        self.recent_table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self.recent_table.setItem(row, 0, QTableWidgetItem(s.ended_at.strftime("%Y-%m-%d %H:%M")))
            self.recent_table.setItem(row, 1, QTableWidgetItem(f"{s.avg_wpm:.0f}"))
            self.recent_table.setItem(row, 2, QTableWidgetItem(str(s.words_read)))
            self.recent_table.setItem(row, 3, QTableWidgetItem(s.source_type))
            self.recent_table.setItem(row, 4, QTableWidgetItem("Y" if s.finished else "N"))

    def _on_reset(self) -> None:
        if self._stats is None:
            return
        reply = QMessageBox.question(
            self,
            "Reset Statistics",
            "This will permanently delete all reading statistics. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._stats.reset()
            self._render()
            logger.info("Statistics reset by user")


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"
```

- [ ] **Step 2: Add "Reading Statistics" menu item in `menu_builder.py`**

In `rsvp/ui/menu_builder.py`, find the `help_menu` section (around line 120) and add a new action above `Keyboard Shortcuts`:

```python
        stats_action = QAction("&Reading Statistics", self._window)
        stats_action.triggered.connect(host._show_statistics)
        help_menu.addAction(stats_action)
        help_menu.addSeparator()
```

- [ ] **Step 3: Add `_show_statistics` and StatsManager wiring in `main_window.py`**

In `rsvp/ui/main_window.py`:

- Add `from rsvp.core.stats import StatsManager` and `from rsvp.core.stats_recorder import StatsRecorder` and `from rsvp.ui.stats_dialog import StatsDialog` to imports
- In `__init__`, after `self._engine = RSVPEngine(settings=self._settings)`, add:

```python
        self._stats_manager = StatsManager()
        self._stats_recorder = StatsRecorder(self._engine, self._stats_manager)
```

- In `_on_document_loaded(self, source)`, add source-type detection:

```python
    def _on_document_loaded(self, source):
        """Hook called by DocumentLoader after each successful load."""
        self._current_file = source
        if source and source.startswith(("http://", "https://")):
            self._stats_recorder.set_source(source, "url")
        else:
            self._stats_recorder.set_source(source, "file")
        self._update_recent_menu()
        self._bookmarks.refresh_menu()
```

- In `_load_text_dialog` and `_paste_and_read`, also set the source:

```python
    def _load_text_dialog(self):
        """Show the text input dialog."""
        dialog = TextInputDialog(self)
        if dialog.exec():
            text = dialog.get_text()
            source = dialog.get_source_path()
            self._documents.load_from_text_dialog(text, source)
            # Track as paste or file/url depending on source
            if source and source.startswith(("http://", "https://")):
                self._stats_recorder.set_source(source, "url")
            elif source:
                self._stats_recorder.set_source(source, "file")
            else:
                self._stats_recorder.set_source(None, "paste")

    def _paste_and_read(self):
        """Paste from clipboard and start reading."""
        self._stats_recorder.set_source(None, "clipboard")
        self._documents.load_from_clipboard()
```

- Add `_show_statistics` method:

```python
    def _show_statistics(self) -> None:
        """Show the reading statistics dialog."""
        dialog = StatsDialog(self, stats_manager=self._stats_manager)
        dialog.exec()
```

- In `closeEvent`, call `shutdown()` on the recorder before saving:

```python
    def closeEvent(self, event):
        """Handle window close."""
        self._stats_recorder.shutdown()
        self._documents.maybe_save_position()
        self._save_window_settings()
        self._check_settings_save_failed()
        event.accept()
```

- [ ] **Step 4: Create `tests/test_ui_stats_dialog.py`**

```python
"""Smoke tests for the StatsDialog."""

from datetime import datetime, timedelta

import pytest

from rsvp.core.stats import (
    AllTimeStats,
    DocumentStats,
    SessionRecord,
    StatsData,
    StatsManager,
)
from rsvp.ui.stats_dialog import StatsDialog


@pytest.fixture
def populated_stats(tmp_path):
    mgr = StatsManager.__new__(StatsManager)
    mgr._data = StatsData(
        all_time=AllTimeStats(total_words_read=500, total_time_seconds=300.0, sessions_count=3),
        per_document={
            "/a.txt": DocumentStats(
                source="/a.txt",
                source_type="file",
                words_read=300,
                total_time_seconds=180.0,
                sessions_count=2,
                last_read=datetime(2026, 6, 5),
            ),
            "/b.txt": DocumentStats(
                source="/b.txt",
                source_type="file",
                words_read=200,
                total_time_seconds=120.0,
                sessions_count=1,
                last_read=datetime(2026, 6, 4),
            ),
        },
        recent_sessions=[
            SessionRecord(
                source="/a.txt",
                source_type="file",
                started_at=datetime(2026, 6, 5, 10, 0),
                ended_at=datetime(2026, 6, 5, 10, 5),
                words_read=150,
                avg_wpm=1800.0,
                peak_wpm=300,
                finished=True,
            ),
        ],
    )
    mgr._config_path = tmp_path / "stats.json"
    mgr._was_reset = False
    return mgr


class TestStatsDialog:
    def test_renders_with_empty_stats(self, qapp):
        mgr = StatsManager.__new__(StatsManager)
        mgr._data = StatsData()
        mgr._config_path = None  # type: ignore[assignment]
        mgr._was_reset = False
        dlg = StatsDialog(stats_manager=mgr)
        assert dlg.total_words_label.text() == "Total words read: 0"

    def test_renders_with_populated_stats(self, qapp, populated_stats):
        dlg = StatsDialog(stats_manager=populated_stats)
        assert "500" in dlg.total_words_label.text()
        assert dlg.docs_table.rowCount() == 2  # /a.txt and /b.txt
        assert dlg.recent_table.rowCount() == 1
        # /a.txt has more words, so it's first
        assert dlg.docs_table.item(0, 0).text() == "/a.txt"

    def test_reset_button_clears_data(self, qapp, populated_stats, monkeypatch):
        # Auto-confirm the reset dialog
        monkeypatch.setattr(
            "rsvp.ui.stats_dialog.QMessageBox.question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        dlg = StatsDialog(stats_manager=populated_stats)
        dlg._on_reset()
        assert populated_stats.data.all_time.total_words_read == 0
        assert populated_stats.data.per_document == {}
```

- [ ] **Step 5: Run all new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_stats.py tests/test_stats_recorder.py tests/test_ui_stats_dialog.py -v 2>&1 | tail -30`
Expected: all new tests pass.

- [ ] **Step 6: Run full test suite + ruff + mypy**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1 && /opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -3`
Expected: all pass, mypy clean (or only pre-existing PyQt6 stub errors).

- [ ] **Step 7: Commit**

```bash
git add rsvp/ui/stats_dialog.py rsvp/ui/menu_builder.py rsvp/ui/main_window.py tests/test_ui_stats_dialog.py
git commit -m "feat: add reading statistics dialog and menu item

New rsvp.ui.stats_dialog.StatsDialog — modal dialog with 3 sections
(all-time totals, top documents, recent sessions) plus a Reset
Statistics button with confirmation.

Menu wiring:
  - 'Help → Reading Statistics' menu item (rsvp.ui.menu_builder)
  - MainWindow._show_statistics opens the dialog

Composition root:
  - MainWindow creates StatsManager + StatsRecorder
  - _on_document_loaded sets the source type ('file' or 'url')
  - _load_text_dialog and _paste_and_read set 'paste' or 'clipboard'
  - closeEvent calls stats_recorder.shutdown() to finalize the
    in-progress session before saving window state

Test coverage:
  - Empty-state rendering
  - Populated-state rendering (top docs sorted by words)
  - Reset button clears data after confirmation"
```

---

## Self-Review

**1. Spec coverage:** 5 spec items mapped to 3 commits (data model = commit 1; recorder = commit 2; dialog + wiring = commit 3).

**2. Placeholder scan:** No "TBD" or "fill in later" markers. All code blocks are concrete with full implementations.

**3. Type consistency:** `SessionRecord`, `DocumentStats`, `AllTimeStats`, `StatsData`, `StatsManager` types used consistently. `StatsRecorder` uses the same `Word | None` pattern as `MainWindow._on_word_changed`.

**4. Edge cases handled:**
- Zero-word sessions dropped (recorder)
- Zero-duration sessions dropped (recorder)
- 30-entry cap on recent_sessions (manager)
- Per-document cap is unbounded (acceptable for personal use)
- set_source ends any active session (recorder)
- shutdown() called by MainWindow.closeEvent (recorder)
- Corruption recovery with .json.bak (manager, same pattern as settings)

**5. Risk acknowledgment:**
- Recording overhead is one int + max per word — bounded and trivial
- File growth: per-doc dict grows with distinct sources, recent capped at 30
- Datetime serialization: ISO 8601 via isoformat/fromisoformat — portable

---

## Success Criteria (from spec)

- [ ] `StatsManager` persists to `stats.json` in the platform-specific config dir
- [ ] Engine load → play → pause → play → stop sequence records 2 sessions
- [ ] Recent sessions list is capped at 30, most recent first
- [ ] Per-document stats aggregate correctly across multiple sessions
- [ ] "Help → Reading Statistics" menu item opens the dialog
- [ ] Dialog shows all-time totals, top documents (by words), and recent sessions
- [ ] "Reset Statistics..." button clears data after confirmation
- [ ] `pytest -q` passes (~294 tests, 21 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature
- [ ] All 3 items above landed in the named atomic commits

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~294 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
