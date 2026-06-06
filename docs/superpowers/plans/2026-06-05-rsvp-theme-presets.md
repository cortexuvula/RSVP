# RSVP Theme Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 4 built-in theme presets (Dark, Light, Sepia, Solarized Light) as a single PR with 3 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-theme-presets-design.md).

**Architecture:** New `rsvp.core.themes` module with `Theme` dataclass and `THEMES` dict. `RSVPSettings.theme_name` field added (default `"Dark"`). `SettingsDialog` gets a "Theme" dropdown at the top of the Display group; selecting a theme previews the 3 colors + font family.

**Tech Stack:** Python 3.10+, PyQt6, dataclasses. No new runtime dependencies.

---

## File Structure

**Created:**
- `rsvp/core/themes.py` — `Theme` dataclass + `THEMES` dict + `THEME_NAMES` list + `DEFAULT_THEME_NAME` + `get_theme()` helper
- `tests/test_themes.py`
- `tests/test_ui_settings_dialog.py`

**Modified:**
- `rsvp/core/__init__.py` — re-export new types
- `rsvp/core/settings.py` — add `theme_name` field to `RSVPSettings`
- `rsvp/ui/settings_dialog.py` — add theme dropdown + apply logic + manual-edit detection
- `CHANGELOG.md` — `[Unreleased]` entry

---

## Task 1: Theme data model + settings field + CHANGELOG

**Files:**
- Create: `rsvp/core/themes.py`
- Modify: `rsvp/core/__init__.py`
- Modify: `rsvp/core/settings.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Create `rsvp/core/themes.py`**

```python
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
```

- [ ] **Step 2: Re-export from `rsvp/core/__init__.py`**

Add to the `from rsvp.core.settings import (...)` block (or create a new `from rsvp.core.themes import` block):

```python
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    Theme,
    get_theme,
)
```

And to `__all__`:

```python
    "CUSTOM_THEME_SENTINEL",
    "DEFAULT_THEME_NAME",
    "THEME_NAMES",
    "THEMES",
    "Theme",
    "get_theme",
```

- [ ] **Step 3: Add `theme_name` field to `RSVPSettings`**

In `rsvp/core/settings.py`, add to the `RSVPSettings` dataclass (anywhere in the Display section is fine):

```python
    theme_name: str = DEFAULT_THEME_NAME
```

- [ ] **Step 4: Add CHANGELOG entry under `[Unreleased]`**

In `CHANGELOG.md` (create it if it doesn't exist on this branch), add:

```markdown
## [Unreleased]

### Added
- Theme presets: switch between Dark, Light, Sepia, and Solarized Light via Settings → Display → Theme. Selecting a theme updates the colors and font family; manual edits switch the dropdown to "Custom".
```

- [ ] **Step 5: Verify**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_settings.py -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: existing settings tests still pass (the new field has a default so no migration needed); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add rsvp/core/themes.py rsvp/core/__init__.py rsvp/core/settings.py CHANGELOG.md
git commit -m "feat: add built-in theme presets (Dark/Light/Sepia/Solarized Light)

New rsvp.core.themes module with:
  - Theme frozen dataclass (name, 3 colors, font family)
  - THEMES dict with 4 built-in themes
  - THEME_NAMES list (for QComboBox ordering)
  - DEFAULT_THEME_NAME = 'Dark' (matches current default look)
  - CUSTOM_THEME_SENTINEL = 'Custom' (UI-only sentinel for manually
    edited presets)
  - get_theme(name) helper with safe fallback to default

Added theme_name field to RSVPSettings (default 'Dark'). No migration
needed: SettingsManager.load() uses setattr-with-hasattr, so existing
settings files lacking the field get the dataclass default.

CHANGELOG entry under [Unreleased] notes the new feature."
```

---

## Task 2: Theme dropdown in Settings dialog

**Files:**
- Modify: `rsvp/ui/settings_dialog.py`

- [ ] **Step 1: Add theme dropdown to the Display group**

In `_setup_ui`, the Display group currently starts with Font. Add the theme combo as the FIRST row (before Font), and wire the signals.

