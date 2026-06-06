"""Modal Reading Statistics dialog."""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
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
