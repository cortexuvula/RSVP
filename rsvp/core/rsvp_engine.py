"""RSVP playback engine."""

import logging
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from rsvp.core.constants import (
    DEFAULT_SKIP_WORDS,
    PAUSE_PARAGRAPH,
    WPM_DEFAULT,
    WPM_MAX,
    WPM_MIN,
)
from rsvp.core.settings import SettingsManager
from rsvp.core.text_processor import Word, process_text

logger = logging.getLogger(__name__)


@dataclass
class RSVPState:
    """Current state of the RSVP engine."""

    words: list[Word] = field(default_factory=list)
    current_index: int = 0
    wpm: int = WPM_DEFAULT
    is_playing: bool = False

    @property
    def current_word(self) -> Word | None:
        """Get the current word."""
        if 0 <= self.current_index < len(self.words):
            return self.words[self.current_index]
        return None

    @property
    def progress(self) -> float:
        """Get progress as a percentage (0-100)."""
        if not self.words:
            return 0.0
        if len(self.words) == 1:
            return 100.0
        return (self.current_index / (len(self.words) - 1)) * 100

    @property
    def words_remaining(self) -> int:
        """Get number of words remaining."""
        return max(0, len(self.words) - self.current_index)

    @property
    def time_remaining_seconds(self) -> float:
        """Estimate time remaining in seconds."""
        if self.wpm <= 0:
            return 0.0
        base_interval = 60.0 / self.wpm
        return sum(base_interval * w.pause_after for w in self.words[self.current_index :])


class RSVPEngine(QObject):
    """Engine for controlling RSVP playback."""

    # Signals
    word_changed = pyqtSignal(object)  # Emits Word or None
    state_changed = pyqtSignal()  # Emits when play/pause/stop changes
    progress_changed = pyqtSignal(float)  # Emits progress percentage
    finished = pyqtSignal()  # Emits when reaching end of text

    def __init__(self, parent=None, settings: SettingsManager | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
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
    def wpm(self, value: int) -> None:
        """Set words per minute."""
        self._state.wpm = max(WPM_MIN, min(WPM_MAX, value))
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

    def load_text(self, text: str) -> None:
        """Load text for RSVP display."""
        self.stop()
        self._state.words = process_text(text)
        self._state.current_index = 0
        self.state_changed.emit()
        self.progress_changed.emit(0.0)
        logger.info("Loaded %d words into engine", len(self._state.words))
        if self._state.words:
            self.word_changed.emit(self._state.current_word)
        else:
            self.word_changed.emit(None)

    def play(self) -> None:
        """Start or resume playback."""
        if not self._state.words:
            return

        # Reset to beginning if at or past the last word
        if self._state.current_index >= len(self._state.words) - 1:
            self._state.current_index = 0

        self._state.is_playing = True
        self._update_timer_interval()
        self._timer.start()
        logger.debug("Engine play() at index %d", self._state.current_index)
        self.state_changed.emit()

    def pause(self) -> None:
        """Pause playback."""
        self._state.is_playing = False
        self._timer.stop()
        logger.debug("Engine pause() at index %d", self._state.current_index)
        self.state_changed.emit()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self._state.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        """Stop playback and reset to beginning."""
        self._state.is_playing = False
        self._timer.stop()
        self._state.current_index = 0
        self.state_changed.emit()
        self.progress_changed.emit(0.0)
        if self._state.words:
            self.word_changed.emit(self._state.current_word)

    def seek(self, index: int) -> None:
        """Seek to a specific word index."""
        if not self._state.words:
            return

        self._state.current_index = max(0, min(index, len(self._state.words) - 1))
        logger.debug("Engine seek() to index %d", self._state.current_index)
        self.word_changed.emit(self._state.current_word)
        self.progress_changed.emit(self._state.progress)

    def seek_percent(self, percent: float) -> None:
        """Seek to a percentage of the text."""
        if not self._state.words:
            return

        if len(self._state.words) == 1:
            index = 0
        else:
            index = round((percent / 100) * (len(self._state.words) - 1))
        self.seek(index)

    def skip_forward(self, words: int = DEFAULT_SKIP_WORDS) -> None:
        """Skip forward by a number of words."""
        self.seek(self._state.current_index + words)

    def skip_backward(self, words: int = DEFAULT_SKIP_WORDS) -> None:
        """Skip backward by a number of words."""
        self.seek(self._state.current_index - words)

    def previous_sentence(self) -> None:
        """Go to the beginning of the current or previous sentence."""
        if not self._state.words:
            return

        # Start from one word before current
        idx = max(0, self._state.current_index - 1)

        # Skip past any contiguous sentence-ending words at the start position.
        # This prevents getting stuck when already at a sentence boundary.
        while idx > 0 and self._state.words[idx].text and self._state.words[idx].text[-1] in ".!?":
            idx -= 1

        # Find the previous sentence-ending punctuation
        while idx > 0:
            word = self._state.words[idx]
            if word.text and word.text[-1] in ".!?":
                # Found end of previous sentence, go to start of next
                self.seek(idx + 1)
                return
            idx -= 1

        # No previous sentence found, go to beginning
        self.seek(0)

    def next_sentence(self) -> None:
        """Go to the beginning of the next sentence."""
        if not self._state.words:
            return

        idx = self._state.current_index

        # Find the next sentence-ending punctuation
        while idx < len(self._state.words) - 1:
            word = self._state.words[idx]
            if word.text and word.text[-1] in ".!?":
                # Found end of sentence, go to start of next
                self.seek(idx + 1)
                return
            idx += 1

        # No next sentence found, go to end
        self.seek(len(self._state.words) - 1)

    def _update_timer_interval(self) -> None:
        """Update timer interval based on WPM and current word."""
        base_interval = 60000 / self._state.wpm

        current = self._state.current_word
        if current:
            interval = base_interval * current.pause_after
            if current.paragraph_break_after and self._settings is not None and self._settings.settings.pause_at_paragraphs:
                interval *= PAUSE_PARAGRAPH
        else:
            interval = base_interval

        self._timer.setInterval(int(interval))

    def _advance(self) -> None:
        """Advance to the next word."""
        self._state.current_index += 1

        if self._state.current_index >= len(self._state.words):
            # Reached the end
            self._state.current_index = len(self._state.words) - 1
            self.pause()
            self.progress_changed.emit(self._state.progress)
            self.finished.emit()
            return

        self.word_changed.emit(self._state.current_word)
        self.progress_changed.emit(self._state.progress)
        self._update_timer_interval()
