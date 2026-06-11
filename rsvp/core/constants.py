"""Module-level constants for the RSVP application."""

# Words-per-minute bounds
WPM_MIN = 50
WPM_MAX = 2000
WPM_DEFAULT = 300
WPM_STEP = 25
WPM_SLIDER_MAX = 1000

# Skip-by-N-words for keyboard navigation
DEFAULT_SKIP_WORDS = 10

# Pause multipliers applied to the base inter-word interval
PAUSE_SENTENCE = 2.5
PAUSE_CLAUSE = 1.5
PAUSE_TRAILING_PUNCTUATION = 1.2
PAUSE_PARAGRAPH = 3.0

# Font size range (points) used by the display
FONT_SIZE_MIN = 12
FONT_SIZE_MAX = 120

# URL fetching
ALLOWED_URL_SCHEMES = ("http", "https")
URL_FETCH_TIMEOUT_SECONDS = 10

# Preview length when loading from file/URL in the text input dialog
PREVIEW_MAX_CHARS = 5000

# File dialog filter for open-file dialogs
FILE_DIALOG_FILTER = (
    "All Supported (*.txt *.md *.html *.htm *.epub *.pdf);;"
    "Text (*.txt);;"
    "Markdown (*.md);;"
    "HTML (*.html *.htm);;"
    "EPUB (*.epub);;"
    "PDF (*.pdf);;"
    "All Files (*)"
)
