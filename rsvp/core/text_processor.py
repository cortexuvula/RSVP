"""Text processing utilities for RSVP."""

import ipaddress
import logging
import re
import socket
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

logger = logging.getLogger(__name__)

# Private / reserved IP ranges that should never be fetched (SSRF protection)
_RESERVED_NETWORKS_V4 = [
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("10.0.0.0/8"),  # private
    ipaddress.ip_network("172.16.0.0/12"),  # private
    ipaddress.ip_network("192.168.0.0/16"),  # private
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("0.0.0.0/8"),  # "this" network
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments (RFC 6890)
]
_RESERVED_NETWORKS_V6 = [
    ipaddress.ip_network("::1/128"),  # loopback
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local
]


def _is_reserved_ip(addr: str) -> bool:
    """Return True if *addr* falls in a private / reserved IP range."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True  # unparseable → treat as reserved
    if ip.version == 4:
        return any(ip in net for net in _RESERVED_NETWORKS_V4)
    # For IPv6, also check IPv4-mapped addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return any(ip.ipv4_mapped in net for net in _RESERVED_NETWORKS_V4)
    return any(ip in net for net in _RESERVED_NETWORKS_V6)


def _check_url_not_private(hostname: str) -> None:
    """Resolve *hostname* and raise ValueError if any result is in a reserved range."""
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}': {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrinfos:
        ip_str = str(sockaddr[0])
        if _is_reserved_ip(ip_str):
            raise ValueError(
                f"URL resolves to a private/reserved IP address ({ip_str}); fetching is not allowed"
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
    return min(length // 3, 4)


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
    """Strip Markdown syntax, keeping readable text for RSVP display."""
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
    # Horizontal rules (before bold/italic to avoid false positives on ---)
    text = re.sub(r"^[\-\*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Strip all markdown formatting characters (*, _, ~, `) but keep content
    text = re.sub(r"[*_~`]+", "", text)
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

    # Normalize CRLF / CR to LF so the paragraph regex matches consistently
    text = text.replace("\r\n", "\n").replace("\r", "\n")

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


def _read_file_with_fallback(filepath: str) -> str:
    """Read a file as UTF-8, falling back to replacement mode on decode errors."""
    try:
        with open(filepath, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        logger.warning("File %s is not valid UTF-8; reading with replacement characters", filepath)
        with open(filepath, encoding="utf-8", errors="replace") as f:
            return f.read()


def load_text_from_file(filepath: str) -> str:
    """Load text from a file, dispatching by extension."""
    ext = Path(filepath).suffix.lower()
    logger.debug("load_text_from_file dispatch for extension %s", ext or "(none)")

    if ext == ".md":
        return strip_markdown(_read_file_with_fallback(filepath))
    elif ext in (".html", ".htm"):
        return extract_text_from_html(_read_file_with_fallback(filepath))
    elif ext == ".epub":
        return load_text_from_epub(filepath)
    elif ext == ".pdf":
        return load_text_from_pdf(filepath)
    else:
        return _read_file_with_fallback(filepath)


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
    other protocols.  Also validates that the resolved IP is not in a private or
    reserved range (SSRF protection).
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

    # SSRF protection: verify the hostname doesn't resolve to a private IP
    _check_url_not_private(parsed.hostname or parsed.netloc)

    import requests

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    response = requests.get(url, headers=headers, timeout=URL_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()

    return extract_text_from_html(response.text)
