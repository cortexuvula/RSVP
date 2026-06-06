"""Text processing utilities for RSVP."""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from rsvp.core.constants import (
    ALLOWED_URL_SCHEMES,
    PAUSE_CLAUSE,
    PAUSE_SENTENCE,
    PAUSE_TRAILING_PUNCTUATION,
    URL_FETCH_TIMEOUT_SECONDS,
)


@dataclass
class Word:
    """Represents a word with its optimal recognition point (ORP)."""

    text: str
    orp_index: int  # Index of the optimal recognition point character
    pause_after: float  # Multiplier for pause duration after this word
    paragraph_break_after: bool = False

    @property
    def before_orp(self) -> str:
        """Text before the ORP character."""
        return self.text[: self.orp_index]

    @property
    def orp_char(self) -> str:
        """The ORP character."""
        return self.text[self.orp_index] if self.orp_index < len(self.text) else ""

    @property
    def after_orp(self) -> str:
        """Text after the ORP character."""
        return self.text[self.orp_index + 1 :] if self.orp_index < len(self.text) else ""


def calculate_orp(word: str) -> int:
    """
    Calculate the Optimal Recognition Point (ORP) for a word.

    The ORP is the character position where the eye naturally focuses.
    Research suggests this is typically around 1/3 into the word,
    slightly left of center.
    """
    length = len(word)
    if length <= 1:
        return 0
    elif length <= 3:
        return 0
    elif length <= 5:
        return 1
    elif length <= 9:
        return 2
    elif length <= 13:
        return 3
    else:
        return 4


def calculate_pause_multiplier(word: str) -> float:
    """
    Calculate pause multiplier based on punctuation.

    Longer pauses after sentences, shorter pauses after commas, etc.
    """
    if not word:
        return 1.0

    last_char = word[-1]

    if last_char in ".!?":
        return PAUSE_SENTENCE
    elif last_char in ",;:":
        return PAUSE_CLAUSE
    elif last_char in "\"')":
        if len(word) > 1 and word[-2] in ".!?":
            return PAUSE_SENTENCE
        return PAUSE_TRAILING_PUNCTUATION

    return 1.0


def strip_markdown(text: str) -> str:
    """Strip Markdown syntax, keeping readable text."""
    # Code blocks (fenced)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Images (keep alt text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # Links (keep link text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Bold + italic combined
    text = re.sub(r"\*{3}([^*]+)\*{3}", r"\1", text)
    text = re.sub(r"_{3}([^_]+)_{3}", r"\1", text)
    # Bold
    text = re.sub(r"\*{2}([^*]+)\*{2}", r"\1", text)
    text = re.sub(r"_{2}([^_]+)_{2}", r"\1", text)
    # Italic
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_\s]+)_", r"\1", text)
    # Horizontal rules
    text = re.sub(r"^[\-\*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text


def process_text(text: str) -> list[Word]:
    """
    Process text into a list of Word objects.

    Splits text on whitespace and calculates ORP and pause for each word.
    Detects paragraph boundaries (double newlines) and marks the last word
    of each paragraph (except the final one) with paragraph_break_after=True.
    """
    if not text or not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)

    all_words: list[Word] = []
    paragraph_end_indices: list[int] = []

    for para in paragraphs:
        normalized = re.sub(r"\s+", " ", para.strip())
        if not normalized:
            continue
        para_start = len(all_words)
        for raw_word in normalized.split():
            if raw_word:
                orp = calculate_orp(raw_word)
                pause = calculate_pause_multiplier(raw_word)
                all_words.append(Word(text=raw_word, orp_index=orp, pause_after=pause))
        if len(all_words) > para_start:
            paragraph_end_indices.append(len(all_words) - 1)

    for idx in paragraph_end_indices[:-1]:
        all_words[idx].paragraph_break_after = True

    return all_words


