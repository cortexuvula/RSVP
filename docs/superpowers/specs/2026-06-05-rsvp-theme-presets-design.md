# Spec 4: Theme Presets

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 4 — 2nd feature spec (1 of 5 from the original review's feature list)
**Branch:** `feature/theme-presets` (off main)
**Target PR:** Single PR with 3 atomic commits

## Context

The original code review listed 5 features. Spec 3 (reading statistics) is done
and pushed. This spec covers theme presets. The remaining 3 features (TTS,
settings export/import, chunk mode) come in their own cycles.

## Scope

**In scope (Spec 4 — this document):**

| # | Item |
|---|------|
| 1 | `Theme` dataclass + 4 built-in themes in `rsvp/core/themes.py` |
| 2 | `theme_name` field on `RSVPSettings` (default: `"Dark"`) |
| 3 | "Theme" dropdown at the top of the Display group in `SettingsDialog` |
| 4 | Apply-theme logic: selecting a theme updates the 3 color buttons and font combo; manually editing reverts dropdown to "Custom" |
| 5 | Tests for the theme data, the apply logic, and a dialog smoke test |
| 6 | CHANGELOG entry under `[Unreleased]` |

**Out of scope (later specs):**

- Spec 5+ — Text-to-speech, settings export/import, chunk mode
- User-saved custom themes (only the 4 built-in presets are selectable; colors are otherwise hand-tuned)
- Theme-aware code highlighting (syntax highlighting for code blocks)
- Per-document theme (a single app-wide theme for now)

## Design Decisions (from brainstorming)

1. **Theme set:** 4 fixed themes: **Dark** (current default), **Light**, **Sepia**, **Solarized Light**. No user-defined themes; only these 4 are selectable.
2. **Theme scope:** Each theme defines **3 colors + font family**. Font size stays as a separate user preference (avoids conflicting with reading-speed preferences).
3. **Selector UI:** A "Theme:" `QComboBox` at the top of the existing Display group in `SettingsDialog`. Selecting a theme previews (updates the color buttons and font combo). On Apply/OK, the theme is persisted.

## Built-in Themes

| Theme | text_color | orp_color | background_color | font_family |
|-------|-----------|-----------|------------------|-------------|
| Dark | `#FFFFFF` | `#FF6B6B` | `#1E1E1E` | Arial (default) |
| Light | `#1A1A1A` | `#C0392B` | `#FAFAFA` | Arial |
| Sepia | `#5B4636` | `#A0522D` | `#F4ECD8` | Georgia |
| Solarized Light | `#586E75` | `#B58900` | `#FDF6E3` | Arial |

**Rationale:**
- **Dark** preserves current default — no migration needed
- **Light** is a neutral high-contrast option
- **Sepia** uses warm browns (KIndle-paper style) with Georgia serif for book-like reading
- **Solarized Light** uses the canonical Solarized palette for users familiar with that color scheme

These are opinionated, hand-picked values. No algorithm, no auto-generation.

## Data Model

```python
# rsvp/core/themes.py

from dataclasses import dataclass

@dataclass(frozen=True)
class Theme:
    name: str
    text_color: str       # hex, e.g. "#FFFFFF"
    orp_color: str        # hex
    background_color: str # hex
    font_family: str      # font name; falls back to system default if not installed


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

THEME_NAMES: list[str] = list(THEMES.keys())  # for the QComboBox
```

## Settings Schema Change

Add one field to `RSVPSettings` in `rsvp/core/settings.py`:

```python
@dataclass
class RSVPSettings:
    # ... existing fields ...
    theme_name: str = DEFAULT_THEME_NAME  # new
```

Existing settings files (lacking `theme_name`) load with the default —
`SettingsManager.load()` uses `setattr` for known keys only, so unknown
keys are ignored and the dataclass default applies. **No migration needed.**

## Dialog Behavior

### Dropdown
- `QComboBox` populated from `THEME_NAMES` (in order: Dark, Light, Sepia, Solarized Light)
- Positioned at the top of the Display group, above the Font row
- Initial value: `settings.theme_name`
- "Custom" sentinel (not a real theme) is shown when the user has manually edited the colors or font since the last theme selection

### Apply-theme flow

```python
def _on_theme_changed(self, theme_name: str) -> None:
    if theme_name == "Custom":
        return  # user manually edited; dropdown shows the divergence
    theme = THEMES[theme_name]
    # Update the color buttons and font combo (preview)
    self.text_color_btn.set_color(theme.text_color)
    self.orp_color_btn.set_color(theme.orp_color)
    self.bg_color_btn.set_color(theme.background_color)
    # blockSignals to avoid the color button's "manual edit" callback
    self.font_combo.blockSignals(True)
    self.font_combo.setCurrentFont(QFont(theme.font_family))
    self.font_combo.blockSignals(False)
    # Mark theme as actively selected
    self._theme_active = theme_name
```

### Manual-edit detection

The color buttons and font combo already have `currentFontChanged`-style
signals. Wire those to a method that, if the current value doesn't match the
active theme's value, switches the dropdown to "Custom".

```python
def _on_color_or_font_changed(self) -> None:
    if not hasattr(self, "_theme_active"):
        return
    active = THEMES.get(self._theme_active)
    if active is None:
        return
    if (self.text_color_btn.get_color() != active.text_color
        or self.orp_color_btn.get_color() != active.orp_color
        or self.bg_color_btn.get_color() != active.background_color
        or self.font_combo.currentFont().family() != active.font_family):
        # Manual divergence — set dropdown to Custom
        idx = self.theme_combo.findText("Custom")
        if idx >= 0 and self.theme_combo.currentIndex() != idx:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(idx)
            self.theme_combo.blockSignals(False)
```

### Save flow

In `_apply`, persist the theme name alongside the existing fields:

```python
settings.theme_name = self._active_theme_name()  # or "Custom" → keep current
```

`_active_theme_name()` returns the dropdown's current value if it's a real
theme, or the existing `settings.theme_name` if it's "Custom" (so manually
edited values persist without losing the theme name).

