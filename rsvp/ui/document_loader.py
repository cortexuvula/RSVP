"""Document loading flow for MainWindow.

Centralizes the cross-cutting work that happens whenever a new document
is loaded into the engine: position save/restore, recent-files tracking,
window title, status bar message, and clipboard ingestion.
"""

import logging
from collections.abc import Callable

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import get_settings_manager
from rsvp.core.text_processor import load_text_from_file

logger = logging.getLogger(__name__)

FILE_DIALOG_FILTER = (
    "All Supported (*.txt *.md *.html *.htm *.epub *.pdf);;"
    "Text (*.txt);;"
    "Markdown (*.md);;"
    "HTML (*.html *.htm);;"
    "EPUB (*.epub);;"
    "PDF (*.pdf);;"
    "All Files (*)"
)


class DocumentLoader:
    """Coordinates the steps that happen when a document is loaded."""

    def __init__(
        self,
        parent_widget: QWidget,
        engine: RSVPEngine,
        status_setter: Callable[[str], None],
        title_setter: Callable[[str], None],
        on_loaded: Callable[[str | None], None],
        current_file_getter: Callable[[], str | None],
    ):
        self._parent = parent_widget
        self._engine = engine
        self._set_status = status_setter
        self._set_title = title_setter
        self._on_loaded = on_loaded
        self._get_current_file = current_file_getter

    def open_file_dialog(self) -> str | None:
        """Show the open-file dialog and load the chosen file. Returns the path or None."""
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Open File",
            "",
            FILE_DIALOG_FILTER,
        )
        if not filepath:
            return None
        self.load_file(filepath)
        return filepath

    def load_file(self, filepath: str) -> bool:
        """Load a file by path. Returns True on success."""
        self._maybe_save_position()
        try:
            text = load_text_from_file(filepath)
        except Exception as e:
            QMessageBox.warning(self._parent, "Error", f"Failed to load file: {e}")
            return False

        self._engine.load_text(text)
        get_settings_manager().add_recent_file(filepath)
        self._set_title(f"RSVP Reader - {filepath}")
        self._set_status(f"Loaded {self._engine.word_count} words")
        logger.info("Loaded file %s (%d words)", filepath, self._engine.word_count)
        self._on_loaded(filepath)
        self._maybe_resume_position(filepath)
        return True

    def load_from_text_dialog(self, text: str, source: str | None) -> None:
        """Load text supplied by TextInputDialog (paste/file/url)."""
        self._maybe_save_position()
        self._engine.load_text(text)

        if source:
            get_settings_manager().add_recent_file(source)
            self._set_title(f"RSVP Reader - {source}")
        else:
            self._set_title("RSVP Reader")

        self._set_status(f"Loaded {self._engine.word_count} words")
        self._on_loaded(source)
        self._maybe_resume_position(source)

    def load_from_clipboard(self) -> None:
        """Read clipboard contents and start reading immediately."""
        text = self._read_clipboard()
        if not text:
            return

        self._engine.load_text(text)
        self._set_title("RSVP Reader - Clipboard")
        self._set_status(f"Loaded {self._engine.word_count} words from clipboard")
        logger.info("Loaded clipboard text (%d words)", self._engine.word_count)
        self._on_loaded(None)
        self._engine.play()

    @staticmethod
    def _read_clipboard() -> str:
        try:
            import pyperclip

            text: str = pyperclip.paste()
            if text:
                return text
        except Exception:
            pass
        from PyQt6.QtWidgets import QApplication

        return QApplication.clipboard().text()

    def maybe_save_position(self) -> None:
        """Public helper so MainWindow can save on close."""
        self._maybe_save_position()

    def _maybe_save_position(self) -> None:
        manager = get_settings_manager()
        if not manager.settings.auto_save_position:
            return
        current_file = self._get_current_file()
        if current_file and self._engine.current_index > 0:
            manager.save_position(current_file, self._engine.current_index)

    def _maybe_resume_position(self, source: str | None) -> None:
        if not source:
            return
        manager = get_settings_manager()
        if not manager.settings.auto_save_position:
            return

        saved_index = manager.get_position(source)
        if saved_index is None or saved_index <= 0:
            return
        if saved_index >= self._engine.word_count:
            return

        reply = QMessageBox.question(
            self._parent,
            "Resume Reading",
            f"Resume from word {saved_index} of {self._engine.word_count}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.seek(saved_index)
