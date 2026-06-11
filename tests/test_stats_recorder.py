"""Tests for StatsRecorder — engine signal integration."""

from datetime import datetime, timedelta

import pytest

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.stats import StatsData, StatsManager
from rsvp.core.stats_recorder import StatsRecorder
from rsvp.core.text_processor import Word


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


def _simulate_reading_session(engine, recorder, word_count, duration_s=60.0):
    """Drive the recorder through a real play→words→pause cycle.

    Loads text, sets source, calls play() (emits state_changed → recorder
    starts session), emits N word_changed signals, backdates the session
    start so the duration guard in _end_session passes, then calls pause()
    (emits state_changed → recorder ends session).
    """
    engine.load_text("one two three four five six seven eight nine ten")
    recorder.set_source("/a.txt", "file")
    engine.play()
    for i in range(word_count):
        engine.word_changed.emit(Word(text=f"w{i}", orp_index=0, pause_after=1.0))
    # Backdate the start so duration > 0 (avoids the zero-duration guard)
    recorder._session_start = datetime.now() - timedelta(seconds=duration_s)
    engine.pause()


class TestSessionLifecycle:
    def test_session_dropped_when_zero_words(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("/a.txt", "file")
        engine.play()  # begin session
        # No word_changed emissions
        engine.pause()  # end session with zero words
        assert stats_manager.data.all_time.sessions_count == 0
        assert stats_manager.data.recent_sessions == []

    def test_session_recorded_after_consuming_words(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        _simulate_reading_session(engine, recorder, word_count=5)
        assert stats_manager.data.all_time.sessions_count == 1
        assert stats_manager.data.all_time.total_words_read == 5
        assert "/a.txt" in stats_manager.data.per_document

    def test_set_source_ends_active_session(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        # Backdate the active session's start time so the duration guard
        # in _end_session passes (sessions in tests are microseconds by
        # default and would be dropped)
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        # Loading a new document + set_source ends the previous session
        engine.load_text("six seven eight")
        recorder.set_source("/b.txt", "file")
        assert stats_manager.data.all_time.sessions_count == 1
        assert stats_manager.data.recent_sessions[0].source == "/a.txt"
        # The new source takes effect for the next session
        assert recorder._current_source == "/b.txt"

    def test_shutdown_ends_active_session(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        recorder.shutdown()
        assert stats_manager.data.all_time.sessions_count == 1

    def test_repeated_sessions_accumulate(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        for _ in range(3):
            engine.play()
            for i in range(5):
                engine.word_changed.emit(Word(text=f"w{i}", orp_index=0, pause_after=1.0))
            recorder._session_start = datetime.now() - timedelta(seconds=30)
            engine.pause()
        assert stats_manager.data.all_time.sessions_count == 3
        assert stats_manager.data.all_time.total_words_read == 15


class TestSessionAttributes:
    def test_finished_marked(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine._state.wpm = 300
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        # Engine emits 'finished' before we end
        engine.finished.emit()
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        # The recorder's _on_finished already called _end_session
        # (which dropped the session due to zero duration from microsecond timestamps)
        # so re-run with a backdated start time
        engine.load_text("four five six")
        recorder._begin_session()
        engine.word_changed.emit(Word(text="w1", orp_index=0, pause_after=1.0))
        recorder._session_finished = True
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        recorder._end_session()
        assert stats_manager.data.recent_sessions[0].finished is True

    def test_peak_wpm_tracked(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine._state.wpm = 500
        engine.play()
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        engine.pause()
        assert stats_manager.data.recent_sessions[0].peak_wpm == 500

    def test_source_type_propagated(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("https://example.com", "url")
        engine.play()
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        engine.pause()
        doc = stats_manager.data.per_document["https://example.com"]
        assert doc.source_type == "url"

    def test_anonymous_source(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source(None, "clipboard")
        engine.play()
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        engine.pause()
        # All-time total still updated
        assert stats_manager.data.all_time.sessions_count == 1
        # But no per-document entry
        assert stats_manager.data.per_document == {}


class TestSignalWiring:
    """Verify the recorder subscribes to the right engine signals."""

    def test_recorder_subscribes_to_word_changed(self, engine_and_recorder):
        engine, recorder, _ = engine_and_recorder
        engine.load_text("one two")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine._state.wpm = 300
        # Emit via the actual signal — proves the recorder is connected
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        assert recorder._words_in_session == 1

    def test_recorder_subscribes_to_finished(self, engine_and_recorder):
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three")
        recorder.set_source("/a.txt", "file")
        engine.play()
        engine._state.wpm = 300
        engine.word_changed.emit(Word(text="w0", orp_index=0, pause_after=1.0))
        # Emit finished via the actual signal
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        engine.finished.emit()
        assert stats_manager.data.recent_sessions[0].finished is True


class TestFinishedFlagOnLastWord:
    """Verify that sessions ending by reaching the last word are marked finished.

    Simulates the real _advance() behaviour: pause() fires before
    finished.emit() due to synchronous same-thread signal delivery.
    """

    def test_pause_then_finished_marks_session_finished(self, engine_and_recorder):
        """Replicate the exact signal order from RSVPEngine._advance()."""
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine._state.wpm = 300
        engine.play()
        # Simulate reading several words
        for i in range(5):
            engine.word_changed.emit(Word(text=f"w{i}", orp_index=0, pause_after=1.0))
        # Backdate session start so the duration guard passes
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        # Replicate _advance()'s signal order: pause() then finished.emit()
        engine.pause()  # → state_changed → _on_state_changed → _end_session (finished=False)
        engine.finished.emit()  # → _on_finished → patches finished=True
        assert stats_manager.data.all_time.sessions_count == 1
        assert stats_manager.data.recent_sessions[0].finished is True

    def test_user_pause_not_marked_finished(self, engine_and_recorder):
        """A manual pause (no finished signal) should leave finished=False."""
        engine, recorder, stats_manager = engine_and_recorder
        engine.load_text("one two three four five")
        recorder.set_source("/a.txt", "file")
        engine._state.wpm = 300
        engine.play()
        for i in range(3):
            engine.word_changed.emit(Word(text=f"w{i}", orp_index=0, pause_after=1.0))
        recorder._session_start = datetime.now() - timedelta(seconds=30)
        engine.pause()  # user pauses mid-read, no finished signal
        assert stats_manager.data.all_time.sessions_count == 1
        assert stats_manager.data.recent_sessions[0].finished is False