Insert immediately after `display_group = QGroupBox("Display")` (and after the layout creation):

```python
        # Theme dropdown (applies to colors + font)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_NAMES)
        self.theme_combo.addItem(CUSTOM_THEME_SENTINEL)
        display_layout.addRow("Theme:", self.theme_combo)
```

- [ ] **Step 2: Add `_theme_active` state in `__init__`**

After `self._setup_ui()` and before `self._load_settings()`, add:

```python
        self._theme_active: str = ""  # the theme currently being shown (or "" before first apply)
```

- [ ] **Step 3: Add the theme-change handler `_on_theme_changed`**

```python
    def _on_theme_changed(self, theme_name: str) -> None:
        """User picked a theme from the dropdown. Update the color/font fields."""
        if theme_name == CUSTOM_THEME_SENTINEL:
            return
        theme = get_theme(theme_name)
        self.text_color_btn.set_color(theme.text_color)
        self.orp_color_btn.set_color(theme.orp_color)
        self.bg_color_btn.set_color(theme.background_color)
        # blockSignals to avoid triggering the manual-edit detector
        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentFont(QFont(theme.font_family))
        self.font_combo.blockSignals(False)
        self._theme_active = theme_name
```

- [ ] **Step 4: Add the manual-edit detector `_on_color_or_font_changed`**

```python
    def _on_color_or_font_changed(self) -> None:
        """User manually changed a color or font; switch dropdown to 'Custom'."""
        if not self._theme_active:
            return
        active = get_theme(self._theme_active)
        if (
            self.text_color_btn.get_color().lower() != active.text_color.lower()
            or self.orp_color_btn.get_color().lower() != active.orp_color.lower()
            or self.bg_color_btn.get_color().lower() != active.background_color.lower()
            or self.font_combo.currentFont().family() != active.font_family
        ):
            idx = self.theme_combo.findText(CUSTOM_THEME_SENTINEL)
            if idx >= 0 and self.theme_combo.currentText() != CUSTOM_THEME_SENTINEL:
                self.theme_combo.blockSignals(True)
                self.theme_combo.setCurrentIndex(idx)
                self.theme_combo.blockSignals(False)
```

- [ ] **Step 5: Wire signals in `_setup_ui`**

Right after the `self.theme_combo = QComboBox()` block, add the connect:

```python
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
```

Also wire the color buttons and font combo to the manual-edit detector. Add these right after the color buttons and font combo are created (in the Display group):

```python
        self.text_color_btn.clicked.connect(self._on_color_or_font_changed)
        self.orp_color_btn.clicked.connect(self._on_color_or_font_changed)
        self.bg_color_btn.clicked.connect(self._on_color_or_font_changed)
        self.font_combo.currentFontChanged.connect(self._on_color_or_font_changed)
```

- [ ] **Step 6: Update `_load_settings` to set the dropdown**

In `_load_settings`, after `self._load_settings` body, add at the end:

```python
        # Theme dropdown reflects the current setting (or "Custom" if the
        # active theme name doesn't match the actual color/font values)
        stored = get_settings_manager().settings.theme_name
        if stored in THEMES:
            theme = get_theme(stored)
            if (
                settings.text_color.lower() == theme.text_color.lower()
                and settings.orp_color.lower() == theme.orp_color.lower()
                and settings.background_color.lower() == theme.background_color.lower()
                and self.font_combo.currentFont().family() == theme.font_family
            ):
                idx = self.theme_combo.findText(stored)
                if idx >= 0:
                    self.theme_combo.setCurrentIndex(idx)
                self._theme_active = stored
            else:
                # Stored theme name but values diverged — show "Custom"
                idx = self.theme_combo.findText(CUSTOM_THEME_SENTINEL)
                if idx >= 0:
                    self.theme_combo.setCurrentIndex(idx)
                self._theme_active = stored  # remember the name for save
        else:
            # Unknown theme name in storage — fall back to default
            idx = self.theme_combo.findText(DEFAULT_THEME_NAME)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            self._theme_active = DEFAULT_THEME_NAME
```

