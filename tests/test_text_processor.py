"""Tests for text_processor module."""
import os
import pytest
from rsvp.core.text_processor import (
    Word,
    calculate_orp,
    calculate_pause_multiplier,
    process_text,
    extract_text_from_html,
    load_text_from_file,
    strip_markdown,
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


class TestLoadTextFromFile:
    """Tests for load_text_from_file function."""

    def test_load_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello world from file", encoding="utf-8")
        text = load_text_from_file(str(f))
        assert text == "Hello world from file"

    def test_load_utf8_file(self, tmp_path):
        f = tmp_path / "utf8.txt"
        f.write_text("Héllo wörld", encoding="utf-8")
        text = load_text_from_file(str(f))
        assert "Héllo" in text

    def test_load_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        text = load_text_from_file(str(f))
        assert text == ""

    def test_load_multiline_file(self, tmp_path):
        f = tmp_path / "multi.txt"
        f.write_text("Line one\nLine two\nLine three", encoding="utf-8")
        text = load_text_from_file(str(f))
        assert "Line one" in text
        assert "Line three" in text

    def test_load_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_text_from_file("/nonexistent/path/file.txt")


class TestParagraphBreakDetection:
    """Tests for paragraph break detection in process_text."""

    def test_no_paragraph_breaks(self):
        words = process_text("Hello world")
        assert all(w.paragraph_break_after is False for w in words)

    def test_single_paragraph_break(self):
        words = process_text("First paragraph.\n\nSecond paragraph.")
        assert words[1].paragraph_break_after is True
        assert words[1].text == "paragraph."
        assert words[0].paragraph_break_after is False
        assert words[2].paragraph_break_after is False
        assert words[3].paragraph_break_after is False

    def test_multiple_paragraph_breaks(self):
        words = process_text("One.\n\nTwo.\n\nThree.")
        assert words[0].paragraph_break_after is True   # "One."
        assert words[1].paragraph_break_after is True   # "Two."
        assert words[2].paragraph_break_after is False   # "Three." (last paragraph)

    def test_last_paragraph_not_marked(self):
        words = process_text("First para.\n\nSecond para.")
        last_word = words[-1]
        assert last_word.paragraph_break_after is False

    def test_extra_blank_lines(self):
        words = process_text("One.\n\n\n\nTwo.")
        assert words[0].paragraph_break_after is True

    def test_blank_line_with_spaces(self):
        words = process_text("One.\n   \nTwo.")
        assert words[0].paragraph_break_after is True

    def test_preserves_existing_word_properties(self):
        words = process_text("Hello.\n\nWorld!")
        assert words[0].text == "Hello."
        assert words[0].pause_after == 2.5
        assert words[0].orp_index == 2  # "Hello." is 6 chars -> orp index 2
        assert words[1].text == "World!"
        assert words[1].pause_after == 2.5

    def test_empty_paragraph_skipped(self):
        words = process_text("\n\nHello\n\n")
        assert len(words) == 1
        assert words[0].text == "Hello"
        assert words[0].paragraph_break_after is False

    def test_single_word_paragraph(self):
        words = process_text("One.\n\nTwo.\n\nThree.")
        assert len(words) == 3
        assert words[0].text == "One."
        assert words[0].paragraph_break_after is True


class TestStripMarkdown:
    """Tests for Markdown syntax stripping."""

    def test_strips_h1(self):
        assert strip_markdown("# Hello World").strip() == "Hello World"

    def test_strips_h3(self):
        assert strip_markdown("### Section Title").strip() == "Section Title"

    def test_strips_bold(self):
        assert "important" in strip_markdown("This is **important** text")
        assert "**" not in strip_markdown("This is **important** text")

    def test_strips_italic(self):
        assert "emphasis" in strip_markdown("This is *emphasis* here")
        assert strip_markdown("This is *emphasis* here").count("*") == 0

    def test_strips_underscore_bold(self):
        result = strip_markdown("This is __bold__ text")
        assert "bold" in result
        assert "__" not in result

    def test_strips_links_keeps_text(self):
        result = strip_markdown("Click [here](https://example.com) please")
        assert "here" in result
        assert "https://example.com" not in result
        assert "[" not in result

    def test_strips_images_keeps_alt(self):
        result = strip_markdown("An image ![alt text](img.png) follows")
        assert "alt text" in result
        assert "img.png" not in result

    def test_strips_inline_code(self):
        result = strip_markdown("Run `npm install` now")
        assert "npm install" in result
        assert "`" not in result

    def test_strips_code_blocks(self):
        md = "Before\n```python\nprint('hello')\n```\nAfter"
        result = strip_markdown(md)
        assert "Before" in result
        assert "After" in result
        assert "```" not in result

    def test_strips_horizontal_rules(self):
        result = strip_markdown("Above\n---\nBelow")
        assert "Above" in result
        assert "Below" in result
        assert "---" not in result

    def test_strips_html_tags(self):
        result = strip_markdown("Some <em>html</em> content")
        assert "html" in result
        assert "<em>" not in result

    def test_preserves_plain_text(self):
        text = "This is plain text with no markdown."
        assert strip_markdown(text).strip() == text

    def test_empty_string(self):
        assert strip_markdown("") == ""


class TestFileFormatDispatch:
    """Tests for load_text_from_file format routing."""

    def test_loads_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Plain text content", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert result == "Plain text content"

    def test_loads_markdown(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Title" in result
        assert "**" not in result
        assert "#" not in result

    def test_loads_html(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html><body><p>Hello world</p></body></html>", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Hello world" in result
        assert "<p>" not in result

    def test_loads_htm(self, tmp_path):
        f = tmp_path / "test.htm"
        f.write_text("<p>HTM content</p>", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "HTM content" in result

    def test_unknown_extension_reads_as_text(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("raw content", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert result == "raw content"

    def test_case_insensitive_extension(self, tmp_path):
        f = tmp_path / "test.MD"
        f.write_text("# Header\n\nContent", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Header" in result
        assert "#" not in result


class TestLoadEpub:
    """Tests for EPUB file loading."""

    @pytest.fixture
    def epub_path(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "test.epub")
        if not os.path.exists(path):
            pytest.skip("test.epub fixture not found")
        return path

    def test_loads_epub_text(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "Chapter One" in result
        assert "First chapter content" in result

    def test_epub_has_multiple_chapters(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "Chapter One" in result
        assert "Chapter Two" in result
        assert "Second chapter content" in result

    def test_epub_strips_html(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "<html>" not in result
        assert "<body>" not in result
        assert "<h1>" not in result

    def test_epub_chapters_separated(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "\n\n" in result


class TestLoadPdf:
    """Tests for PDF file loading."""

    @pytest.fixture
    def pdf_path(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "test.pdf")
        if not os.path.exists(path):
            pytest.skip("test.pdf fixture not found")
        return path

    def test_loads_pdf_text(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "Page one content" in result

    def test_pdf_has_multiple_pages(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "Page one content" in result
        assert "Page two content" in result

    def test_pdf_pages_separated(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "\n\n" in result