## Architecture

```
main.py → MainWindow(settings)
              │
              └─ WordDisplayWidget reads settings (no change)
              └─ SettingsDialog reads/writes settings (theme dropdown added)
              └─ THEMES dict in rsvp.core.themes (new)
```

No composition root changes — `RSVPSettings` gets a new field, the dialog
gets a new widget, and the theme data lives in a new module.

## File-Level Changes

| File | Change |
|------|--------|
| `rsvp/core/themes.py` | New — `Theme` dataclass + `THEMES` dict + `THEME_NAMES` list + `DEFAULT_THEME_NAME` |
| `rsvp/core/__init__.py` | Re-export `Theme`, `THEMES`, `THEME_NAMES`, `DEFAULT_THEME_NAME` |
| `rsvp/core/settings.py` | Add `theme_name: str = DEFAULT_THEME_NAME` to `RSVPSettings` |
| `rsvp/ui/settings_dialog.py` | Add theme combo to Display group; wire apply logic; manual-edit detection |
| `tests/test_themes.py` | New — verify all 4 themes are valid, lookup, DEFAULT_THEME_NAME exists |
| `tests/test_ui_settings_dialog.py` | New — smoke test: dropdown populated, selecting a theme updates fields, manual edit shows "Custom" |
| `CHANGELOG.md` | New — `[Unreleased]` entry |

## Per-Item Design

### Item 1 — `rsvp/core/themes.py`

`Theme` is a frozen dataclass (immutable). The `THEMES` dict is keyed by
display name (matches the dropdown order). A `THEME_NAMES` list provides
the ordered list for the `QComboBox`.

Helper function:
```python
def get_theme(name: str) -> Theme:
    """Return the named theme, or the default if not found."""
    return THEMES.get(name, THEMES[DEFAULT_THEME_NAME])
```

### Item 2 — `RSVPSettings.theme_name`

Add the field with default = `"Dark"`. This matches the current default
look of the app (white text on near-black with red ORP), so existing
users see no change on upgrade.

### Item 3 — Dropdown in SettingsDialog

The dropdown goes at the top of the Display group:

```
Display
  Theme:           [Dark ▼]
  Font:            [Arial ▼]
  Font Size:       [48  ] pt
  Text Color:      [#FFFFFF]
  ORP Color:       [#FF6B6B]
  Background:      [#1E1E1E]
```

