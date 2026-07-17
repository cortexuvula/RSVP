"""Menu construction for MainWindow."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QMenu

from rsvp.core.rsvp_engine import RSVPEngine


@runtime_checkable
class MenuHost(Protocol):
    """Interface that MenuBuilder expects from its host object."""

    @property
    def engine(self) -> RSVPEngine: ...

    def _load_text_dialog(self) -> None: ...
    def _open_file(self) -> None: ...
    def _paste_and_read(self) -> None: ...
    def _show_settings(self) -> None: ...
    def _toggle_always_on_top(self, checked: bool) -> None: ...
    def _toggle_fullscreen(self) -> None: ...
    def _speed_up(self) -> None: ...
    def _speed_down(self) -> None: ...
    def _add_bookmark(self) -> None: ...
    def _remove_bookmark(self) -> None: ...
    def _show_statistics(self) -> None: ...
    def _show_shortcuts(self) -> None: ...
    def _show_about(self) -> None: ...


@dataclass
class MenuRefs:
    """References to menu elements that MainWindow needs to mutate at runtime."""

    recent_menu: QMenu
    bookmarks_submenu: QMenu
    always_on_top_action: QAction


class MenuBuilder:
    """Builds the application menu bar for MainWindow.

    The host is expected to expose the action handler methods used below
    (e.g. ``_load_text_dialog``, ``_add_bookmark``).
    """

    def __init__(self, window: QMainWindow, host: MenuHost) -> None:
        self._window = window
        self._host = host

    def build(self) -> MenuRefs:
        menubar = self._window.menuBar()
        host = self._host

        file_menu = menubar.addMenu("&File")

        load_action = QAction("&Load Text...", self._window)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(host._load_text_dialog)
        file_menu.addAction(load_action)

        open_action = QAction("&Open File...", self._window)
        open_action.setShortcut("Ctrl+Shift+O")
        open_action.triggered.connect(host._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        recent_menu = file_menu.addMenu("Recent Files")

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self._window)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self._window.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("&Edit")

        paste_action = QAction("&Paste and Read", self._window)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(host._paste_and_read)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        settings_action = QAction("&Settings...", self._window)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(host._show_settings)
        edit_menu.addAction(settings_action)

        view_menu = menubar.addMenu("&View")

        always_on_top_action = QAction("Always on &Top", self._window)
        always_on_top_action.setCheckable(True)
        always_on_top_action.triggered.connect(host._toggle_always_on_top)
        view_menu.addAction(always_on_top_action)

        fullscreen_action = QAction("&Fullscreen", self._window)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(host._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        playback_menu = menubar.addMenu("&Playback")

        play_action = QAction("&Play/Pause", self._window)
        play_action.setShortcut("Space")
        play_action.triggered.connect(host.engine.toggle_play_pause)
        playback_menu.addAction(play_action)

        stop_action = QAction("&Stop", self._window)
        stop_action.setShortcut("S")
        stop_action.triggered.connect(host.engine.stop)
        playback_menu.addAction(stop_action)

        playback_menu.addSeparator()

        speed_up_action = QAction("Speed &Up (+/Up)", self._window)
        speed_up_action.triggered.connect(host._speed_up)
        playback_menu.addAction(speed_up_action)

        speed_down_action = QAction("Speed &Down (-/Down)", self._window)
        speed_down_action.triggered.connect(host._speed_down)
        playback_menu.addAction(speed_down_action)

        bookmarks_menu = menubar.addMenu("&Bookmarks")

        add_bookmark_action = QAction("&Add Bookmark", self._window)
        add_bookmark_action.setShortcut("Ctrl+B")
        add_bookmark_action.triggered.connect(host._add_bookmark)
        bookmarks_menu.addAction(add_bookmark_action)

        remove_bookmark_action = QAction("&Remove Bookmark", self._window)
        remove_bookmark_action.setShortcut("Ctrl+Shift+B")
        remove_bookmark_action.triggered.connect(host._remove_bookmark)
        bookmarks_menu.addAction(remove_bookmark_action)

        bookmarks_menu.addSeparator()

        bookmarks_submenu = bookmarks_menu.addMenu("Go to Bookmark")

        help_menu = menubar.addMenu("&Help")

        stats_action = QAction("&Reading Statistics", self._window)
        stats_action.triggered.connect(host._show_statistics)
        help_menu.addAction(stats_action)

        help_menu.addSeparator()

        shortcuts_action = QAction("Keyboard &Shortcuts", self._window)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(host._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self._window)
        about_action.triggered.connect(host._show_about)
        help_menu.addAction(about_action)

        return MenuRefs(
            recent_menu=recent_menu,  # type: ignore[arg-type]  # PyQt6 stubs widen addMenu return to QMenu | None
            bookmarks_submenu=bookmarks_submenu,  # type: ignore[arg-type]  # same
            always_on_top_action=always_on_top_action,
        )