- [ ] **Step 7: Add `THEME_NAMES`, `get_theme`, `CUSTOM_THEME_SENTINEL`, `QFont`, `QComboBox` imports**

At the top of `rsvp/ui/settings_dialog.py`:

```python
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from rsvp.core.constants import FONT_SIZE_MAX, FONT_SIZE_MIN, WPM_MAX, WPM_MIN
from rsvp.core.settings import get_settings_manager
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    get_theme,
)
```

- [ ] **Step 8: Update `_apply` to persist `theme_name`**

In `_apply`, add at the end (before `manager.save()`):

```python
        # Persist the active theme name (only if the dropdown shows a real theme;
        # "Custom" means the user kept their previous theme_name and tweaked values)
        current_dropdown = self.theme_combo.currentText()
        if current_dropdown in THEMES:
            settings.theme_name = current_dropdown
        # else: keep settings.theme_name as it was
```

- [ ] **Step 9: Verify dialog opens and tests still pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: 297 tests pass; ruff clean.

- [ ] **Step 10: Commit**

```bash
git add rsvp/ui/settings_dialog.py
git commit -m "feat: add theme dropdown to Settings dialog

The Display group in SettingsDialog now has a 'Theme' dropdown at the
top, populated with the 4 built-in themes plus a 'Custom' sentinel.

Behavior:
  - Selecting a theme updates the 3 color buttons AND the font combo
    immediately (live preview)
  - blockSignals is used to prevent the manual-edit detector from
    firing when the theme is applied programmatically
  - Manually clicking a color button or changing the font after
    selecting a theme switches the dropdown to 'Custom' (the
    divergence is preserved)
  - Apply/OK persists settings.theme_name; 'Custom' preserves the
    prior theme name so future upgrades don't break

The dialog correctly handles three cases when loading:
  - Stored theme name + matching values → show that theme
  - Stored theme name + diverged values → show 'Custom'
  - Unknown/missing theme name → fall back to Dark (the default)"
```

---

## Task 3: Tests

**Files:**
- Create: `tests/test_themes.py`
- Create: `tests/test_ui_settings_dialog.py`

- [ ] **Step 1: Create `tests/test_themes.py`**

```python
"""Tests for the themes module."""

import re

from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    Theme,
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
```

- [ ] **Step 2: Create `tests/test_ui_settings_dialog.py`**

```python
"""Smoke tests for the SettingsDialog theme integration."""

import pytest
from PyQt6.QtGui import QFont

from rsvp.core.settings import get_settings_manager
from rsvp.core.themes import (
    CUSTOM_THEME_SENTINEL,
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    get_theme,
)
from rsvp.ui.settings_dialog import SettingsDialog


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Reset the global settings manager to a tmp config path."""
    from rsvp.core import settings as settings_mod
    from rsvp.core.settings import RSVPSettings, SettingsManager

    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "get_settings_manager", lambda: mgr)
    return mgr


class TestSettingsDialogTheme:
    def test_dialog_has_theme_dropdown(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        assert hasattr(dlg, "theme_combo")
        assert dlg.theme_combo.count() == len(THEME_NAMES) + 1  # +1 for Custom

    def test_theme_dropdown_populated_with_4_themes(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        for name in THEME_NAMES:
            assert dlg.theme_combo.findText(name) >= 0
        assert dlg.theme_combo.findText(CUSTOM_THEME_SENTINEL) >= 0

    def test_selecting_theme_updates_colors(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        dlg.theme_combo.setCurrentText("Light")
        light = get_theme("Light")
        assert dlg.text_color_btn.get_color().lower() == light.text_color.lower()
        assert dlg.orp_color_btn.get_color().lower() == light.orp_color.lower()
        assert dlg.bg_color_btn.get_color().lower() == light.background_color.lower()

    def test_selecting_theme_updates_font(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        dlg.theme_combo.setCurrentText("Sepia")
        sepia = get_theme("Sepia")
        assert dlg.font_combo.currentFont().family() == sepia.font_family

    def test_manual_color_edit_shows_custom(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        dlg.theme_combo.setCurrentText("Dark")
        # Simulate a manual change to the text color
        dlg.text_color_btn.set_color("#FF00FF")
        dlg._on_color_or_font_changed()
        assert dlg.theme_combo.currentText() == CUSTOM_THEME_SENTINEL

    def test_apply_persists_theme_name(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        dlg.theme_combo.setCurrentText("Light")
        dlg._apply()
        assert isolated_settings.settings.theme_name == "Light"

    def test_invalid_stored_theme_falls_back_to_default(self, qapp, tmp_path):
        from rsvp.core import settings as settings_mod
        from rsvp.core.settings import RSVPSettings, SettingsManager

        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings(theme_name="NonexistentTheme")
        mgr._settings_were_reset = False
        mgr._save_failed = False
        mgr._config_path = tmp_path / "settings.json"
        import pytest as _pytest

        # Temporarily patch get_settings_manager to return our fixture
        _pytest.MonkeyPatch().setattr(settings_mod, "get_settings_manager", lambda: mgr)
        dlg = SettingsDialog()
        # The dropdown should fall back to the default theme
        assert dlg.theme_combo.currentText() == DEFAULT_THEME_NAME
        assert dlg._theme_active == DEFAULT_THEME_NAME
```

