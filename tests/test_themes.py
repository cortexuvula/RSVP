"""Tests for the themes module."""

import re

from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    get_theme,
)


def test_all_4_themes_defined():
    assert set(THEMES.keys()) == {"Dark", "Light", "Sepia", "Solarized Light"}


def test_default_theme_is_dark():
    assert DEFAULT_THEME_NAME == "Dark"
    assert DEFAULT_THEME_NAME in THEMES


def test_theme_names_in_expected_order():
    assert THEME_NAMES == ["Dark", "Light", "Sepia", "Solarized Light"]


def test_get_theme_returns_default_for_unknown():
    theme = get_theme("NonexistentTheme")
    assert theme.name == DEFAULT_THEME_NAME


def test_get_theme_returns_named_theme():
    theme = get_theme("Sepia")
    assert theme.name == "Sepia"
    assert theme.font_family == "Georgia"


def test_theme_colors_are_valid_hex():
    """All color fields should be 7-char hex strings (#RRGGBB)."""
    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for theme in THEMES.values():
        assert hex_re.match(theme.text_color), f"{theme.name}.text_color not valid hex"
        assert hex_re.match(theme.orp_color), f"{theme.name}.orp_color not valid hex"
        assert hex_re.match(theme.background_color), f"{theme.name}.background_color not valid hex"


def test_custom_sentinel_not_a_real_theme():
    """CUSTOM_THEME_SENTINEL is a UI-only marker; it shouldn't be in THEMES."""
    assert CUSTOM_THEME_SENTINEL not in THEMES
    # get_theme falls back to default for unknown names
    theme = get_theme(CUSTOM_THEME_SENTINEL)
    assert theme.name == DEFAULT_THEME_NAME


def test_theme_is_immutable():
    """Theme is a frozen dataclass — cannot mutate after construction."""
    theme = get_theme("Dark")
    try:
        theme.text_color = "#000000"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Theme should be frozen")
