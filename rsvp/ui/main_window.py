"""Main application window."""

import logging

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStatusBar, QVBoxLayout, QWidget

from rsvp.core.constants import WPM_MAX, WPM_MIN, WPM_STEP
from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import get_settings_manager
from rsvp.ui.bookmark_controller import BookmarkController
from rsvp.ui.controls import PlaybackControls, ProgressWidget, SpeedControl
from rsvp.ui.document_loader import DocumentLoader
from rsvp.ui.menu_builder import MenuBuilder
from rsvp.ui.settings_dialog import SettingsDialog
from rsvp.ui.text_input_dialog import TextInputDialog
from rsvp.ui.word_display import WordDisplayWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self._current_file = None
        self._engine = RSVPEngine()
        self._setup_ui()
        self._setup_menus()
        self._setup_controllers()
        self._setup_shortcuts()
        self._connect_signals()
        self._load_window_settings()
        self.installEventFilter(self)
        self._setup_tab_order()
        self._check_settings_reset()
        logger.info("MainWindow initialized")

    # ------------------------------------------------------------------
    # Accessors used by MenuBuilder
    # ------------------------------------------------------------------

    @property
    def engine(self) -> RSVPEngine:
        return self._engine

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setWindowTitle("RSVP Reader")
        self.setMinimumSize(600, 400)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.word_display = WordDisplayWidget()
        layout.addWidget(self.word_display, stretch=1)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setSpacing(5)

        self.progress_widget = ProgressWidget()
        controls_layout.addWidget(self.progress_widget)

        controls_row = QHBoxLayout()

        self.speed_control = SpeedControl()
        controls_row.addWidget(self.speed_control)

        self.playback_controls = PlaybackControls()
        controls_row.addWidget(self.playback_controls)

        controls_layout.addLayout(controls_row)
        layout.addWidget(controls_panel)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("No text loaded")
        self.status_bar.addWidget(self.status_label)

        self._apply_settings()

    def _setup_menus(self) -> None:
        """Set up the menu bar."""
        refs = MenuBuilder(self, self).build()
        self.recent_menu = refs.recent_menu
        self.bookmarks_submenu = refs.bookmarks_submenu
        self.always_on_top_action = refs.always_on_top_action
        self._update_recent_menu()

    def _setup_controllers(self) -> None:
        """Wire up the helpers that own bookmark + document-loading logic."""
        self._bookmarks = BookmarkController(
            parent_widget=self,
            engine=self._engine,
            submenu=self.bookmarks_submenu,
            status_setter=self.status_label.setText,
            current_file_getter=lambda: self._current_file,
        )
        self._documents = DocumentLoader(
            parent_widget=self,
            engine=self._engine,
            status_setter=self.status_label.setText,
            title_setter=self.setWindowTitle,
            on_loaded=self._on_document_loaded,
            current_file_getter=lambda: self._current_file,
        )
        self._bookmarks.refresh_menu()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Shift+Left"), self, self._engine.previous_sentence)
        QShortcut(QKeySequence("Shift+Right"), self, self._engine.next_sentence)
        QShortcut(QKeySequence("Home"), self, lambda: self._engine.seek(0))
        QShortcut(QKeySequence("End"), self, lambda: self._engine.seek(self._engine.word_count - 1))

    def _connect_signals(self) -> None:
        """Connect signals between components."""
        self._engine.word_changed.connect(self._on_word_changed)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.progress_changed.connect(self._on_progress_changed)
        self._engine.finished.connect(self._on_finished)

        self.playback_controls.play_clicked.connect(self._engine.play)
        self.playback_controls.pause_clicked.connect(self._engine.pause)
        self.playback_controls.stop_clicked.connect(self._engine.stop)
        self.playback_controls.skip_forward_clicked.connect(self._engine.skip_forward)
        self.playback_controls.skip_backward_clicked.connect(self._engine.skip_backward)
        self.playback_controls.prev_sentence_clicked.connect(self._engine.previous_sentence)
        self.playback_controls.next_sentence_clicked.connect(self._engine.next_sentence)

        self.speed_control.wpm_changed.connect(self._on_wpm_changed)
        self.progress_widget.seek_requested.connect(self._engine.seek_percent)

    def eventFilter(self, obj, event) -> bool:
        """Handle focus-aware keyboard navigation."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                focus = self.focusWidget()
                if focus in (self.speed_control.slider, self.speed_control.spinbox):
                    return False
                if key == Qt.Key.Key_Up:
                    self._speed_up()
                elif key == Qt.Key.Key_Down:
                    self._speed_down()
                elif key == Qt.Key.Key_Left:
                    self._engine.skip_backward()
                elif key == Qt.Key.Key_Right:
                    self._engine.skip_forward()
                return True
            if key == Qt.Key.Key_Escape:
                self._engine.pause()
                self.word_display.setFocus()
                return True
        return super().eventFilter(obj, event)

    def _setup_tab_order(self) -> None:
        """Set up Tab key navigation order."""
        self.setTabOrder(self.speed_control.slider, self.speed_control.spinbox)
        self.setTabOrder(self.speed_control.spinbox, self.word_display)

    # ------------------------------------------------------------------
    # Window settings
    # ------------------------------------------------------------------

    def _load_window_settings(self) -> None:
        """Load window position and size from settings."""
        settings = get_settings_manager().settings

        self.resize(settings.window_width, settings.window_height)

        if settings.window_x is not None and settings.window_y is not None:
            self.move(settings.window_x, settings.window_y)

        if settings.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.always_on_top_action.setChecked(True)

        self.speed_control.set_wpm(settings.wpm)

    def _save_window_settings(self) -> None:
        """Save window position and size to settings."""
        manager = get_settings_manager()
        settings = manager.settings

        settings.window_width = self.width()
        settings.window_height = self.height()
        settings.window_x = self.x()
        settings.window_y = self.y()

        manager.save()

    def _apply_settings(self) -> None:
        """Apply current settings to UI."""
        settings = get_settings_manager().settings
        self.word_display.update_settings()

        if settings.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        # setWindowFlag hides the widget; re-show only if already visible
        if self.isVisible():
            self.show()

    def _update_recent_menu(self) -> None:
        """Update the recent files menu."""
        from PyQt6.QtGui import QAction

        self.recent_menu.clear()
        settings = get_settings_manager().settings

        for filepath in settings.recent_files:
            action = QAction(filepath, self)
            action.triggered.connect(lambda checked, f=filepath: self._load_file(f))
            self.recent_menu.addAction(action)

        if not settings.recent_files:
            no_recent = QAction("No recent files", self)
            no_recent.setEnabled(False)
            self.recent_menu.addAction(no_recent)

    # ------------------------------------------------------------------
    # Document loading (delegated)
    # ------------------------------------------------------------------

    def _load_text_dialog(self) -> None:
        """Show the text input dialog."""
        dialog = TextInputDialog(self)
        if dialog.exec():
            self._documents.load_from_text_dialog(dialog.get_text(), dialog.get_source_path())

    def _open_file(self) -> None:
        """Open a file directly."""
        self._documents.open_file_dialog()

    def _load_file(self, filepath: str) -> None:
        """Load a file by path (used by recent files menu)."""
        self._documents.load_file(filepath)

    def _paste_and_read(self) -> None:
        """Paste from clipboard and start reading."""
        self._documents.load_from_clipboard()

    def _on_document_loaded(self, source: str | None) -> None:
        """Hook called by DocumentLoader after each successful load."""
        self._current_file = source
        self._update_recent_menu()
        self._bookmarks.refresh_menu()

    # ------------------------------------------------------------------
    # Dialogs / view toggles
    # ------------------------------------------------------------------

    def _show_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self._apply_settings()
            self.speed_control.set_wpm(get_settings_manager().settings.wpm)

    def _toggle_always_on_top(self) -> None:
        """Toggle always on top."""
        on_top = self.always_on_top_action.isChecked()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.show()

        manager = get_settings_manager()
        manager.settings.always_on_top = on_top
        manager.save()

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _speed_up(self) -> None:
        """Increase WPM."""
        new_wpm = min(WPM_MAX, self._engine.wpm + WPM_STEP)
        self.speed_control.set_wpm(new_wpm)

    def _speed_down(self) -> None:
        """Decrease WPM."""
        new_wpm = max(WPM_MIN, self._engine.wpm - WPM_STEP)
        self.speed_control.set_wpm(new_wpm)

    # ------------------------------------------------------------------
    # Bookmarks (delegated)
    # ------------------------------------------------------------------

    def _add_bookmark(self) -> None:
        self._bookmarks.add()

    def _remove_bookmark(self) -> None:
        self._bookmarks.remove()

    def _update_bookmarks_menu(self) -> None:
        self._bookmarks.refresh_menu()

    # ------------------------------------------------------------------
    # Help dialogs
    # ------------------------------------------------------------------

    def _show_shortcuts(self) -> None:
        """Show keyboard shortcuts help."""
        shortcuts = """
