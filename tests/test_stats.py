"""Tests for the stats module."""

from datetime import datetime, timedelta

import pytest

from rsvp.core.stats import (
    AllTimeStats,
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
        stats_manager.record_session(_make_record(source="/tmp/x.txt"))
        # Manually clear the source to simulate an anonymous record
        rec = stats_manager.data.recent_sessions[0]
        rec.source = None
        stats_manager.reset()
        stats_manager.record_session(rec)
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
