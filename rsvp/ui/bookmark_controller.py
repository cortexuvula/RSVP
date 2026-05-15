"""Bookmark management for MainWindow."""

from collections.abc import Callable

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QMessageBox, QWidget

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import get_settings_manager


class BookmarkController:
    """Encapsulates bookmark add/remove and Go-to-Bookmark menu population."""

    def __init__(
        self,
        parent_widget: QWidget,
        engine: RSVPEngine,
        submenu: QMenu,
        status_setter: Callable[[str], None],
        current_file_getter: Callable[[], str | None],
    ):
        self._parent = parent_widget
        self._engine = engine
        self._submenu = submenu
        self._set_status = status_setter
        self._get_current_file = current_file_getter

    def add(self) -> None:
        """Add a bookmark at the engine's current position."""
        current_file = self._get_current_file()
        if not current_file:
            QMessageBox.information(
                self._parent,
                "Bookmark",
                "Bookmarks are only available for files.",
            )
            return

        get_settings_manager().add_bookmark(current_file, self._engine.current_index)
        self.refresh_menu()
        self._set_status(f"Bookmark added at word {self._engine.current_index}")

    def remove(self) -> None:
        """Remove the bookmark at the engine's current position, if any."""
        current_file = self._get_current_file()
        if not current_file:
            return

        bookmarks = get_settings_manager().get_bookmarks(current_file)
        if not bookmarks:
            self._set_status("No bookmarks to remove")
            return

        current = self._engine.current_index
        if current in bookmarks:
            get_settings_manager().remove_bookmark(current_file, current)
            self.refresh_menu()
            self._set_status(f"Bookmark removed at word {current}")
        else:
            self._set_status("No bookmark at current position")

    def refresh_menu(self) -> None:
        """Repopulate the Go-to-Bookmark submenu from the current file's bookmarks."""
        self._submenu.clear()
        current_file = self._get_current_file()

        if not current_file:
            self._add_placeholder("No bookmarks")
            return

        bookmarks = get_settings_manager().get_bookmarks(current_file)
        if not bookmarks:
            self._add_placeholder("No bookmarks")
            return

        words = self._engine.state.words
        for idx in bookmarks:
            if idx < len(words):
                label = f'Word {idx}: "{words[idx].text}"'
            else:
                label = f"Word {idx}"
            action = QAction(label, self._parent)
            action.triggered.connect(lambda checked, i=idx: self._engine.seek(i))
            self._submenu.addAction(action)

    def _add_placeholder(self, text: str) -> None:
        action = QAction(text, self._parent)
        action.setEnabled(False)
        self._submenu.addAction(action)