<h3>Keyboard Shortcuts</h3>
<table>
<tr><td><b>Space</b></td><td>Play/Pause</td></tr>
<tr><td><b>S</b></td><td>Stop</td></tr>
<tr><td><b>Left/Right</b></td><td>Skip 10 words</td></tr>
<tr><td><b>Shift+Left/Right</b></td><td>Previous/Next sentence</td></tr>
<tr><td><b>Up/Down</b></td><td>Increase/Decrease speed</td></tr>
<tr><td><b>Home/End</b></td><td>Go to start/end</td></tr>
<tr><td><b>Ctrl+O</b></td><td>Load text</td></tr>
<tr><td><b>Ctrl+V</b></td><td>Paste and read</td></tr>
<tr><td><b>Ctrl+B</b></td><td>Add bookmark</td></tr>
<tr><td><b>Ctrl+,</b></td><td>Settings</td></tr>
<tr><td><b>F11</b></td><td>Fullscreen</td></tr>
<tr><td><b>Tab</b></td><td>Cycle focus (speed controls)</td></tr>
<tr><td><b>Escape</b></td><td>Pause and return focus to display</td></tr>
</table>
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def _show_about(self) -> None:
        """Show about dialog."""
        from rsvp import __version__

        QMessageBox.about(
            self,
            "About RSVP Reader",
            f"<h2>RSVP Reader</h2>"
            f"<p>Version {__version__}</p>"
            "<p>A Rapid Serial Visual Presentation speed reading application.</p>"
            "<p>RSVP displays text one word at a time with the Optimal Recognition "
            "Point (ORP) highlighted, allowing for faster reading speeds.</p>",
        )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_word_changed(self, word) -> None:
        """Handle word changed signal."""
        self.word_display.set_word(word)

    def _on_state_changed(self) -> None:
        """Handle state changed signal."""
        self.playback_controls.set_playing(self._engine.is_playing)

    def _on_progress_changed(self, progress: float) -> None:
        """Handle progress changed signal."""
        state = self._engine.state
        self.progress_widget.update_progress(
            progress, state.current_index, len(state.words), state.time_remaining_seconds
        )

    def _on_wpm_changed(self, wpm) -> None:
        """Handle WPM changed signal."""
        self._engine.wpm = wpm

    def _on_finished(self) -> None:
        """Handle finished signal."""
        self.status_label.setText("Finished reading")
        if self._current_file:
            get_settings_manager().clear_position(self._current_file)
            logger.info("Reading finished; cleared saved position for %s", self._current_file)

    # ------------------------------------------------------------------
    # Notifications / lifecycle
    # ------------------------------------------------------------------

    def _check_settings_reset(self) -> None:
        """Show notification if settings were reset due to corruption."""
        if get_settings_manager().was_reset():
            QMessageBox.warning(
                self,
                "Settings Reset",
                "Your settings file was corrupted and has been reset to defaults. "
                "A backup was saved to settings.json.bak.",
            )

    def _check_settings_save_failed(self) -> None:
        """Show notification if settings could not be saved (e.g. read-only filesystem)."""
        if get_settings_manager().save_failed():
            self.status_label.setText("Warning: settings could not be saved (filesystem error)")

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._documents.maybe_save_position()
        self._save_window_settings()
        self._check_settings_save_failed()
        event.accept()
