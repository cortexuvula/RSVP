"""Tests for DocumentLoader."""

import os
from unittest.mock import MagicMock, patch

import pytest

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.text_processor import load_text_from_file
from rsvp.ui.document_loader import DocumentLoader


@pytest.fixture
def loader_components(qapp):
    """Create a DocumentLoader with mock dependencies."""
    engine = RSVPEngine()
    parent = MagicMock()
    status_setter = MagicMock()
    title_setter = MagicMock()
    on_loaded = MagicMock()
    current_file_getter = MagicMock(return_value=None)
    settings = MagicMock()
    # Configure settings mock so _maybe_resume_position doesn't fail
    settings.settings.auto_save_position = False
    settings.get_position.return_value = None

    loader = DocumentLoader(
        parent_widget=parent,
        engine=engine,
        status_setter=status_setter,
        title_setter=title_setter,
        on_loaded=on_loaded,
        current_file_getter=current_file_getter,
        settings=settings,
    )
    return loader, engine, status_setter, title_setter, on_loaded, current_file_getter, settings


class TestLoadTextFromFile:
    """Tests for load_text_from_file using test fixtures."""

    def test_load_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Plain text content", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert result == "Plain text content"

    def test_load_md(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Header\n\n**bold** text.", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Header" in result
        assert "bold" in result
        assert "**" not in result
        assert "#" not in result

    def test_load_html(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html><body><p>Hello world</p></body></html>", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Hello world" in result
        assert "<p>" not in result

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_text_from_file("/nonexistent/path/file.txt")

    def test_load_fixture_txt(self):
        """Load the test fixtures if they exist."""
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        # test.md fixture
        md_path = os.path.join(fixtures_dir, "test.md")
        if os.path.exists(md_path):
            result = load_text_from_file(md_path)
            assert len(result) > 0
            # Markdown syntax should be stripped
            assert "**" not in result

    def test_load_fixture_html(self):
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        html_path = os.path.join(fixtures_dir, "test.html")
        if os.path.exists(html_path):
            result = load_text_from_file(html_path)
            assert len(result) > 0
            # HTML tags should be stripped; HTML entities like &lt; are decoded to characters
            assert "<h1>" not in result
            assert "<p>" not in result
            assert "<script>" not in result


class TestDocumentLoader:
    """Tests for the DocumentLoader coordination class."""

    def test_load_file_success(self, loader_components, tmp_path):
        loader, engine, status_setter, title_setter, on_loaded, _, settings = loader_components
        f = tmp_path / "test.txt"
        f.write_text("Hello world from file", encoding="utf-8")
        result = loader.load_file(str(f))
        assert result is True
        assert engine.word_count > 0
        title_setter.assert_called_once()
        on_loaded.assert_called_once_with(str(f))
        settings.add_recent_file.assert_called_once_with(str(f))

    @patch("rsvp.ui.document_loader.QMessageBox")
    def test_load_file_nonexistent(self, mock_msgbox, loader_components):
        loader, engine, _, _, _, _, _ = loader_components
        result = loader.load_file("/nonexistent/file.txt")
        assert result is False
        mock_msgbox.warning.assert_called_once()

    def test_load_from_text_dialog(self, loader_components):
        loader, engine, status_setter, title_setter, on_loaded, _, settings = loader_components
        loader.load_from_text_dialog("Some text to read", "source_id")
        assert engine.word_count > 0
        title_setter.assert_called_once()
        on_loaded.assert_called_once_with("source_id")
        settings.add_recent_file.assert_called_once_with("source_id")

    def test_load_from_text_dialog_no_source(self, loader_components):
        loader, engine, _, title_setter, on_loaded, _, settings = loader_components
        loader.load_from_text_dialog("Some text", None)
        assert engine.word_count > 0
        # Title should be plain "RSVP Reader" without a source
        title_setter.assert_called_once_with("RSVP Reader")
        on_loaded.assert_called_once_with(None)
        settings.add_recent_file.assert_not_called()

    @patch("rsvp.ui.document_loader.QFileDialog")
    def test_open_file_dialog_cancel(self, mock_file_dialog, loader_components):
        mock_file_dialog.getOpenFileName.return_value = ("", "")
        loader, *_ = loader_components
        result = loader.open_file_dialog()
        assert result is None


class TestLoadTextFromURL:
    """Tests for fetch_text_from_url with mocked requests."""

    @patch("rsvp.core.text_processor.socket.getaddrinfo")
    @patch("requests.get")
    def test_fetch_valid_url(self, mock_get, mock_getaddrinfo):
        from rsvp.core.text_processor import fetch_text_from_url

        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
        ]
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello world</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_text_from_url("https://example.com/article")
        assert "Hello world" in result
        mock_get.assert_called_once()

    def test_fetch_empty_url(self):
        from rsvp.core.text_processor import fetch_text_from_url

        with pytest.raises(ValueError, match="empty"):
            fetch_text_from_url("")

    def test_fetch_invalid_scheme(self):
        from rsvp.core.text_processor import fetch_text_from_url

        with pytest.raises(ValueError, match="supported"):
            fetch_text_from_url("ftp://example.com/file")

    def test_fetch_no_host(self):
        from rsvp.core.text_processor import fetch_text_from_url

        with pytest.raises(ValueError, match="host"):
            fetch_text_from_url("https://")

    @patch("rsvp.core.text_processor.socket.getaddrinfo")
    def test_fetch_ssrf_private_ip_blocked(self, mock_getaddrinfo):
        from rsvp.core.text_processor import fetch_text_from_url

        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        with pytest.raises(ValueError, match="private"):
            fetch_text_from_url("https://localhost/secret")
