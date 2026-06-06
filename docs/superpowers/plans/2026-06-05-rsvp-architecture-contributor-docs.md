# RSVP Architecture & Contributor Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land Spec 2's 4 items (settings DI refactor, QPainter safety, CONTRIBUTING.md, DI smoke tests) as a single PR with 4 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-architecture-contributor-docs-design.md).

**Architecture:** SettingsManager becomes a constructor parameter for every class that needs it. MainWindow is the single composition root. No global singleton. Other items are mechanical.

**Tech Stack:** Python 3.10+, PyQt6, mypy, pytest, ruff. No new runtime dependencies.

---

## File Structure

**Created:**
- `CONTRIBUTING.md`
- `README.md` — one-line cross-link addition (existing file)

**Modified:**
- `rsvp/core/settings.py` — remove `get_settings_manager()` and `_settings_manager` global
- `rsvp/core/__init__.py` — remove `get_settings_manager` from imports and `__all__`
- `rsvp/core/rsvp_engine.py` — accept `SettingsManager` in `__init__`
- `rsvp/ui/word_display.py` — `ORPWordDisplay` and `WordDisplayWidget` accept `SettingsManager`; `paintEvent` wrapped in `try/finally`
- `rsvp/ui/bookmark_controller.py` — accept `SettingsManager`
- `rsvp/ui/document_loader.py` — accept `SettingsManager`
- `rsvp/ui/settings_dialog.py` — accept `SettingsManager`
- `rsvp/ui/main_window.py` — construct `SettingsManager` in `__init__`; pass to all children
- `tests/test_settings.py` — add `TestSettingsInjection` class with 3 tests

---

## Task 1: Add CONTRIBUTING.md + README cross-link

**Files:**
- Create: `CONTRIBUTING.md`
- Modify: `README.md` (add one line to any "Development" or similar section)

- [ ] **Step 1: Create CONTRIBUTING.md**

Write `CONTRIBUTING.md` with the verbatim content from the design spec's "Item 3 — CONTRIBUTING.md" section (the full markdown content in a ` ```markdown ` block). The file is ~130 lines.

- [ ] **Step 2: Cross-link from README.md**

Read `README.md`. If it has a "Development" / "Contributing" / "Testing" section, add a one-line link:

```markdown
See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.
```

If no such section exists, skip this step (don't add a new section just for one line).

- [ ] **Step 3: Verify**

Run: `head -5 CONTRIBUTING.md && wc -l CONTRIBUTING.md`
Expected: `# Contributing to RSVP Reader` as the first line. File is ~130 lines.

- [ ] **Step 4: Commit**

```bash
git add CONTRIBUTING.md README.md
git commit -m "docs: add CONTRIBUTING.md

Single-file guide covering dev setup, test/lint/mypy commands, code
style conventions (type hints, dataclasses, logging, exception
handling, constants), commit format (Conventional Commits), and PR
process. Cross-references README.md and CHANGELOG.md."
```

---

## Task 2: Fix QPainter.end() safety in ORPWordDisplay.paintEvent

**Files:**
- Modify: `rsvp/ui/word_display.py` (one method, ~30 lines)

- [ ] **Step 1: Verify current code shape**

Read `rsvp/ui/word_display.py` lines 47-102 to confirm the current `paintEvent` body matches the design spec. It should have:
- `painter = QPainter(self)` at top
- `if not self._word:` with `painter.end()` and `return` mid-method
- 30+ lines of drawing code
- Final `painter.end()` before the method ends

- [ ] **Step 2: Apply try/finally refactor**

Replace the entire `paintEvent` method body with the version from the design spec's "Item 2" section. The diff: wrap everything in `try:` and add `finally: painter.end()`. Remove the mid-method `painter.end()` call (it's now redundant — the `finally` covers it).

The new method should look like:

```python
    def paintEvent(self, event) -> None:
        """Paint the word with ORP highlighting."""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), self._bg_color)

            if not self._word:
                return

            painter.setFont(self._font)
            fm = QFontMetrics(self._font)

            before = self._word.before_orp
            orp_char = self._word.orp_char
            after = self._word.after_orp

            before_width = fm.horizontalAdvance(before)
            orp_width = fm.horizontalAdvance(orp_char)

            center_x = self.width() // 2
            center_y = self.height() // 2

            indicator_height = fm.height() + 20
            painter.setPen(self._orp_color)
            painter.drawLine(
                center_x, center_y - indicator_height // 2, center_x, center_y + indicator_height // 2
            )

            text_y = center_y + fm.ascent() // 2

            orp_center = before_width + orp_width // 2
            text_x = center_x - orp_center

            painter.setPen(self._text_color)
            painter.drawText(int(text_x), int(text_y), before)

            painter.setPen(self._orp_color)
            painter.drawText(int(text_x + before_width), int(text_y), orp_char)

            painter.setPen(self._text_color)
            painter.drawText(int(text_x + before_width + orp_width), int(text_y), after)
        finally:
            painter.end()
```

