"""Text processing utilities for RSVP."""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Word:
    """Represents a word with its optimal recognition point (ORP)."""
    text: str
    orp_index: int  # Index of the optimal recognition point character
    pause_after: float  # Multiplier for pause duration after this word

    @property
    def before_orp(self) -> str:
        """Text before the ORP character."""
        return self.text[:self.orp_index]

    @property
    def orp_char(self) -> str:
        """The ORP character."""
        return self.text[self.orp_index] if self.orp_index < len(self.text) else ""

    @property
    def after_orp(self) -> str:
        """Text after the ORP character."""
        return self.text[self.orp_index + 1:] if self.orp_index < len(self.text) else ""


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

    # End of sentence
    if last_char in '.!?':
        return 2.5
    # Clause separators
    elif last_char in ',;:':
        return 1.5
    # Other punctuation
    elif last_char in '"\')':
        # Check if there's sentence-ending punctuation before
        if len(word) > 1 and word[-2] in '.!?':
            return 2.5
        return 1.2

    return 1.0


def process_text(text: str) -> list[Word]:
    """
    Process text into a list of Word objects.

    Splits text on whitespace and calculates ORP and pause for each word.
    """
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    if not text:
        return []

    words = []
    for raw_word in text.split():
        if raw_word:
            orp = calculate_orp(raw_word)
            pause = calculate_pause_multiplier(raw_word)
            words.append(Word(text=raw_word, orp_index=orp, pause_after=pause))

    return words


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')

    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        element.decompose()

    # Get text
    text = soup.get_text(separator=' ')

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def load_text_from_file(filepath: str) -> str:
    """Load text from a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def fetch_text_from_url(url: str) -> str:
    """Fetch and extract text from a URL."""
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    return extract_text_from_html(response.text)
