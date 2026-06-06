"""Core logic for RSVP application."""

import logging

from rsvp.core.constants import (
    ALLOWED_URL_SCHEMES,
    DEFAULT_SKIP_WORDS,
    FONT_SIZE_MAX,
    FONT_SIZE_MIN,
    PAUSE_CLAUSE,
    PAUSE_PARAGRAPH,
    PAUSE_SENTENCE,
    PAUSE_TRAILING_PUNCTUATION,
    PREVIEW_MAX_CHARS,
    URL_FETCH_TIMEOUT_SECONDS,
    WPM_DEFAULT,
    WPM_MAX,
    WPM_MIN,
    WPM_SLIDER_MAX,
    WPM_STEP,
)
from rsvp.core.rsvp_engine import RSVPEngine, RSVPState
from rsvp.core.settings import (
    RSVPSettings,
    SettingsManager,
    get_settings_manager,
)
from rsvp.core.stats import (
    AllTimeStats,
    DocumentStats,
    SessionRecord,
    StatsData,
    StatsManager,
)
from rsvp.core.text_processor import (
    Word,
    calculate_orp,
    calculate_pause_multiplier,
    extract_text_from_html,
    fetch_text_from_url,
    load_text_from_file,
    process_text,
    strip_markdown,
)
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    Theme,
    get_theme,
)
from rsvp.core.tts import (
    NullDriver,
    Pyttsx3Driver,
    TTSController,
    TTSDriver,
    create_tts_driver,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ALLOWED_URL_SCHEMES",
    "AllTimeStats",
    "CUSTOM_THEME_SENTINEL",
    "DEFAULT_SKIP_WORDS",
    "DEFAULT_THEME_NAME",
    "DocumentStats",
    "FONT_SIZE_MAX",
    "FONT_SIZE_MIN",
    "NullDriver",
    "PAUSE_CLAUSE",
    "PAUSE_PARAGRAPH",
    "PAUSE_SENTENCE",
    "PAUSE_TRAILING_PUNCTUATION",
    "Pyttsx3Driver",
    "PREVIEW_MAX_CHARS",
    "RSVPEngine",
    "RSVPSettings",
    "RSVPState",
    "SessionRecord",
    "SettingsManager",
    "StatsData",
    "StatsManager",
    "THEME_NAMES",
    "THEMES",
    "Theme",
    "TTSController",
    "TTSDriver",
    "URL_FETCH_TIMEOUT_SECONDS",
    "WPM_DEFAULT",
    "WPM_MAX",
    "WPM_MIN",
    "WPM_SLIDER_MAX",
    "WPM_STEP",
    "Word",
    "calculate_orp",
    "calculate_pause_multiplier",
    "create_tts_driver",
    "extract_text_from_html",
    "fetch_text_from_url",
    "get_settings_manager",
    "get_theme",
    "load_text_from_file",
    "process_text",
    "strip_markdown",
]