- [ ] **Step 3: Run tests + ruff + mypy**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_ui_word_display.py -q 2>&1 | tail -3`
Expected: tests pass.

Run: `/opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/`
Expected: clean.

Run: `/opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -3`
Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add rsvp/ui/word_display.py
git commit -m "fix: ensure QPainter.end() is called in ORPWordDisplay.paintEvent

Wraps the paint body in try/finally so painter.end() always runs,
even if the drawing code raises (e.g., font metrics on a degenerate
glyph, setPen with an invalid color). Previously the early-return
path needed its own painter.end() and any exception in the main draw
path would leave the painter unclosed, causing
'QPainter: Paint device returned engine that is being deleted'
warnings on shutdown."
```

---

## Task 3: Replace get_settings_manager() with constructor DI

**Files (7 source files + the singleton removal):**
- Modify: `rsvp/core/settings.py` — remove `get_settings_manager()` and `_settings_manager` global
- Modify: `rsvp/core/__init__.py` — remove `get_settings_manager` from imports and `__all__`
- Modify: `rsvp/core/rsvp_engine.py` — accept `SettingsManager` in `__init__`
- Modify: `rsvp/ui/word_display.py` — `ORPWordDisplay` and `WordDisplayWidget` accept `SettingsManager`
- Modify: `rsvp/ui/bookmark_controller.py` — accept `SettingsManager`
- Modify: `rsvp/ui/document_loader.py` — accept `SettingsManager`
- Modify: `rsvp/ui/settings_dialog.py` — accept `SettingsManager`
- Modify: `rsvp/ui/main_window.py` — construct `SettingsManager` in `__init__`; pass to all children

- [ ] **Step 1: Remove the singleton from core/settings.py**

In `rsvp/core/settings.py`, delete the last 8 lines (the module-level `_settings_manager: SettingsManager | None = None` global and the `get_settings_manager()` function).

The file should end at `clear_position` (line 165 or thereabouts).

- [ ] **Step 2: Remove from core/__init__.py**

In `rsvp/core/__init__.py`:
- Remove the `get_settings_manager,` line from the `from rsvp.core.settings import (...)` block
- Remove the `"get_settings_manager",` line from `__all__`

- [ ] **Step 3: Update RSVPEngine.__init__**

In `rsvp/core/rsvp_engine.py`:
- Change `__init__(self, parent=None) -> None:` to `__init__(self, parent=None, settings: SettingsManager) -> None:`
- Add `self._settings = settings` at the top of the body
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- In `_update_timer_interval`, replace `get_settings_manager().settings.pause_at_paragraphs` with `self._settings.settings.pause_at_paragraphs`

- [ ] **Step 4: Update ORPWordDisplay and WordDisplayWidget**

In `rsvp/ui/word_display.py`:
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- Change `ORPWordDisplay.__init__(self, parent=None) -> None:` to `ORPWordDisplay.__init__(self, parent=None, settings: SettingsManager) -> None:`
- Add `self._settings = settings` at top of body
- In `_load_settings`, replace `settings = get_settings_manager().settings` with `settings = self._settings.settings`
- Change `WordDisplayWidget.__init__(self, parent=None) -> None:` to `WordDisplayWidget.__init__(self, parent=None, settings: SettingsManager) -> None:`
- Add `self._settings = settings`
- In `_setup_ui`, change `self.word_display = ORPWordDisplay()` to `self.word_display = ORPWordDisplay(settings=self._settings)`

- [ ] **Step 5: Update BookmarkController**

In `rsvp/ui/bookmark_controller.py`:
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- Change `__init__` to add `settings: SettingsManager` parameter and `self._settings = settings`
- Replace all 4 `get_settings_manager()` call sites with `self._settings`

- [ ] **Step 6: Update DocumentLoader**

In `rsvp/ui/document_loader.py`:
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- Change `__init__` to add `settings: SettingsManager` parameter and `self._settings = settings`
- Replace all 4 `get_settings_manager()` call sites with `self._settings`

- [ ] **Step 7: Update SettingsDialog**

In `rsvp/ui/settings_dialog.py`:
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- Change `__init__` to add `settings: SettingsManager` parameter and `self._settings = settings`
- Replace all 4 `get_settings_manager()` call sites with `self._settings`

- [ ] **Step 8: Update MainWindow (composition root)**

In `rsvp/ui/main_window.py`:
- Remove `from rsvp.core.settings import get_settings_manager` from imports
- Add `from rsvp.core.settings import SettingsManager` to imports
- Change `__init__(self) -> None:` to `__init__(self, settings: SettingsManager) -> None:`
- Add `self._settings = settings` at top of body
- Change `self._engine = RSVPEngine()` to `self._engine = RSVPEngine(settings=self._settings)`
- In `_setup_ui`, change `self.word_display = WordDisplayWidget()` to `self.word_display = WordDisplayWidget(settings=self._settings)`
- In `_setup_controllers`, pass `settings=self._settings` to `BookmarkController` and `DocumentLoader`
- In `_show_settings`, change `dialog = SettingsDialog(self)` to `dialog = SettingsDialog(self, settings=self._settings)`
- Replace all 10 `get_settings_manager()` call sites in MainWindow with `self._settings`

