"""Tests for TextInputDialog."""

import pytest

from rsvp.ui.text_input_dialog import TextInputDialog


@pytest.fixture
def dialog(qapp):
    """Create a TextInputDialog for testing."""
    return TextInputDialog()


class TestTextInputDialogInit:
    """Tests for dialog initialization."""

    def test_dialog_has_title(self, dialog):
        assert dialog.windowTitle() == "Load Text"

    def test_dialog_has_tabs(self, dialog):
        assert hasattr(dialog, "tabs")
        assert dialog.tabs.count() == 3

    def test_tab_names(self, dialog):
        assert dialog.tabs.tabText(0) == "Paste Text"
        assert dialog.tabs.tabText(1) == "Open File"
        assert dialog.tabs.tabText(2) == "From URL"

    def test_initial_text_is_empty(self, dialog):
        assert dialog.get_text() == ""

    def test_initial_source_path_is_none(self, dialog):
        assert dialog.get_source_path() is None

    def test_has_text_edit(self, dialog):
        assert hasattr(dialog, "text_edit")

    def test_has_url_edit(self, dialog):
        assert hasattr(dialog, "url_edit")

    def test_has_file_path_edit(self, dialog):
        assert hasattr(dialog, "file_path_edit")


class TestTabSwitching:
    """Tests for tab switching."""

    def test_default_tab_is_paste(self, dialog):
        assert dialog.tabs.currentIndex() == 0

    def test_switch_to_file_tab(self, dialog):
        dialog.tabs.setCurrentIndex(1)
        assert dialog.tabs.currentIndex() == 1

    def test_switch_to_url_tab(self, dialog):
        dialog.tabs.setCurrentIndex(2)
        assert dialog.tabs.currentIndex() == 2

    def test_switch_back_to_paste(self, dialog):
        dialog.tabs.setCurrentIndex(2)
        dialog.tabs.setCurrentIndex(0)
        assert dialog.tabs.currentIndex() == 0


class TestURLValidation:
    """Tests for URL input handling."""

    def test_empty_url_does_nothing(self, dialog):
        """Fetching with an empty URL field should not crash."""
        dialog.url_edit.setText("")
        dialog._fetch_url()
        assert dialog.url_preview.toPlainText() == ""

    def test_url_edit_placeholder(self, dialog):
        assert dialog.url_edit.placeholderText() == "https://example.com/article"

    def test_url_preview_is_read_only(self, dialog):
        assert dialog.url_preview.isReadOnly()


class TestConcurrentFetchGuard:
    """Tests for the guard against concurrent fetches (S4)."""

    def test_fetch_url_early_returns_when_thread_active(self, dialog):
        """If _fetch_thread is already set, _fetch_url should return early."""
        from PyQt6.QtCore import QThread

        dialog.url_edit.setText("https://example.com")
        # Simulate an in-progress fetch by setting the thread reference
        dialog._fetch_thread = QThread()
        # Should not start a new fetch (early return)
        dialog._fetch_url()
        # The worker should still be None since no new fetch was started
        assert dialog._fetch_worker is None
        # Clean up the dummy thread
        dialog._fetch_thread = None