def process_text_into_chunks(text: str, chunk_size: int) -> list[Word]:
    """Group `text` into chunks of `chunk_size` words, aligned to paragraph boundaries.

    Each chunk becomes a Word with:
      - .text: the joined words (e.g., "the quick brown")
      - .orp_index: the ORP of the FIRST word in the chunk (single focal point)
      - .pause_after: the pause multiplier of the LAST word in the chunk
      - .paragraph_break_after: True if this chunk ends a paragraph

    Paragraph breaks (\\n\\n) never fall mid-chunk. The last chunk of a
    paragraph may be shorter than chunk_size if the paragraph's word
    count doesn't divide evenly.

    Empty input returns an empty list. chunk_size <= 1 falls through to
    process_text() (no grouping).
    """
    if chunk_size <= 1:
        return process_text(text)
    if not text or not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    all_chunks: list[Word] = []
    paragraph_end_indices: list[int] = []

    for para in paragraphs:
        normalized = re.sub(r"\s+", " ", para.strip())
        if not normalized:
            continue
        words = normalized.split(" ")
        para_start = len(all_chunks)
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            if not chunk_words:
                continue
            chunk_text = " ".join(chunk_words)
            first_word = chunk_words[0]
            orp_idx = calculate_orp(first_word)
            last_word = chunk_words[-1]
            pause_mult = calculate_pause_multiplier(last_word)
            all_chunks.append(
                Word(
                    text=chunk_text,
                    orp_index=orp_idx,
                    pause_after=pause_mult,
                )
            )
        if len(all_chunks) > para_start:
            paragraph_end_indices.append(len(all_chunks) - 1)

    for idx in paragraph_end_indices[:-1]:
        all_chunks[idx].paragraph_break_after = True

    return all_chunks


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
        element.decompose()

    BLOCK_TAGS = {
        "p",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "blockquote",
        "pre",
        "tr",
        "br",
        "hr",
        "section",
        "article",
        "main",
    }
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n\n")

    text = soup.get_text()
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r" *\n", "\n", text)
    return text.strip()


def load_text_from_file(filepath: str) -> str:
    """Load text from a file, dispatching by extension."""
    ext = Path(filepath).suffix.lower()

    if ext == ".md":
        with open(filepath, encoding="utf-8") as f:
            return strip_markdown(f.read())
    elif ext in (".html", ".htm"):
        with open(filepath, encoding="utf-8") as f:
            return extract_text_from_html(f.read())
    elif ext == ".epub":
        return load_text_from_epub(filepath)
    elif ext == ".pdf":
        return load_text_from_pdf(filepath)
    else:
        with open(filepath, encoding="utf-8") as f:
            return f.read()


def load_text_from_epub(filepath: str) -> str:
    """Load text from an EPUB file."""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError as e:
        raise ValueError("EPUB support requires 'ebooklib'. Install with: pip install ebooklib") from e

    book = epub.read_epub(filepath)
    chapters = []

    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_content().decode("utf-8", errors="replace")
            text = extract_text_from_html(content)
            if text.strip():
                chapters.append(text.strip())

    if not chapters:
        raise ValueError("No readable text found in EPUB file")

    return "\n\n".join(chapters)


def load_text_from_pdf(filepath: str) -> str:
    """Load text from a PDF file."""
    try:
        import fitz
    except ImportError as e:
        raise ValueError("PDF support requires 'pymupdf'. Install with: pip install pymupdf") from e

    with fitz.open(filepath) as doc:
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text.strip())

    if not pages:
        raise ValueError("No readable text found in PDF file")

    return "\n\n".join(pages)


def fetch_text_from_url(url: str) -> str:
    """Fetch and extract text from an HTTP(S) URL.

    Raises ValueError for empty input or non-http(s) schemes (e.g. file://, ftp://,
    javascript:) so that user input cannot be coerced into reading local files or
    other protocols.
    """
    if not url or not url.strip():
        raise ValueError("URL is empty")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"Only {', '.join(s + '://' for s in ALLOWED_URL_SCHEMES)} URLs are supported "
            f"(got {parsed.scheme + '://' if parsed.scheme else 'no scheme'})"
        )
    if not parsed.netloc:
        raise ValueError("URL has no host")

    import requests

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    response = requests.get(url, headers=headers, timeout=URL_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()

    return extract_text_from_html(response.text)