- [ ] **Step 9: Verify the singleton is gone**

Run: `rg "get_settings_manager" rsvp/ tests/`
Expected: no matches.

- [ ] **Step 10: Run tests + ruff + mypy**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3`
Expected: 273 tests pass (no new tests yet — those come in Task 4).

Run: `/opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/`
Expected: clean.

Run: `/opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -3`
Expected: 0 errors.

- [ ] **Step 11: Commit**

```bash
git add rsvp/
git commit -m "refactor: replace get_settings_manager() singleton with constructor DI

Every class that previously called get_settings_manager() now accepts
a SettingsManager via __init__ and stores it as self._settings:

  - RSVPEngine
  - ORPWordDisplay, WordDisplayWidget
  - BookmarkController
  - DocumentLoader
  - SettingsDialog
  - MainWindow (composition root — constructs the SettingsManager here)

The get_settings_manager() function and its module-level
_settings_manager global are removed from core/settings.py. The
core/__init__.py export is also removed.

Benefits:
  - Widgets are now testable in isolation by passing a fixture
    SettingsManager with a tmp_path config
  - The lifecycle of the settings instance is explicit
  - No hidden global state

No public API change for end users (main.py is unchanged — MainWindow
still constructs everything internally). The change is breaking for
anyone subclassing the affected classes, hence the upcoming 1.4.0
version bump in CHANGELOG.md."
```

---

## Task 4: Add DI smoke tests

**Files:**
- Modify: `tests/test_settings.py` (append a new `TestSettingsInjection` class)

- [ ] **Step 1: Append the test class**

Read the end of `tests/test_settings.py` and append the `TestSettingsInjection` class from the design spec's "Item 4 — DI Smoke Tests" section (verbatim).

The class has 3 tests:
- `test_engine_accepts_injected_settings`
- `test_word_display_accepts_injected_settings`
- `test_get_settings_manager_removed`

- [ ] **Step 2: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_settings.py::TestSettingsInjection -v 2>&1 | tail -10`
Expected: 3 tests pass.

- [ ] **Step 3: Run the full test suite**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3`
Expected: 276 tests pass (273 + 3 new).

- [ ] **Step 4: Commit**

```bash
git add tests/test_settings.py
git commit -m "test: add DI smoke tests for SettingsManager injection

Verifies that:
  - RSVPEngine can be constructed with an injected SettingsManager
  - WordDisplayWidget can be constructed with an injected SettingsManager
  - The get_settings_manager() function is gone (proves the refactor
    is complete)

The first two tests use SettingsManager.__new__ + manual attribute
setup to bypass the real load() that reads from the user's config
directory. This gives a fully isolated fixture that doesn't touch
the developer's actual settings file."
```

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|-----------|------|
| Item 1: Settings DI refactor | Task 3 (7 files) |
| Item 2: QPainter.end() safety | Task 2 (1 file) |
| Item 3: CONTRIBUTING.md | Task 1 (1 file + README cross-link) |
| Item 4: DI smoke tests | Task 4 (1 test file) |

**2. Placeholder scan:** No "TBD" or "fill in later" markers. Every step is concrete with exact code or exact commands.

**3. Type consistency:** `SettingsManager` is imported and used as the parameter type consistently across all 7 modified classes. `self._settings` is the storage attribute name everywhere.

**4. Risk acknowledgment:**
- Removing `get_settings_manager()` is verified safe by `rg` — no callers in tests/main.py
- The `__new__` test fixture is documented in the design spec as the workaround for SettingsManager's real `__init__` reading from the user config dir
- CONTRIBUTING.md cross-link to README is conditional (only if a relevant section exists)

**5. Commit order rationale:**
- Task 1: pure docs additive, no risk
- Task 2: small isolated fix, no interaction with other tasks
- Task 3: the structural change, biggest diff, isolated from Task 1/2
- Task 4: verifies Task 3, depends on Task 3

---

## Success Criteria (from spec)

- [ ] `get_settings_manager` no longer exists anywhere in `rsvp/`
- [ ] Every class that previously called `get_settings_manager()` accepts a `SettingsManager` via `__init__` and stores it as `self._settings`
- [ ] MainWindow constructs the SettingsManager in `__init__` (the only composition root)
- [ ] `ORPWordDisplay.paintEvent` wraps the paint body in `try/finally: painter.end()`
- [ ] `CONTRIBUTING.md` exists at the repo root
- [ ] `pytest -q` passes (273 + 3 = 276 tests)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 4 items above landed in the named atomic commits

---

## Final Verification (after all tasks)

```bash
rg "get_settings_manager" rsvp/ tests/   # expect: no matches
rg "except Exception" rsvp/              # expect: no matches
QT_QPA_PLATFORM=offscreen pytest -q      # expect: 276 passed
ruff check rsvp/ tests/                  # expect: clean
mypy rsvp/                               # expect: 0 errors
git log --oneline main..HEAD             # expect: 4 new commits
```
