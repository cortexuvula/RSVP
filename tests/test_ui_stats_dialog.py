"""Smoke tests for the StatsDialog."""

from datetime import datetime

import pytest
from PyQt6.QtWidgets import QMessageBox

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
        # The session row should show its data
        assert "Y" in dlg.recent_table.item(0, 4).text()  # finished=Y

    def test_reset_button_clears_data(self, qapp, populated_stats, monkeypatch):
        # Auto-confirm the reset dialog
        from rsvp.ui import stats_dialog

        monkeypatch.setattr(
            stats_dialog.QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        dlg = StatsDialog(stats_manager=populated_stats)
        dlg._on_reset()
        assert populated_stats.data.all_time.total_words_read == 0
        assert populated_stats.data.per_document == {}
        assert populated_stats.data.recent_sessions == []

    def test_reset_canceled_preserves_data(self, qapp, populated_stats, monkeypatch):
        from rsvp.ui import stats_dialog

        monkeypatch.setattr(
            stats_dialog.QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )
        dlg = StatsDialog(stats_manager=populated_stats)
        dlg._on_reset()
        # Data preserved
        assert populated_stats.data.all_time.total_words_read == 500

    def test_no_manager_does_not_crash(self, qapp):
        dlg = StatsDialog(stats_manager=None)
        # Labels show the em-dash placeholders
        assert dlg.total_words_label.text() == "Total words read: —"
        assert dlg.docs_table.rowCount() == 0
        assert dlg.recent_table.rowCount() == 0
