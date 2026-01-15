"""RSVP playback engine."""
from dataclasses import dataclass, field
from typing import Optional, Callable
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rsvp.core.text_processor import Word, process_text


@dataclass
class RSVPState:
    """Current state of the RSVP engine."""
    words: list[Word] = field(default_factory=list)
    current_index: int = 0
    wpm: int = 300
    is_playing: bool = False

    @property
    def current_word(self) -> Optional[Word]:
        """Get the current word."""
        if 0 <= self.current_index < len(self.words):
            return self.words[self.current_index]
        return None

    @property
    def progress(self) -> float:
        """Get progress as a percentage (0-100)."""
        if not self.words:
            return 0.0
        return (self.current_index / len(self.words)) * 100

    @property
    def words_remaining(self) -> int:
        """Get number of words remaining."""
        return max(0, len(self.words) - self.current_index)

    @property
    def time_remaining_seconds(self) -> float:
        """Estimate time remaining in seconds."""
        if self.wpm <= 0:
            return 0.0
        return (self.words_remaining / self.wpm) * 60


class RSVPEngine(QObject):
    """Engine for controlling RSVP playback."""

    # Signals
    word_changed = pyqtSignal(object)  # Emits Word or None
    state_changed = pyqtSignal()  # Emits when play/pause/stop changes
    progress_changed = pyqtSignal(float)  # Emits progress percentage
    finished = pyqtSignal()  # Emits when reaching end of text

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = RSVPState()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    @property
    def state(self) -> RSVPState:
        """Get current state."""
        return self._state

    @property
    def wpm(self) -> int:
        """Get current words per minute."""
        return self._state.wpm

    @wpm.setter
    def wpm(self, value: int):
        """Set words per minute."""
        self._state.wpm = max(50, min(2000, value))
        if self._state.is_playing:
            self._update_timer_interval()

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._state.is_playing

    @property
    def current_index(self) -> int:
        """Get current word index."""
        return self._state.current_index

    @property
    def word_count(self) -> int:
        """Get total word count."""
        return len(self._state.words)

    def load_text(self, text: str):
        """Load text for RSVP display."""
        self.stop()
        self._state.words = process_text(text)
        self._state.current_index = 0
        self.state_changed.emit()
        self.progress_changed.emit(0.0)
        if self._state.words:
            self.word_changed.emit(self._state.current_word)
        else:
            self.word_changed.emit(None)

    def play(self):
        """Start or resume playback."""
        if not self._state.words:
            return

        # Reset to beginning if at or past the last word
        if self._state.current_index >= len(self._state.words) - 1:
            self._state.current_index = 0

        self._state.is_playing = True
        self._update_timer_interval()
        self._timer.start()
        self.state_changed.emit()

    def pause(self):
        """Pause playback."""
        self._state.is_playing = False
        self._timer.stop()
        self.state_changed.emit()

    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self._state.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        """Stop playback and reset to beginning."""
        self._state.is_playing = False
        self._timer.stop()
        self._state.current_index = 0
        self.state_changed.emit()
        self.progress_changed.emit(0.0)
        if self._state.words:
            self.word_changed.emit(self._state.current_word)

    def seek(self, index: int):
        """Seek to a specific word index."""
        if not self._state.words:
            return

        self._state.current_index = max(0, min(index, len(self._state.words) - 1))
        self.word_changed.emit(self._state.current_word)
        self.progress_changed.emit(self._state.progress)

    def seek_percent(self, percent: float):
        """Seek to a percentage of the text."""
        if not self._state.words:
            return

        index = int((percent / 100) * len(self._state.words))
        self.seek(index)

    def skip_forward(self, words: int = 10):
        """Skip forward by a number of words."""
        self.seek(self._state.current_index + words)

    def skip_backward(self, words: int = 10):
        """Skip backward by a number of words."""
        self.seek(self._state.current_index - words)

    def previous_sentence(self):
        """Go to the beginning of the current or previous sentence."""
        if not self._state.words:
            return

        # Start from one word before current
        idx = max(0, self._state.current_index - 1)

        # Find the previous sentence-ending punctuation
        while idx > 0:
            word = self._state.words[idx]
            if word.text and word.text[-1] in '.!?':
                # Found end of previous sentence, go to start of next
                self.seek(idx + 1)
                return
            idx -= 1

        # No previous sentence found, go to beginning
        self.seek(0)

    def next_sentence(self):
        """Go to the beginning of the next sentence."""
        if not self._state.words:
            return

        idx = self._state.current_index

        # Find the next sentence-ending punctuation
        while idx < len(self._state.words) - 1:
            word = self._state.words[idx]
            if word.text and word.text[-1] in '.!?':
                # Found end of sentence, go to start of next
                self.seek(idx + 1)
                return
            idx += 1

        # No next sentence found, go to end
        self.seek(len(self._state.words) - 1)

    def _update_timer_interval(self):
        """Update timer interval based on WPM and current word."""
        base_interval = 60000 / self._state.wpm  # Base ms per word

        # Apply pause multiplier for current word
        current = self._state.current_word
        if current:
            interval = base_interval * current.pause_after
        else:
            interval = base_interval

        self._timer.setInterval(int(interval))

    def _advance(self):
        """Advance to the next word."""
        self._state.current_index += 1

        if self._state.current_index >= len(self._state.words):
            # Reached the end
            self.pause()
            self._state.current_index = len(self._state.words) - 1
            self.finished.emit()
            return

        self.word_changed.emit(self._state.current_word)
        self.progress_changed.emit(self._state.progress)
        self._update_timer_interval()
