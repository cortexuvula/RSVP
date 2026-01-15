"""Tests for text_processor module."""
import pytest
from rsvp.core.text_processor import (
    Word,
    calculate_orp,
    calculate_pause_multiplier,
    process_text,
    extract_text_from_html,
)


class TestCalculateORP:
    """Tests for ORP (Optimal Recognition Point) calculation."""

    def test_single_char(self):
        assert calculate_orp("a") == 0

    def test_empty_string(self):
        assert calculate_orp("") == 0

    def test_two_chars(self):
        assert calculate_orp("ab") == 0

    def test_three_chars(self):
        assert calculate_orp("the") == 0

    def test_four_chars(self):
        assert calculate_orp("word") == 1

    def test_five_chars(self):
        assert calculate_orp("hello") == 1

    def test_six_chars(self):
        assert calculate_orp("system") == 2

    def test_nine_chars(self):
        assert calculate_orp("beautiful") == 2

    def test_ten_chars(self):
        assert calculate_orp("understood") == 3

    def test_thirteen_chars(self):
        assert calculate_orp("communication") == 3

    def test_fourteen_chars(self):
        assert calculate_orp("representation") == 4

    def test_very_long_word(self):
        assert calculate_orp("internationalization") == 4


class TestCalculatePauseMultiplier:
    """Tests for pause multiplier calculation based on punctuation."""

    def test_regular_word(self):
        assert calculate_pause_multiplier("word") == 1.0

    def test_empty_string(self):
        assert calculate_pause_multiplier("") == 1.0

    def test_period(self):
        assert calculate_pause_multiplier("end.") == 2.5

    def test_exclamation(self):
        assert calculate_pause_multiplier("wow!") == 2.5

    def test_question(self):
        assert calculate_pause_multiplier("what?") == 2.5

    def test_comma(self):
        assert calculate_pause_multiplier("however,") == 1.5

    def test_semicolon(self):
        assert calculate_pause_multiplier("first;") == 1.5

    def test_colon(self):
        assert calculate_pause_multiplier("note:") == 1.5

    def test_closing_quote(self):
        assert calculate_pause_multiplier('said"') == 1.2

    def test_closing_paren(self):
        assert calculate_pause_multiplier("(aside)") == 1.2

    def test_quote_after_period(self):
        assert calculate_pause_multiplier('done."') == 2.5

    def test_quote_after_exclamation(self):
        assert calculate_pause_multiplier('great!"') == 2.5

    def test_paren_after_question(self):
        assert calculate_pause_multiplier("really?)") == 2.5


class TestWord:
    """Tests for Word dataclass."""

    def test_before_orp(self):
        word = Word(text="hello", orp_index=2, pause_after=1.0)
        assert word.before_orp == "he"

    def test_orp_char(self):
        word = Word(text="hello", orp_index=2, pause_after=1.0)
        assert word.orp_char == "l"

    def test_after_orp(self):
        word = Word(text="hello", orp_index=2, pause_after=1.0)
        assert word.after_orp == "lo"

    def test_orp_at_start(self):
        word = Word(text="hi", orp_index=0, pause_after=1.0)
        assert word.before_orp == ""
        assert word.orp_char == "h"
        assert word.after_orp == "i"

    def test_orp_at_end(self):
        word = Word(text="ab", orp_index=1, pause_after=1.0)
        assert word.before_orp == "a"
        assert word.orp_char == "b"
        assert word.after_orp == ""

    def test_orp_index_out_of_bounds(self):
        word = Word(text="hi", orp_index=5, pause_after=1.0)
        assert word.orp_char == ""
        assert word.after_orp == ""

    def test_single_char_word(self):
        word = Word(text="I", orp_index=0, pause_after=1.0)
        assert word.before_orp == ""
        assert word.orp_char == "I"
        assert word.after_orp == ""


class TestProcessText:
    """Tests for process_text function."""

    def test_simple_sentence(self):
        words = process_text("Hello world")
        assert len(words) == 2
        assert words[0].text == "Hello"
        assert words[1].text == "world"

    def test_empty_string(self):
        words = process_text("")
        assert words == []

    def test_whitespace_only(self):
        words = process_text("   \n\t  ")
        assert words == []

    def test_normalizes_whitespace(self):
        words = process_text("Hello   \n\t  world")
        assert len(words) == 2

    def test_preserves_punctuation(self):
        words = process_text("Hello, world!")
        assert words[0].text == "Hello,"
        assert words[1].text == "world!"

    def test_calculates_orp(self):
        words = process_text("I am reading")
        assert words[0].orp_index == 0  # "I" - single char
        assert words[1].orp_index == 0  # "am" - 2 chars
        assert words[2].orp_index == 2  # "reading" - 7 chars

    def test_calculates_pause(self):
        words = process_text("Hello. How are you?")
        assert words[0].pause_after == 2.5  # "Hello."
        assert words[1].pause_after == 1.0  # "How"
        assert words[2].pause_after == 1.0  # "are"
        assert words[3].pause_after == 2.5  # "you?"

    def test_sentence_with_comma(self):
        words = process_text("First, second")
        assert words[0].pause_after == 1.5  # comma
        assert words[1].pause_after == 1.0  # no punctuation

    def test_long_text(self):
        text = "The quick brown fox jumps over the lazy dog."
        words = process_text(text)
        assert len(words) == 9
        assert words[-1].pause_after == 2.5  # ends with period


class TestExtractTextFromHTML:
    """Tests for HTML text extraction."""

    def test_simple_html(self):
        html = "<p>Hello world</p>"
        text = extract_text_from_html(html)
        assert text == "Hello world"

    def test_removes_script_tags(self):
        html = "<p>Hello</p><script>alert('bad')</script><p>world</p>"
        text = extract_text_from_html(html)
        assert "alert" not in text
        assert "Hello" in text
        assert "world" in text

    def test_removes_style_tags(self):
        html = "<style>.foo { color: red; }</style><p>Content</p>"
        text = extract_text_from_html(html)
        assert "color" not in text
        assert "Content" in text

    def test_removes_nav_tags(self):
        html = "<nav>Menu items</nav><main>Main content</main>"
        text = extract_text_from_html(html)
        assert "Main content" in text

    def test_normalizes_whitespace(self):
        html = "<p>Hello</p>   <p>world</p>"
        text = extract_text_from_html(html)
        assert "  " not in text

    def test_empty_html(self):
        text = extract_text_from_html("")
        assert text == ""

    def test_nested_tags(self):
        html = "<div><p><span>Nested</span> content</p></div>"
        text = extract_text_from_html(html)
        assert "Nested" in text
        assert "content" in text
