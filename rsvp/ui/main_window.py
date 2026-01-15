"""Main application window."""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QLabel
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import get_settings_manager
from rsvp.core.text_processor import load_text_from_file
from rsvp.ui.word_display import WordDisplayWidget
from rsvp.ui.controls import PlaybackControls, SpeedControl, ProgressWidget
from rsvp.ui.text_input_dialog import TextInputDialog
from rsvp.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._current_file = None
        self._engine = RSVPEngine()
        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()
        self._connect_signals()
        self._load_window_settings()

    def _setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("RSVP Reader")
        self.setMinimumSize(600, 400)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Word display (main area)
        self.word_display = WordDisplayWidget()
        layout.addWidget(self.word_display, stretch=1)

        # Controls panel
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setSpacing(5)

        # Progress bar
        self.progress_widget = ProgressWidget()
        controls_layout.addWidget(self.progress_widget)

        # Speed and playback controls row
        controls_row = QHBoxLayout()

        self.speed_control = SpeedControl()
        controls_row.addWidget(self.speed_control)

        self.playback_controls = PlaybackControls()
        controls_row.addWidget(self.playback_controls)

        controls_layout.addLayout(controls_row)
        layout.addWidget(controls_panel)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("No text loaded")
        self.status_bar.addWidget(self.status_label)

        # Apply settings
        self._apply_settings()

    def _setup_menus(self):
        """Set up the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Load text
        load_action = QAction("&Load Text...", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self._load_text_dialog)
        file_menu.addAction(load_action)

        # Open file
        open_action = QAction("&Open File...", self)
        open_action.setShortcut("Ctrl+Shift+O")
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # Recent files submenu
        self.recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_menu()

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        # Paste and read
        paste_action = QAction("&Paste and Read", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self._paste_and_read)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        # Settings
        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Always on top
        self.always_on_top_action = QAction("Always on &Top", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.triggered.connect(self._toggle_always_on_top)
        view_menu.addAction(self.always_on_top_action)

        # Fullscreen
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        # Playback menu
        playback_menu = menubar.addMenu("&Playback")

        play_action = QAction("&Play/Pause", self)
        play_action.setShortcut("Space")
        play_action.triggered.connect(self._engine.toggle_play_pause)
        playback_menu.addAction(play_action)

        stop_action = QAction("&Stop", self)
        stop_action.setShortcut("S")
        stop_action.triggered.connect(self._engine.stop)
        playback_menu.addAction(stop_action)

        playback_menu.addSeparator()

        speed_up_action = QAction("Speed &Up", self)
        speed_up_action.setShortcut("Up")
        speed_up_action.triggered.connect(self._speed_up)
        playback_menu.addAction(speed_up_action)

        speed_down_action = QAction("Speed &Down", self)
        speed_down_action.setShortcut("Down")
        speed_down_action.triggered.connect(self._speed_down)
        playback_menu.addAction(speed_down_action)

        # Bookmarks menu
        bookmarks_menu = menubar.addMenu("&Bookmarks")

        add_bookmark_action = QAction("&Add Bookmark", self)
        add_bookmark_action.setShortcut("Ctrl+B")
        add_bookmark_action.triggered.connect(self._add_bookmark)
        bookmarks_menu.addAction(add_bookmark_action)

        self.bookmarks_submenu = bookmarks_menu.addMenu("Go to Bookmark")

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("Keyboard &Shortcuts", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Navigation shortcuts
        QShortcut(QKeySequence("Left"), self, self._engine.skip_backward)
        QShortcut(QKeySequence("Right"), self, self._engine.skip_forward)
        QShortcut(QKeySequence("Shift+Left"), self, self._engine.previous_sentence)
        QShortcut(QKeySequence("Shift+Right"), self, self._engine.next_sentence)
        QShortcut(QKeySequence("Home"), self, lambda: self._engine.seek(0))
        QShortcut(QKeySequence("End"), self, lambda: self._engine.seek(self._engine.word_count - 1))

        # Escape to stop
        QShortcut(QKeySequence("Escape"), self, self._engine.pause)

    def _connect_signals(self):
        """Connect signals between components."""
        # Engine signals
        self._engine.word_changed.connect(self._on_word_changed)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.progress_changed.connect(self._on_progress_changed)
        self._engine.finished.connect(self._on_finished)

        # Control signals
        self.playback_controls.play_clicked.connect(self._engine.play)
        self.playback_controls.pause_clicked.connect(self._engine.pause)
        self.playback_controls.stop_clicked.connect(self._engine.stop)
        self.playback_controls.skip_forward_clicked.connect(self._engine.skip_forward)
        self.playback_controls.skip_backward_clicked.connect(self._engine.skip_backward)
        self.playback_controls.prev_sentence_clicked.connect(self._engine.previous_sentence)
        self.playback_controls.next_sentence_clicked.connect(self._engine.next_sentence)

        self.speed_control.wpm_changed.connect(self._on_wpm_changed)
        self.progress_widget.seek_requested.connect(self._engine.seek_percent)

    def _load_window_settings(self):
        """Load window position and size from settings."""
        settings = get_settings_manager().settings

        self.resize(settings.window_width, settings.window_height)

        if settings.window_x is not None and settings.window_y is not None:
            self.move(settings.window_x, settings.window_y)

        if settings.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.always_on_top_action.setChecked(True)

        self.speed_control.set_wpm(settings.wpm)

    def _save_window_settings(self):
        """Save window position and size to settings."""
        manager = get_settings_manager()
        settings = manager.settings

        settings.window_width = self.width()
        settings.window_height = self.height()
        settings.window_x = self.x()
        settings.window_y = self.y()

        manager.save()

    def _apply_settings(self):
        """Apply current settings to UI."""
        settings = get_settings_manager().settings
        self.word_display.update_settings()

        if settings.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.show()

    def _update_recent_menu(self):
        """Update the recent files menu."""
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

    def _load_text_dialog(self):
        """Show the text input dialog."""
        dialog = TextInputDialog(self)
        if dialog.exec():
            text = dialog.get_text()
            source = dialog.get_source_path()

            self._engine.load_text(text)
            self._current_file = source

            if source:
                get_settings_manager().add_recent_file(source)
                self._update_recent_menu()
                self.setWindowTitle(f"RSVP Reader - {source}")
            else:
                self.setWindowTitle("RSVP Reader")

            self._update_bookmarks_menu()
            self.status_label.setText(f"Loaded {self._engine.word_count} words")

    def _open_file(self):
        """Open a file directly."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Text File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )

        if filepath:
            self._load_file(filepath)

    def _load_file(self, filepath: str):
        """Load a file."""
        try:
            text = load_text_from_file(filepath)
            self._engine.load_text(text)
            self._current_file = filepath

            get_settings_manager().add_recent_file(filepath)
            self._update_recent_menu()
            self._update_bookmarks_menu()

            self.setWindowTitle(f"RSVP Reader - {filepath}")
            self.status_label.setText(f"Loaded {self._engine.word_count} words")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load file: {e}")

    def _paste_and_read(self):
        """Paste from clipboard and start reading."""
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception:
            from PyQt6.QtWidgets import QApplication
            text = QApplication.clipboard().text()

        if text:
            self._engine.load_text(text)
            self._current_file = None
            self.setWindowTitle("RSVP Reader - Clipboard")
            self.status_label.setText(f"Loaded {self._engine.word_count} words from clipboard")
            self._engine.play()

    def _show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self._apply_settings()
            self.speed_control.set_wpm(get_settings_manager().settings.wpm)

    def _toggle_always_on_top(self):
        """Toggle always on top."""
        on_top = self.always_on_top_action.isChecked()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.show()

        settings = get_settings_manager()
        settings.settings.always_on_top = on_top
        settings.save()

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _speed_up(self):
        """Increase WPM."""
        new_wpm = min(2000, self._engine.wpm + 25)
        self._engine.wpm = new_wpm
        self.speed_control.set_wpm(new_wpm)

    def _speed_down(self):
        """Decrease WPM."""
        new_wpm = max(50, self._engine.wpm - 25)
        self._engine.wpm = new_wpm
        self.speed_control.set_wpm(new_wpm)

    def _add_bookmark(self):
        """Add a bookmark at current position."""
        if not self._current_file:
            QMessageBox.information(
                self, "Bookmark",
                "Bookmarks are only available for files."
            )
            return

        get_settings_manager().add_bookmark(
            self._current_file,
            self._engine.current_index
        )
        self._update_bookmarks_menu()
        self.status_label.setText(f"Bookmark added at word {self._engine.current_index}")

    def _update_bookmarks_menu(self):
        """Update the bookmarks submenu."""
        self.bookmarks_submenu.clear()

        if not self._current_file:
            no_bookmarks = QAction("No bookmarks", self)
            no_bookmarks.setEnabled(False)
            self.bookmarks_submenu.addAction(no_bookmarks)
            return

        bookmarks = get_settings_manager().get_bookmarks(self._current_file)

        if not bookmarks:
            no_bookmarks = QAction("No bookmarks", self)
            no_bookmarks.setEnabled(False)
            self.bookmarks_submenu.addAction(no_bookmarks)
            return

        for idx in bookmarks:
            action = QAction(f"Word {idx}", self)
            action.triggered.connect(lambda checked, i=idx: self._engine.seek(i))
            self.bookmarks_submenu.addAction(action)

    def _show_shortcuts(self):
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
<tr><td><b>Escape</b></td><td>Pause</td></tr>
</table>
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About RSVP Reader",
            "<h2>RSVP Reader</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A Rapid Serial Visual Presentation speed reading application.</p>"
            "<p>RSVP displays text one word at a time with the Optimal Recognition "
            "Point (ORP) highlighted, allowing for faster reading speeds.</p>"
        )

    def _on_word_changed(self, word):
        """Handle word changed signal."""
        self.word_display.set_word(word)

    def _on_state_changed(self):
        """Handle state changed signal."""
        self.playback_controls.set_playing(self._engine.is_playing)

    def _on_progress_changed(self, progress):
        """Handle progress changed signal."""
        state = self._engine.state
        self.progress_widget.update_progress(
            state.current_index,
            len(state.words),
            state.time_remaining_seconds
        )

    def _on_wpm_changed(self, wpm):
        """Handle WPM changed signal."""
        self._engine.wpm = wpm

    def _on_finished(self):
        """Handle finished signal."""
        self.status_label.setText("Finished reading")

    def closeEvent(self, event):
        """Handle window close."""
        self._save_window_settings()
        event.accept()
