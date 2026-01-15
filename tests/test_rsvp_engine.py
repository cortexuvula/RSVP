"""Tests for rsvp_engine module."""
import pytest
from rsvp.core.text_processor import Word, process_text
from rsvp.core.rsvp_engine import RSVPState, RSVPEngine


class TestRSVPState:
    """Tests for RSVPState dataclass."""

    def test_default_state(self):
        state = RSVPState()
        assert state.words == []
        assert state.current_index == 0
        assert state.wpm == 300
        assert state.is_playing is False

    def test_current_word_empty(self):
        state = RSVPState()
        assert state.current_word is None

    def test_current_word_valid(self):
        words = process_text("Hello world")
        state = RSVPState(words=words, current_index=0)
        assert state.current_word is not None
        assert state.current_word.text == "Hello"

    def test_current_word_second(self):
        words = process_text("Hello world")
        state = RSVPState(words=words, current_index=1)
        assert state.current_word.text == "world"

    def test_current_word_out_of_bounds(self):
        words = process_text("Hello world")
        state = RSVPState(words=words, current_index=10)
        assert state.current_word is None

    def test_current_word_negative_index(self):
        words = process_text("Hello world")
        state = RSVPState(words=words, current_index=-1)
        assert state.current_word is None

    def test_progress_empty(self):
        state = RSVPState()
        assert state.progress == 0.0

    def test_progress_at_start(self):
        words = process_text("one two three four")
        state = RSVPState(words=words, current_index=0)
        assert state.progress == 0.0

    def test_progress_at_middle(self):
        words = process_text("one two three four")
        state = RSVPState(words=words, current_index=2)
        assert state.progress == 50.0

    def test_progress_at_end(self):
        words = process_text("one two three four")
        state = RSVPState(words=words, current_index=4)
        assert state.progress == 100.0

    def test_words_remaining_at_start(self):
        words = process_text("one two three")
        state = RSVPState(words=words, current_index=0)
        assert state.words_remaining == 3

    def test_words_remaining_at_middle(self):
        words = process_text("one two three")
        state = RSVPState(words=words, current_index=1)
        assert state.words_remaining == 2

    def test_words_remaining_at_end(self):
        words = process_text("one two three")
        state = RSVPState(words=words, current_index=3)
        assert state.words_remaining == 0

    def test_words_remaining_empty(self):
        state = RSVPState()
        assert state.words_remaining == 0

    def test_time_remaining_at_300wpm(self):
        words = process_text("one two three")  # 3 words
        state = RSVPState(words=words, current_index=0, wpm=300)
        # 3 words / 300 wpm * 60 = 0.6 seconds
        assert state.time_remaining_seconds == pytest.approx(0.6)

    def test_time_remaining_at_600wpm(self):
        words = process_text("one two three")  # 3 words
        state = RSVPState(words=words, current_index=0, wpm=600)
        # 3 words / 600 wpm * 60 = 0.3 seconds
        assert state.time_remaining_seconds == pytest.approx(0.3)

    def test_time_remaining_zero_wpm(self):
        words = process_text("one two three")
        state = RSVPState(words=words, current_index=0, wpm=0)
        assert state.time_remaining_seconds == 0.0


class TestRSVPEngine:
    """Tests for RSVPEngine class."""

    def test_initial_state(self, qapp):
        engine = RSVPEngine()
        assert engine.wpm == 300
        assert engine.is_playing is False
        assert engine.current_index == 0
        assert engine.word_count == 0

    def test_load_text(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world test")
        assert engine.word_count == 3
        assert engine.current_index == 0

    def test_load_empty_text(self, qapp):
        engine = RSVPEngine()
        engine.load_text("")
        assert engine.word_count == 0

    def test_wpm_setter_normal(self, qapp):
        engine = RSVPEngine()
        engine.wpm = 400
        assert engine.wpm == 400

    def test_wpm_setter_min_clamp(self, qapp):
        engine = RSVPEngine()
        engine.wpm = 10
        assert engine.wpm == 50

    def test_wpm_setter_max_clamp(self, qapp):
        engine = RSVPEngine()
        engine.wpm = 5000
        assert engine.wpm == 2000

    def test_seek_valid(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three four five")
        engine.seek(2)
        assert engine.current_index == 2

    def test_seek_negative(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.seek(-5)
        assert engine.current_index == 0

    def test_seek_beyond_end(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.seek(100)
        assert engine.current_index == 2  # last valid index

    def test_seek_empty_text(self, qapp):
        engine = RSVPEngine()
        engine.seek(5)  # should not crash
        assert engine.current_index == 0

    def test_seek_percent(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three four")  # 4 words
        engine.seek_percent(50)
        assert engine.current_index == 2

    def test_seek_percent_zero(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three four")
        engine.seek_percent(0)
        assert engine.current_index == 0

    def test_skip_forward(self, qapp):
        engine = RSVPEngine()
        engine.load_text(" ".join(["word"] * 20))
        engine.seek(5)
        engine.skip_forward(10)
        assert engine.current_index == 15

    def test_skip_forward_clamps(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.skip_forward(10)
        assert engine.current_index == 2  # clamped to last

    def test_skip_backward(self, qapp):
        engine = RSVPEngine()
        engine.load_text(" ".join(["word"] * 20))
        engine.seek(15)
        engine.skip_backward(10)
        assert engine.current_index == 5

    def test_skip_backward_clamps(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.seek(1)
        engine.skip_backward(10)
        assert engine.current_index == 0  # clamped to first

    def test_play_sets_playing(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")
        engine.play()
        assert engine.is_playing is True

    def test_play_empty_does_nothing(self, qapp):
        engine = RSVPEngine()
        engine.play()
        assert engine.is_playing is False

    def test_pause(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")
        engine.play()
        engine.pause()
        assert engine.is_playing is False

    def test_stop_resets_index(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.seek(2)
        engine.stop()
        assert engine.current_index == 0
        assert engine.is_playing is False

    def test_toggle_play_pause(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")

        engine.toggle_play_pause()
        assert engine.is_playing is True

        engine.toggle_play_pause()
        assert engine.is_playing is False

    def test_play_at_end_resets(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek(2)  # at end
        engine.play()
        assert engine.current_index == 0


class TestRSVPEngineSentenceNavigation:
    """Tests for sentence navigation in RSVPEngine."""

    def test_next_sentence(self, qapp):
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence. Third.")
        engine.seek(0)
        engine.next_sentence()
        # Should be at "Second" (index 2)
        assert engine.state.current_word.text == "Second"

    def test_next_sentence_from_middle(self, qapp):
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence. Third.")
        engine.seek(1)  # at "sentence."
        engine.next_sentence()
        # Should be at "Second"
        assert engine.state.current_word.text == "Second"

    def test_next_sentence_at_end(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Only one sentence.")
        engine.seek(0)
        engine.next_sentence()
        # Should be at last word
        assert engine.current_index == engine.word_count - 1

    def test_previous_sentence(self, qapp):
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence.")
        engine.seek(3)  # at "sentence." (second one)
        engine.previous_sentence()
        # Should be at "Second"
        assert engine.state.current_word.text == "Second"

    def test_previous_sentence_at_start(self, qapp):
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence.")
        engine.seek(0)
        engine.previous_sentence()
        assert engine.current_index == 0

    def test_navigation_empty_text(self, qapp):
        engine = RSVPEngine()
        engine.next_sentence()  # should not crash
        engine.previous_sentence()  # should not crash
        assert engine.current_index == 0
