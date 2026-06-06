"""Built-in theme presets for the reader display."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    text_color: str
    orp_color: str
    background_color: str
    font_family: str


THEMES: dict[str, Theme] = {
    "Dark": Theme(
        name="Dark",
        text_color="#FFFFFF",
        orp_color="#FF6B6B",
        background_color="#1E1E1E",
        font_family="Arial",
    ),
    "Light": Theme(
        name="Light",
        text_color="#1A1A1A",
        orp_color="#C0392B",
        background_color="#FAFAFA",
        font_family="Arial",
    ),
    "Sepia": Theme(
        name="Sepia",
        text_color="#5B4636",
        orp_color="#A0522D",
        background_color="#F4ECD8",
        font_family="Georgia",
    ),
    "Solarized Light": Theme(
        name="Solarized Light",
        text_color="#586E75",
        orp_color="#B58900",
        background_color="#FDF6E3",
        font_family="Arial",
    ),
}

DEFAULT_THEME_NAME = "Dark"
THEME_NAMES: list[str] = list(THEMES.keys())
CUSTOM_THEME_SENTINEL = "Custom"


def get_theme(name: str) -> Theme:
    """Return the named theme, or the default if not found."""
    return THEMES.get(name, THEMES[DEFAULT_THEME_NAME])