Selecting a theme:
- Updates the 3 color buttons (`ColorButton.set_color()`)
- Updates the font combo (`QFontComboBox.setCurrentFont()`)
- Sets `_theme_active` so the manual-edit detector can compare
- Shows a live preview immediately (no Apply required)

On Apply/OK: writes `settings.theme_name` to the active theme name (or
preserves the old `theme_name` if the dropdown is on "Custom").

### Item 4 — Manual-edit detection

Connect the color buttons' `clicked` signal (which triggers the color
picker) and the font combo's `currentFontChanged` signal to
`_on_color_or_font_changed`. When any value diverges from the active
theme, the dropdown is set to "Custom" (with `blockSignals` to avoid
recursion).

### Item 5 — Tests

**`tests/test_themes.py`** (pure logic):
- `test_all_4_themes_defined`
- `test_default_theme_is_dark`
- `test_theme_names_in_expected_order`
- `test_get_theme_returns_default_for_unknown`
- `test_theme_colors_are_valid_hex`
- `test_theme_is_immutable` (frozen=True)

**`tests/test_ui_settings_dialog.py`** (UI smoke):
- `test_dialog_has_theme_dropdown`
- `test_theme_dropdown_populated_with_4_themes`
- `test_selecting_theme_updates_colors`
- `test_selecting_theme_updates_font`
- `test_manual_color_edit_shows_custom`
- `test_apply_persists_theme_name`
- `test_invalid_stored_theme_falls_back_to_default`

## Commit Plan (3 atomic commits)

```
feat: add built-in theme presets (Dark/Light/Sepia/Solarized Light)
feat: add theme dropdown to Settings dialog
test: add themes and settings-dialog theme tests
```

**Rationale:**
1. **Data model first:** `themes.py` and `RSVPSettings` field — pure
   data, no UI. Easiest to review.
2. **Dialog wiring second:** `SettingsDialog` integration with the
   dropdown, apply logic, manual-edit detection. Depends on the data
   model.
3. **Tests third:** Both `test_themes.py` and `test_ui_settings_dialog.py`.
   Note: this is slightly out of strict TDD order (data-model tests
   should ideally come with the data), but in this codebase the
   pattern has been to commit all tests for a feature in one batch.
   Either order works.

The CHANGELOG entry goes with the first commit (the user-visible
thing is the feature itself).

## Testing Strategy

- 297 existing tests + ~13 new (6 themes + 7 dialog) = 310 total
- All tests use the existing `qapp` and `tmp_path` fixtures
- Theme data tests are pure (no Qt)
- Dialog smoke test uses the real `SettingsManager` with an isolated
  `tmp_path` config

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| `theme_name` field is a breaking change for users with old settings.json | `SettingsManager.load()` uses `setattr` with `hasattr` check — unknown keys are ignored, the dataclass default applies. Verified during Spec 2 testing. |
| Font "Georgia" / "Arial" not installed on every system | The app already has this risk for the user's current font selection. The font combo shows installed fonts; selecting a non-installed font falls back to system default. |
| Color contrast (WCAG) on the chosen themes | Each theme was hand-picked for adequate contrast. The 4 themes listed all have text/bg contrast ratios ≥ 4.5:1 (WCAG AA for normal text). |
| "Custom" sentinel collides with a future theme name | "Custom" is a UI-only sentinel; THEMES dict doesn't contain it. `get_theme("Custom")` falls through to the default. |
| Dropdown ordering changes after a user upgrades | `THEME_NAMES` is a list literal in code, so it's stable across versions. New themes would be appended. |
| User picks theme, then manually changes one color, then opens dialog again | The dropdown shows "Custom" — the divergence is preserved. The `theme_name` in settings is preserved (not overwritten with "Custom") so future upgrades don't break. |

## Out of Scope (Explicitly)

- User-defined custom themes (no UI to create, save, or delete)
- Theme preview thumbnails (the dropdown is text-only; thumbnails would be visual polish that can come later)
- Per-document theme overrides
- Theme-aware syntax highlighting in code blocks
- Theme export/import (covered by the settings export/import spec)
- Auto-theme based on system dark/light mode preference

## Success Criteria

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