- [ ] **Step 3: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_themes.py tests/test_ui_settings_dialog.py -v 2>&1 | tail -25`
Expected: 15 new tests pass.

- [ ] **Step 4: Run full verification**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1 && /opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -1`
Expected: ~312 tests pass, ruff clean, mypy 0 errors.

- [ ] **Step 5: Commit**

```bash
git add tests/test_themes.py tests/test_ui_settings_dialog.py
git commit -m "test: add themes and settings-dialog theme tests

tests/test_themes.py (8 tests, pure data):
  - 4 themes defined, default is Dark
  - THEME_NAMES ordering
  - get_theme fallback for unknown names
  - Hex color validation
  - CUSTOM_THEME_SENTINEL not in THEMES (UI-only marker)
  - Theme is frozen (immutable)

tests/test_ui_settings_dialog.py (7 tests, Qt smoke):
  - Dropdown has all 4 themes + Custom
  - Selecting a theme updates 3 color buttons
  - Selecting a theme updates font combo
  - Manual color edit shows Custom
  - Apply persists theme_name
  - Invalid stored theme falls back to default"
```

---

## Self-Review

**1. Spec coverage:** 6 spec items mapped to 3 commits (data model + settings field = commit 1; dialog integration = commit 2; tests = commit 3).

**2. Placeholder scan:** No "TBD" or "fill in later" markers. All code blocks are concrete with full implementations.

**3. Type consistency:** `Theme` dataclass used everywhere. `get_theme()` is the only lookup function. `CUSTOM_THEME_SENTINEL` is referenced consistently.

**4. Edge cases handled:**
- Unknown theme name in storage → defaults to Dark
- Custom sentinel picked manually → no-op (no theme to apply)
- Manual edit after theme selection → dropdown switches to Custom
- `theme_name` field missing from old settings.json → dataclass default applies
- Font not installed on system → QFontComboBox handles it (existing behavior)

**5. Risk acknowledgment:**
- WCAG contrast: each theme pair was hand-picked for ≥4.5:1 text contrast
- Font availability: falls through to system default (existing app behavior)
- New theme in future version: append to THEMES, dropdown picks it up

---

## Success Criteria (from spec)

- [ ] `THEMES` dict has 4 themes; all 4 are selectable from the dropdown
- [ ] Selecting a theme updates the 3 color buttons AND the font combo immediately
- [ ] Manually changing a color or font switches the dropdown to "Custom"
- [ ] Apply/OK persists `theme_name` to `settings.json`
- [ ] `pytest -q` passes (~310 tests, 13 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature
- [ ] All 3 items above landed in the named atomic commits
- [ ] No new bare excepts introduced

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~312 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
