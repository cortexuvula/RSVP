"""Playback control widgets."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QSlider, QLabel, QSpinBox, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal


class PlaybackControls(QWidget):
    """Widget containing playback control buttons."""

    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    skip_forward_clicked = pyqtSignal()
    skip_backward_clicked = pyqtSignal()
    prev_sentence_clicked = pyqtSignal()
    next_sentence_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        style = self.style()

        # Previous sentence
        self.prev_sentence_btn = QPushButton()
        self.prev_sentence_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.prev_sentence_btn.setToolTip("Previous sentence (Shift+Left)")
        self.prev_sentence_btn.setFixedSize(40, 40)
        self.prev_sentence_btn.clicked.connect(self.prev_sentence_clicked.emit)
        layout.addWidget(self.prev_sentence_btn)

        # Skip backward
        self.skip_back_btn = QPushButton()
        self.skip_back_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSeekBackward))
        self.skip_back_btn.setToolTip("Skip back 10 words (Left)")
        self.skip_back_btn.setFixedSize(40, 40)
        self.skip_back_btn.clicked.connect(self.skip_backward_clicked.emit)
        layout.addWidget(self.skip_back_btn)

        # Play/Pause
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_pause_btn.setToolTip("Play/Pause (Space)")
        self.play_pause_btn.setFixedSize(50, 50)
        self.play_pause_btn.clicked.connect(self._on_play_pause)
        layout.addWidget(self.play_pause_btn)

        # Stop
        self.stop_btn = QPushButton()
        self.stop_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_btn.setToolTip("Stop (S)")
        self.stop_btn.setFixedSize(40, 40)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        layout.addWidget(self.stop_btn)

        # Skip forward
        self.skip_fwd_btn = QPushButton()
        self.skip_fwd_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward))
        self.skip_fwd_btn.setToolTip("Skip forward 10 words (Right)")
        self.skip_fwd_btn.setFixedSize(40, 40)
        self.skip_fwd_btn.clicked.connect(self.skip_forward_clicked.emit)
        layout.addWidget(self.skip_fwd_btn)

        # Next sentence
        self.next_sentence_btn = QPushButton()
        self.next_sentence_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        self.next_sentence_btn.setToolTip("Next sentence (Shift+Right)")
        self.next_sentence_btn.setFixedSize(40, 40)
        self.next_sentence_btn.clicked.connect(self.next_sentence_clicked.emit)
        layout.addWidget(self.next_sentence_btn)

    def _on_play_pause(self):
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()

    def set_playing(self, is_playing: bool):
        """Update the play/pause button state."""
        self._is_playing = is_playing
        style = self.style()
        if is_playing:
            self.play_pause_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_pause_btn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))


class SpeedControl(QWidget):
    """Widget for controlling reading speed (WPM)."""

    wpm_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Label
        layout.addWidget(QLabel("WPM:"))

        # Decrease button
        self.decrease_btn = QPushButton("-")
        self.decrease_btn.setFixedSize(30, 30)
        self.decrease_btn.clicked.connect(self._decrease_wpm)
        layout.addWidget(self.decrease_btn)

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(50)
        self.slider.setMaximum(1000)
        self.slider.setValue(300)
        self.slider.setTickInterval(50)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.valueChanged.connect(self._on_slider_change)
        layout.addWidget(self.slider)

        # Spinbox
        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(50)
        self.spinbox.setMaximum(2000)
        self.spinbox.setValue(300)
        self.spinbox.setSingleStep(25)
        self.spinbox.setSuffix(" wpm")
        self.spinbox.valueChanged.connect(self._on_spinbox_change)
        layout.addWidget(self.spinbox)

        # Increase button
        self.increase_btn = QPushButton("+")
        self.increase_btn.setFixedSize(30, 30)
        self.increase_btn.clicked.connect(self._increase_wpm)
        layout.addWidget(self.increase_btn)

    def _decrease_wpm(self):
        new_val = max(50, self.spinbox.value() - 25)
        self.set_wpm(new_val)

    def _increase_wpm(self):
        new_val = min(2000, self.spinbox.value() + 25)
        self.set_wpm(new_val)

    def _on_slider_change(self, value):
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        self.wpm_changed.emit(value)

    def _on_spinbox_change(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(min(value, 1000))
        self.slider.blockSignals(False)
        self.wpm_changed.emit(value)

    def set_wpm(self, wpm: int):
        """Set the WPM value."""
        self.spinbox.blockSignals(True)
        self.slider.blockSignals(True)
        self.spinbox.setValue(wpm)
        self.slider.setValue(min(wpm, 1000))
        self.spinbox.blockSignals(False)
        self.slider.blockSignals(False)
        self.wpm_changed.emit(wpm)

    def get_wpm(self) -> int:
        """Get the current WPM value."""
        return self.spinbox.value()


class ProgressWidget(QWidget):
    """Widget showing reading progress."""

    seek_requested = pyqtSignal(float)  # Emits percentage 0-100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Progress slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.slider.setValue(0)
        self.slider.sliderReleased.connect(self._on_seek)
        layout.addWidget(self.slider)

        # Progress label
        self.label = QLabel("0 / 0 words")
        self.label.setMinimumWidth(120)
        layout.addWidget(self.label)

        # Time remaining
        self.time_label = QLabel("")
        self.time_label.setMinimumWidth(80)
        layout.addWidget(self.time_label)

    def _on_seek(self):
        percent = (self.slider.value() / 1000) * 100
        self.seek_requested.emit(percent)

    def update_progress(self, current: int, total: int, time_remaining: float):
        """Update the progress display."""
        if total > 0:
            self.slider.blockSignals(True)
            self.slider.setValue(int((current / total) * 1000))
            self.slider.blockSignals(False)

        self.label.setText(f"{current} / {total} words")

        # Format time remaining
        if time_remaining > 0:
            minutes = int(time_remaining // 60)
            seconds = int(time_remaining % 60)
            if minutes > 0:
                self.time_label.setText(f"{minutes}m {seconds}s left")
            else:
                self.time_label.setText(f"{seconds}s left")
        else:
            self.time_label.setText("")
