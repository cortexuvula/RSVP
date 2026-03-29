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
        # 2 / (4-1) * 100 = 66.67%
        assert state.progress == pytest.approx(66.67, abs=0.01)

    def test_progress_at_end(self):
        words = process_text("one two three four")
        state = RSVPState(words=words, current_index=3)  # last valid index
        assert state.progress == 100.0

    def test_progress_single_word(self):
        words = process_text("hello")
        state = RSVPState(words=words, current_index=0)
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
        engine.seek(1)  # at last word (index 1 of 2 words)
        engine.play()
        assert engine.current_index == 0


class TestRSVPEngineSeekPercent:
    """Tests for seek_percent edge cases after formula change."""

    def test_seek_percent_100(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three four")  # 4 words, indices 0-3
        engine.seek_percent(100)
        assert engine.current_index == 3  # last word

    def test_seek_percent_single_word(self, qapp):
        engine = RSVPEngine()
        engine.load_text("hello")
        engine.seek_percent(50)
        assert engine.current_index == 0

    def test_seek_percent_empty_text(self, qapp):
        engine = RSVPEngine()
        engine.seek_percent(50)  # should not crash
        assert engine.current_index == 0

    def test_seek_percent_roundtrip(self, qapp):
        """Seeking to a progress percentage should land at the index that produces that percentage."""
        engine = RSVPEngine()
        engine.load_text("one two three four five")  # 5 words, indices 0-4
        # Progress at index 2 = 2/4 * 100 = 50%
        engine.seek_percent(50)
        assert engine.current_index == 2
        assert engine.state.progress == pytest.approx(50.0)

    def test_seek_percent_two_words(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek_percent(0)
        assert engine.current_index == 0
        engine.seek_percent(100)
        assert engine.current_index == 1


class TestRSVPEngineSignals:
    """Tests for signal emissions."""

    def test_load_text_emits_word_changed(self, qapp):
        engine = RSVPEngine()
        received = []
        engine.word_changed.connect(lambda w: received.append(w))
        engine.load_text("Hello world")
        assert len(received) == 1
        assert received[0].text == "Hello"

    def test_load_text_emits_none_for_empty(self, qapp):
        engine = RSVPEngine()
        received = []
        engine.word_changed.connect(lambda w: received.append(w))
        engine.load_text("")
        assert len(received) == 1
        assert received[0] is None

    def test_load_text_emits_state_changed(self, qapp):
        engine = RSVPEngine()
        count = []
        engine.state_changed.connect(lambda: count.append(1))
        engine.load_text("Hello")
        assert len(count) >= 1

    def test_load_text_emits_progress_zero(self, qapp):
        engine = RSVPEngine()
        values = []
        engine.progress_changed.connect(lambda v: values.append(v))
        engine.load_text("Hello world")
        assert 0.0 in values

    def test_play_emits_state_changed(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")
        count = []
        engine.state_changed.connect(lambda: count.append(1))
        engine.play()
        assert len(count) >= 1

    def test_pause_emits_state_changed(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")
        engine.play()
        count = []
        engine.state_changed.connect(lambda: count.append(1))
        engine.pause()
        assert len(count) >= 1

    def test_stop_emits_word_changed_and_progress(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        engine.seek(2)
        words = []
        progress = []
        engine.word_changed.connect(lambda w: words.append(w))
        engine.progress_changed.connect(lambda p: progress.append(p))
        engine.stop()
        assert len(words) >= 1
        assert words[-1].text == "one"  # reset to first word
        assert 0.0 in progress

    def test_seek_emits_word_and_progress(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        words = []
        progress = []
        engine.word_changed.connect(lambda w: words.append(w))
        engine.progress_changed.connect(lambda p: progress.append(p))
        engine.seek(1)
        assert words[-1].text == "two"
        assert len(progress) >= 1


class TestRSVPEngineAdvance:
    """Tests for _advance() — the core playback method."""

    def test_advance_moves_to_next_word(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        assert engine.current_index == 0
        engine._advance()
        assert engine.current_index == 1

    def test_advance_emits_word_changed(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        words = []
        engine.word_changed.connect(lambda w: words.append(w))
        engine._advance()
        assert words[-1].text == "two"

    def test_advance_emits_progress(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two three")
        progress = []
        engine.progress_changed.connect(lambda p: progress.append(p))
        engine._advance()
        assert len(progress) >= 1
        assert progress[-1] == pytest.approx(50.0)  # 1/(3-1)*100

    def test_advance_past_end_emits_finished(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek(1)  # at last word
        finished = []
        engine.finished.connect(lambda: finished.append(True))
        engine._state.is_playing = True  # simulate playing state for pause()
        engine._advance()
        assert len(finished) == 1

    def test_advance_past_end_pauses(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek(1)
        engine._state.is_playing = True
        engine._advance()
        assert engine.is_playing is False

    def test_advance_past_end_clamps_index(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek(1)
        engine._state.is_playing = True
        engine._advance()
        assert engine.current_index == 1  # stays at last, not beyond

    def test_advance_past_end_emits_100_progress(self, qapp):
        engine = RSVPEngine()
        engine.load_text("one two")
        engine.seek(1)
        progress = []
        engine.progress_changed.connect(lambda p: progress.append(p))
        engine._state.is_playing = True
        engine._advance()
        assert progress[-1] == 100.0

    def test_advance_full_playthrough(self, qapp):
        """Simulate a full playthrough by calling _advance repeatedly."""
        engine = RSVPEngine()
        engine.load_text("one two three")
        words = []
        engine.word_changed.connect(lambda w: words.append(w))
        finished = []
        engine.finished.connect(lambda: finished.append(True))

        engine._state.is_playing = True
        engine._advance()  # index 0 -> 1
        engine._advance()  # index 1 -> 2
        engine._advance()  # index 2 -> 3 (past end) -> finish

        assert [w.text for w in words] == ["two", "three"]
        assert len(finished) == 1
        assert engine.current_index == 2
        assert engine.is_playing is False


class TestRSVPEngineTimerInterval:
    """Tests for timer interval calculation."""

    def test_update_timer_interval_base(self, qapp):
        engine = RSVPEngine()
        engine.load_text("hello")
        engine._state.wpm = 300
        engine._update_timer_interval()
        # 60000 / 300 = 200ms base, "hello" has pause_after=1.0
        assert engine._timer.interval() == 200

    def test_update_timer_interval_with_punctuation(self, qapp):
        engine = RSVPEngine()
        engine.load_text("end.")
        engine._state.wpm = 300
        engine._update_timer_interval()
        # 200ms * 2.5 = 500ms for sentence-ending punctuation
        assert engine._timer.interval() == 500

    def test_wpm_change_while_playing_updates_timer(self, qapp):
        engine = RSVPEngine()
        engine.load_text("hello world")
        engine.play()
        initial_interval = engine._timer.interval()
        engine.wpm = 600
        new_interval = engine._timer.interval()
        assert new_interval < initial_interval
        engine.pause()


class TestRSVPStateTimeRemaining:
    """Tests for time_remaining_seconds with pause multipliers."""

    def test_time_remaining_accounts_for_punctuation(self):
        words = process_text("Hello world.")
        # "Hello" pause=1.0, "world." pause=2.5
        state = RSVPState(words=words, current_index=0, wpm=300)
        base = 60.0 / 300  # 0.2 seconds per base word
        expected = base * 1.0 + base * 2.5  # 0.2 + 0.5 = 0.7
        assert state.time_remaining_seconds == pytest.approx(expected)

    def test_time_remaining_from_middle(self):
        words = process_text("Hello world.")
        state = RSVPState(words=words, current_index=1, wpm=300)
        base = 60.0 / 300
        expected = base * 2.5  # only "world." remaining
        assert state.time_remaining_seconds == pytest.approx(expected)

    def test_time_remaining_at_end(self):
        words = process_text("one two three")
        state = RSVPState(words=words, current_index=3)
        state.wpm = 300
        assert state.time_remaining_seconds == 0.0

    def test_time_remaining_empty(self):
        state = RSVPState(wpm=300)
        assert state.time_remaining_seconds == 0.0


class TestRSVPEngineLoadTextReplace:
    """Tests for loading new text when text is already loaded."""

    def test_load_replaces_previous_text(self, qapp):
        engine = RSVPEngine()
        engine.load_text("old text here")
        engine.seek(2)
        engine.load_text("new words")
        assert engine.word_count == 2
        assert engine.current_index == 0
        assert engine.state.current_word.text == "new"

    def test_load_stops_playback(self, qapp):
        engine = RSVPEngine()
        engine.load_text("some text here")
        engine.play()
        assert engine.is_playing is True
        engine.load_text("different text")
        assert engine.is_playing is False

    def test_load_after_empty(self, qapp):
        engine = RSVPEngine()
        engine.load_text("")
        assert engine.word_count == 0
        engine.load_text("hello")
        assert engine.word_count == 1


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

    def test_previous_sentence_from_sentence_start(self, qapp):
        """Pressing previous_sentence at start of second sentence should go to first."""
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence. Third sentence.")
        # "First"=0, "sentence."=1, "Second"=2, "sentence."=3, "Third"=4, "sentence."=5
        engine.seek(2)  # at "Second" - first word of second sentence
        engine.previous_sentence()
        assert engine.current_index == 0
        assert engine.state.current_word.text == "First"

    def test_previous_sentence_from_third_sentence_start(self, qapp):
        """From start of third sentence, should go to start of second."""
        engine = RSVPEngine()
        engine.load_text("First sentence. Second sentence. Third sentence.")
        engine.seek(4)  # at "Third"
        engine.previous_sentence()
        assert engine.current_index == 2
        assert engine.state.current_word.text == "Second"

    def test_navigation_empty_text(self, qapp):
        engine = RSVPEngine()
        engine.next_sentence()  # should not crash
        engine.previous_sentence()  # should not crash
        assert engine.current_index == 0
