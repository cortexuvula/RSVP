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
        # When the engine reaches the last word, pause() fires before
        # finished.emit() due to synchronous same-thread signal delivery.
        # The _end_session() call above is therefore a no-op (session was
        # already ended by _on_state_changed with finished=False).  Patch
        # the most recent record to mark it as finished.
        if self._stats.data.recent_sessions:
            self._stats.data.recent_sessions[0].finished = True

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
