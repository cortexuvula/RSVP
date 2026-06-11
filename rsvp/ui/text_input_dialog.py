"""Dialog for text input."""

import logging

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rsvp.core.constants import FILE_DIALOG_FILTER, PREVIEW_MAX_CHARS
from rsvp.core.text_processor import fetch_text_from_url, load_text_from_file

logger = logging.getLogger(__name__)


class _FetchWorker(QObject):
    """Worker that fetches URL text on a background thread."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url

    @pyqtSlot()
    def run(self) -> None:
        """Fetch text from the URL. Runs in the worker thread."""
        try:
            text = fetch_text_from_url(self._url)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class TextInputDialog(QDialog):
    """Dialog for inputting text via paste, file, or URL."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load Text")
        self.setMinimumSize(600, 400)
        self._text: str = ""
        self._source_path: str | None = None
        self._url_text_truncated: bool = False
        self._fetch_thread: QThread | None = None
        self._fetch_worker: _FetchWorker | None = None
        self._fetched_full_text: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()

        # Paste tab
        paste_tab = QWidget()
        paste_layout = QVBoxLayout(paste_tab)
        paste_layout.addWidget(QLabel("Paste or type text below:"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste your text here...")
        paste_layout.addWidget(self.text_edit)

        # Paste from clipboard button
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        paste_layout.addWidget(paste_btn)

        tabs.addTab(paste_tab, "Paste Text")

        # File tab
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        file_layout.addWidget(QLabel("Select a text file:"))

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("No file selected")
        self.file_path_edit.setReadOnly(True)
        file_row.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)

        file_layout.addLayout(file_row)

        # File preview
        file_layout.addWidget(QLabel("Preview:"))
        self.file_preview = QTextEdit()
        self.file_preview.setReadOnly(True)
        file_layout.addWidget(self.file_preview)

        tabs.addTab(file_tab, "Open File")

        # URL tab
        url_tab = QWidget()
        url_layout = QVBoxLayout(url_tab)
        url_layout.addWidget(QLabel("Enter URL:"))

        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com/article")
        url_row.addWidget(self.url_edit)

        fetch_btn = QPushButton("Fetch")
        fetch_btn.clicked.connect(self._fetch_url)
        url_row.addWidget(fetch_btn)

        url_layout.addLayout(url_row)

        # URL preview
        url_layout.addWidget(QLabel("Preview:"))
        self.url_preview = QTextEdit()
        self.url_preview.setReadOnly(True)
        url_layout.addWidget(self.url_preview)

        tabs.addTab(url_tab, "From URL")

        layout.addWidget(tabs)

        # Store tab widget reference
        self.tabs = tabs

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._accept)
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _paste_from_clipboard(self) -> None:
        """Paste text from clipboard."""
        try:
            import pyperclip

            text = pyperclip.paste()
            if text:
                self.text_edit.setPlainText(text)
                logger.debug("Pasted %d chars from clipboard via pyperclip", len(text))
        except (ImportError, OSError) as e:
            # pyperclip may be missing, or the system clipboard helper (xclip/xsel)
            # is unavailable on Linux. Fall back to Qt's clipboard.
            logger.debug("pyperclip unavailable, falling back to Qt clipboard: %s", e)
            from PyQt6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            self.text_edit.setPlainText(clipboard.text())

    def _browse_file(self) -> None:
        """Open file browser."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            FILE_DIALOG_FILTER,
        )

        if filepath:
            try:
                text = load_text_from_file(filepath)
                self.file_path_edit.setText(filepath)
                truncated = len(text) > PREVIEW_MAX_CHARS
                self.file_preview.setPlainText(text[:PREVIEW_MAX_CHARS] + ("..." if truncated else ""))
                self._source_path = filepath
            except (OSError, ValueError) as e:
                logger.exception("Failed to load file: %s", filepath)
                QMessageBox.warning(self, "Error", f"Failed to load file: {e}")

    def _fetch_url(self) -> None:
        """Fetch text from URL."""
        url = self.url_edit.text().strip()
        if not url:
            return
        # Guard against concurrent fetches (e.g. keyboard shortcut while
        # a background fetch is already in progress).
        if self._fetch_thread is not None:
            return

        # Disable the fetch button while working
        self._set_fetch_enabled(False)

        self._fetch_thread = QThread()
        self._fetch_worker = _FetchWorker(url)
        self._fetch_worker.moveToThread(self._fetch_thread)
        self._fetch_worker.finished.connect(self._on_fetch_finished)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_thread.finished.connect(self._cleanup_fetch_thread)
        self._fetch_thread.start()

    def _set_fetch_enabled(self, enabled: bool) -> None:
        """Enable or disable fetch-related UI controls."""
        # Find the Fetch button in the URL tab
        for btn in self.url_edit.parentWidget().findChildren(QPushButton):
            if btn.text() == "Fetch":
                btn.setEnabled(enabled)
                break

    @pyqtSlot(str)
    def _on_fetch_finished(self, text: str) -> None:
        """Handle successful URL fetch."""
        self._fetched_full_text = text
        self._url_text_truncated = len(text) > PREVIEW_MAX_CHARS
        self.url_preview.setPlainText(text[:PREVIEW_MAX_CHARS] + ("..." if self._url_text_truncated else ""))
        url = self.url_edit.text().strip()
        self._source_path = url
        logger.info("Fetched URL %s (%d chars)", url, len(text))
        self._set_fetch_enabled(True)
        self._cleanup_fetch_thread()

    @pyqtSlot(str)
    def _on_fetch_error(self, error_msg: str) -> None:
        """Handle URL fetch error."""
        url = self.url_edit.text().strip()
        logger.error("Failed to fetch URL: %s — %s", url, error_msg)
        QMessageBox.warning(self, "Error", f"Failed to fetch URL: {error_msg}")
        self._set_fetch_enabled(True)
        self._cleanup_fetch_thread()

    def _cleanup_fetch_thread(self) -> None:
        """Tear down the fetch worker thread."""
        if self._fetch_thread is not None:
            self._fetch_thread.quit()
            self._fetch_thread.wait()
            self._fetch_thread = None
            self._fetch_worker = None

    def _accept(self) -> None:
        """Accept the dialog and set the text."""
        current_tab = self.tabs.currentIndex()

        if current_tab == 0:  # Paste
            self._text = self.text_edit.toPlainText()
            self._source_path = None
        elif current_tab == 1:  # File
            if self.file_path_edit.text():
                try:
                    self._text = load_text_from_file(self.file_path_edit.text())
                except (OSError, ValueError) as e:
                    logger.exception("Failed to load file: %s", self.file_path_edit.text())
                    QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
                    return
            else:
                self._text = ""
        else:  # URL
            if self._url_text_truncated:
                # Use the cached full text from the background fetch
                if self._fetched_full_text is not None:
                    self._text = self._fetched_full_text
                else:
                    # Fallback: re-fetch synchronously (should not normally happen)
                    try:
                        self._text = fetch_text_from_url(self.url_edit.text().strip())
                    except (OSError, ValueError) as e:
                        logger.exception("Failed to fetch URL: %s", self.url_edit.text().strip())
                        QMessageBox.warning(self, "Error", f"Failed to fetch URL: {e}")
                        return
            else:
                self._text = self.url_preview.toPlainText()

        if self._text.strip():
            self.accept()
        else:
            QMessageBox.warning(self, "No Text", "Please enter or load some text.")

    def get_text(self) -> str:
        """Get the loaded text."""
        return self._text

    def get_source_path(self) -> str | None:
        """Get the source file path or URL."""
        return self._source_path
