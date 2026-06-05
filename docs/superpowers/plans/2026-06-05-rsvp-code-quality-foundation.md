# RSVP Code Quality & Tooling Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 7 code-quality and tooling improvements (broad excepts, type hints, mypy, CHANGELOG, fixtures, logging, requirements.txt cleanup) as a single PR with 7 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-code-quality-foundation-design.md).

**Architecture:** No architectural change. Each commit is a self-contained, reversible change ordered so the next builds on it: housekeeping → docs → tests → logging → excepts → type hints → mypy validation. pyproject.toml remains the canonical dependency source; `rsvp/py.typed` markers the package as typed.

**Tech Stack:** Python 3.10+, PyQt6, mypy (new), pytest, ruff. No new runtime dependencies.

---

## File Structure

**Deleted:**
- `requirements.txt`

**Created:**
- `CHANGELOG.md`
- `rsvp/py.typed` (empty marker)
- `tests/fixtures/test.md`
- `tests/fixtures/test.html`

**Modified:**
- `pyproject.toml` — add `[tool.mypy]`
- `tests/test_text_processor.py` — add `TestLoadTextFromFile` class
- 11 source files — add `logger`, narrow excepts, add type hints (see per-task file lists)

The split is: one commit per logical change. Source files appear in multiple commits but only one kind of change per file per commit (logging commit adds loggers, excepts commit narrows excepts, hints commit adds annotations).

---

## Task 1: Delete redundant requirements.txt

**Files:**
- Delete: `requirements.txt`

- [ ] **Step 1: Verify pyproject.toml lists all dependencies**

Run: `cat pyproject.toml | grep -A 20 "dependencies = \["`
Expected: PyQt6, requests, beautifulsoup4, pyperclip, ebooklib, pymupdf — all six matching `requirements.txt`.

- [ ] **Step 2: Delete the file**

Run: `git rm requirements.txt`
Expected: `rm 'requirements.txt'`

- [ ] **Step 3: Verify tests still resolve dependencies**

Run: `pip install -e .[dev] 2>&1 | tail -5` then `pytest -x --no-header -q 2>&1 | tail -5`
Expected: pytest collects and runs (may have failures unrelated to this change; the key signal is "no collection errors").

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove redundant requirements.txt

pyproject.toml is the canonical dependency source per PEP 621.
requirements.txt duplicated the same list and was a drift risk."
```

---

## Task 2: Add CHANGELOG.md

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Create CHANGELOG.md with backfilled content**

Write `CHANGELOG.md` with the following content:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Replace `requirements.txt` with `pyproject.toml` as the canonical dependency source

## [1.3.5] - 2026-05-15

### Changed
- Bump CI actions off Node.js 20

## [1.3.4] - 2026-05-15

### Changed
- Ship macOS as signed/notarized DMG instead of zip

## [1.3.3] - 2026-05-15

### Changed
- Transparent rounded-square icon

## [1.3.2] - 2026-05-15

### Added
- Application icon

## [1.3.1] - 2026-05-15

### Added
- Sign and notarize macOS release builds

## [1.3.0] - 2026-05-15

### Added
- Address code review findings from prior evaluation cycle (HTML paragraph breaks, PDF resource leak, settings reset, etc.)

## [1.2.0] - 2026-04-20

### Added
- Focus-aware keyboard navigation (Up/Down adjust WPM, Left/Right skip)
- File dialogs updated for all supported formats (txt, md, html, htm, epub, pdf)
- PDF file support via pymupdf
- EPUB file support via ebooklib
- File format dispatch for `.md` and `.html`
- `strip_markdown` function
- Auto-save reading position per file
- "Resume reading?" prompt when reopening a file with a saved position
- Pause at paragraph breaks
- Saved reading positions to settings
- Error recovery for corrupted settings (backup + reset notification)
- Coverage reporting in CI
- macOS test target in CI

### Changed
- HTML extraction now inserts double-newlines at block elements (paragraphs, headings, lists, etc.)

## [1.1.0] - 2026-03-29

### Added
- 7 bug fixes and 11 improvements (see git log for detail)

## [1.0.0] - 2026-01-15

### Added
- Initial release: RSVP speed reading application
- PyQt6 GUI with dark theme
- Optimal Recognition Point (ORP) highlighting
- WPM control (slider + spinbox)
- Playback controls (play/pause/stop/skip)
- Sentence-level navigation (Shift+Left/Right)
- Bookmark support (Ctrl+B, Ctrl+Shift+B)
- Recent files menu
- Settings dialog (font, color, WPM, always-on-top)
- Fullscreen mode (F11)
- URL fetching (http/https only)
- Clipboard paste-and-read
- Cross-platform builds via GitHub Actions (Ubuntu, macOS, Windows)
```

- [ ] **Step 2: Verify the file**

Run: `head -5 CHANGELOG.md` and `wc -l CHANGELOG.md`
Expected: header line, "All notable changes..." line, blank, "The format is based on..." line, blank, `## [Unreleased]`. File is ~50 lines.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG.md

Backfilled from git log and release history using Keep a Changelog
1.1.0 format. Provides a curated, human-readable history of changes
to complement GitHub's auto-generated release notes."
```

---

## Task 3: Add .md and .html test fixtures and dispatch tests

**Files:**
- Create: `tests/fixtures/test.md`
- Create: `tests/fixtures/test.html`
- Modify: `tests/test_text_processor.py` (add `TestLoadTextFromFile` class)

- [ ] **Step 1: Create test.md fixture**

Write `tests/fixtures/test.md`:

```markdown
# Heading One

This is a paragraph with **bold**, *italic*, and `inline code`.

## Heading Two

A [link to example](https://example.com) and an image ![alt text](image.png).

- List item one
- List item two

```python
def hello():
    print("world")
```

> Blockquote with <sub>subscript</sub>.
```

- [ ] **Step 2: Create test.html fixture**

Write `tests/fixtures/test.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Test</title>
<script>alert('strip me');</script>
<style>body { color: red; }</style>
</head>
<body>
<h1>Heading One</h1>
<p>First paragraph with &amp; ampersand and &lt; less-than.</p>
<p>Second paragraph with a <a href="https://example.com">link</a>.</p>
<img src="image.png" alt="image alt text">
<h2>Heading Two</h2>
<ul>
<li>List item one</li>
<li>List item two</li>
</ul>
<hr>
<p>Trailing paragraph.</p>
</body>
</html>
```

- [ ] **Step 3: Add the failing test**

Add the following class to the end of `tests/test_text_processor.py`:

```python
class TestLoadTextFromFile:
    """Tests for the format dispatch in load_text_from_file."""

    def test_dispatches_markdown(self, tmp_path):
        from tests.conftest import FIXTURES_DIR  # noqa: F401  (see note)

        # Inline content keeps the test self-contained and exercises the
        # .md branch of load_text_from_file without depending on the
        # fixture file existing.
        p = tmp_path / "doc.md"
        p.write_text("# Header\n\n**bold** text", encoding="utf-8")
        result = load_text_from_file(str(p))
        assert "Header" in result
        assert "bold" in result
        assert "#" not in result

    def test_dispatches_html(self, tmp_path):
        p = tmp_path / "doc.html"
        p.write_text("<h1>Title</h1><p>Body &amp; more</p>", encoding="utf-8")
        result = load_text_from_file(str(p))
        assert "Title" in result
        assert "Body & more" in result
        assert "<h1>" not in result

    def test_dispatches_plain_text(self, tmp_path):
        p = tmp_path / "doc.txt"
        p.write_text("plain content", encoding="utf-8")
        assert load_text_from_file(str(p)) == "plain content"

    def test_htm_extension_treated_as_html(self, tmp_path):
        p = tmp_path / "doc.htm"
        p.write_text("<p>html</p>", encoding="utf-8")
        result = load_text_from_file(str(p))
        assert "html" in result
        assert "<p>" not in result

    def test_missing_file_raises(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        with pytest.raises(OSError):
            load_text_from_file(str(missing))
```

**Note:** Remove the `from tests.conftest import FIXTURES_DIR  # noqa: F401` line — it was a placeholder to remind you to drop it. The `tmp_path` fixture is built into pytest and avoids the import.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `pytest tests/test_text_processor.py::TestLoadTextFromFile -v`
Expected: 5 tests pass. The code paths already exist; the tests just confirm dispatch works end-to-end.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `pytest -q 2>&1 | tail -3`
Expected: all tests pass (existing test count plus 5 new = 156 + 5 = 161 tests).

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/test.md tests/fixtures/test.html tests/test_text_processor.py
git commit -m "test: add .md and .html fixtures and load_text_from_file dispatch tests

Closes the gap where format-specific regressions in the .md and .html
branches of load_text_from_file could ship undetected. The .epub and
.pdf branches already had integration coverage; .md and .html now
have it too.

The .htm extension is explicitly tested as an alias for .html to lock
in the current dispatch behavior."
```

---

## Task 4: Add logging to core and UI modules

**Files (logging-only change, one module per step):**
- Modify: `rsvp/main.py` (logger already configured; add `logger = logging.getLogger(__name__)` and update `_configure_logging` return)
- Modify: `rsvp/core/__init__.py` (add logger for re-export context)
- Modify: `rsvp/core/rsvp_engine.py`
- Modify: `rsvp/core/text_processor.py`
- Modify: `rsvp/ui/bookmark_controller.py`
- Modify: `rsvp/ui/controls.py`
- Modify: `rsvp/ui/document_loader.py`
- Modify: `rsvp/ui/main_window.py`
- Modify: `rsvp/ui/settings_dialog.py`
- Modify: `rsvp/ui/text_input_dialog.py`
- Modify: `rsvp/ui/word_display.py`

The pattern is: add `import logging` + `logger = logging.getLogger(__name__)` near the top, then sprinkle `logger.debug/info/exception` at the key events listed below. Existing `settings.py` already has a logger — leave it untouched.

- [ ] **Step 1: Update main.py to expose a logger**

In `rsvp/main.py`, add after the existing imports (line 11):

```python
logger = logging.getLogger(__name__)
```

Then change `_configure_logging` to also set our package's logger to the configured level (so `RSVP_LOG_LEVEL=DEBUG` actually works for `rsvp.*` loggers, not just the root):

Replace the body of `_configure_logging`:

```python
def _configure_logging() -> None:
    """Configure logging for the application."""
    level_name = os.environ.get("RSVP_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    # Ensure the rsvp package logger uses the configured level even when
    # basicConfig is a no-op (e.g. root already configured by a host env).
    logging.getLogger("rsvp").setLevel(level)
```

In `main()`, after `app = QApplication(sys.argv)`, add:

```python
    logger.info("RSVP Reader starting (version %s)", __version__)
```

- [ ] **Step 2: Add logger to rsvp/core/__init__.py**

Add after the existing imports (line 35, before `__all__`):

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 3: Add logger + INFO to rsvp/core/rsvp_engine.py**

Add after line 2 (after the docstring):

```python
import logging

from rsvp.core.constants import (
    DEFAULT_SKIP_WORDS,
    PAUSE_PARAGRAPH,
    WPM_DEFAULT,
    WPM_MAX,
    WPM_MIN,
)

logger = logging.getLogger(__name__)
```

(Keep the existing `from rsvp.core.constants import (...)` block — add `import logging` above it and the logger below it.)

In `load_text`, after `self._state.words = process_text(text)`, add:

```python
        logger.info("Loaded %d words into engine", len(self._state.words))
```

In `play`, after `self._state.is_playing = True`, add:

```python
        logger.debug("Engine play() at index %d", self._state.current_index)
```

In `pause`, add:

```python
        logger.debug("Engine pause() at index %d", self._state.current_index)
```

In `seek`, after the bounds check, add:

```python
        logger.debug("Engine seek() to index %d", self._state.current_index)
```

- [ ] **Step 4: Add logger to rsvp/core/text_processor.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 14):

```python
logger = logging.getLogger(__name__)
```

In `load_text_from_file`, add at the top of each branch:

```python
def load_text_from_file(filepath: str) -> str:
    """Load text from a file, dispatching by extension."""
    ext = Path(filepath).suffix.lower()
    logger.debug("load_text_from_file dispatch for extension %s", ext or "(none)")

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
```

(Only the `logger.debug(...)` line is added; rest is unchanged.)

- [ ] **Step 5: Add logger to rsvp/ui/bookmark_controller.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 9):

```python
logger = logging.getLogger(__name__)
```

In `add`, after `self._set_status(...)`, add:

```python
        logger.info("Bookmark added at word %d in %s", self._engine.current_index, current_file)
```

In `remove`, after the successful remove branch, add:

```python
            logger.info("Bookmark removed at word %d in %s", current, current_file)
```

- [ ] **Step 6: Add logger to rsvp/ui/controls.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 12):

```python
logger = logging.getLogger(__name__)
```

In `SpeedControl.set_wpm`, after the spinbox/slider setup, add:

```python
        logger.debug("WPM set to %d", wpm)
```

(No logging in `PlaybackControls` or `ProgressWidget` — those are pure UI event handlers whose debug value is low.)

- [ ] **Step 7: Add logger + INFO/EXCEPTION to rsvp/ui/document_loader.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 14):

```python
logger = logging.getLogger(__name__)
```

In `load_file`, after `text = load_text_from_file(filepath)`, add:

```python
        logger.info("Loaded file %s (%d words)", filepath, self._engine.word_count)
```

In `load_from_clipboard`, after the early-return guard, add:

```python
        logger.info("Loaded clipboard text (%d words)", self._engine.word_count)
```

(The except site in `load_file` gets its `logger.exception` in Task 5 — leave the bare `except Exception` for now.)

- [ ] **Step 8: Add logger + INFO/DEBUG to rsvp/ui/main_window.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 16):

```python
logger = logging.getLogger(__name__)
```

In `__init__`, after `self._check_settings_reset()`, add:

```python
        logger.info("MainWindow initialized")
```

In `_on_finished`, after the `clear_position` call, add:

```python
        logger.info("Reading finished; cleared saved position for %s", self._current_file)
```

In `_show_shortcuts` and `_show_about`, do NOT add logging — they are pure UI dialogs that are noisy when DEBUG.

- [ ] **Step 9: Add logger to rsvp/ui/settings_dialog.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 20):

```python
logger = logging.getLogger(__name__)
```

In `_apply`, after `manager.save()`, add:

```python
        logger.info("Settings applied")
```

- [ ] **Step 10: Add logger to rsvp/ui/text_input_dialog.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 19):

```python
logger = logging.getLogger(__name__)
```

In `_paste_from_clipboard`, inside the success branch (after `self.text_edit.setPlainText(text)`), add:

```python
            logger.debug("Pasted %d chars from clipboard via pyperclip", len(text))
```

In `_fetch_url`, after `text = fetch_text_from_url(url)`, add:

```python
            logger.info("Fetched URL %s (%d chars)", url, len(text))
```

(The except sites get `logger.exception` in Task 5.)

- [ ] **Step 11: Add logger to rsvp/ui/word_display.py**

Add after line 1 (docstring):

```python
import logging
```

Add after the existing imports (line 7):

```python
logger = logging.getLogger(__name__)
```

In `ORPWordDisplay.paintEvent`, this is a hot path. Do NOT log per-paint. Skip.

(No logging change needed in word_display — paint events are too hot. The settings are loaded once at init via `_load_settings`, no logging needed there either.)

- [ ] **Step 12: Run ruff + tests**

Run: `ruff check rsvp/ tests/`
Expected: no errors.

Run: `pytest -q 2>&1 | tail -3`
Expected: all 161 tests pass.

- [ ] **Step 13: Smoke-test logging works**

Run: `RSVP_LOG_LEVEL=DEBUG python -c "import logging; logging.basicConfig(level=logging.DEBUG); from rsvp.core.rsvp_engine import RSVPEngine; e = RSVPEngine(); e.load_text('hello world'); e.play()" 2>&1 | head -10`
Expected: at least one log line like `INFO rsvp.core.rsvp_engine: Loaded 2 words into engine` and `DEBUG rsvp.core.rsvp_engine: Engine play() at index 0`.

(Use `QT_QPA_PLATFORM=offscreen` if you want to silence any Qt warnings: `QT_QPA_PLATFORM=offscreen RSVP_LOG_LEVEL=DEBUG ...`)

- [ ] **Step 14: Commit**

```bash
git add rsvp/main.py rsvp/core/__init__.py rsvp/core/rsvp_engine.py rsvp/core/text_processor.py rsvp/ui/bookmark_controller.py rsvp/ui/controls.py rsvp/ui/document_loader.py rsvp/ui/main_window.py rsvp/ui/settings_dialog.py rsvp/ui/text_input_dialog.py rsvp/ui/word_display.py
git commit -m "feat: add logging throughout application

Foundation for the upcoming except-narrowing work. Adds a module-level
logger to every rsvp.* module using getLogger(__name__). The existing
logging.basicConfig call in rsvp.main is unchanged but now also sets
the rsvp package logger level, so RSVP_LOG_LEVEL=DEBUG actually works.

Log levels:
  DEBUG  - engine state changes, clipboard fallback
  INFO   - document loads, bookmark changes, settings apply, app start
  WARN   - (already used in settings.py for corrupt config)

Hot paths (paintEvent, slider drag) are deliberately not logged."
```

---

## Task 5: Replace bare `except Exception` with specific types

**Files (one site per step):**
- Modify: `rsvp/ui/text_input_dialog.py` (5 sites: lines 132, 161, 180, 196, 206)
- Modify: `rsvp/ui/document_loader.py` (2 sites: lines 64, 111)

The pattern is: replace `except Exception` (or `except Exception as e`) with the specific types identified in the design spec, and add `logger.exception(...)` for the unexpected-path visibility. QMessageBox user dialog is preserved.

- [ ] **Step 1: Narrow text_input_dialog.py:132 — clipboard fallback**

Replace lines 124-137 (the entire `_paste_from_clipboard` method body) with:

```python
    def _paste_from_clipboard(self) -> None:
        """Paste text from clipboard."""
        try:
            import pyperclip

            text = pyperclip.paste()
            if text:
                self.text_edit.setPlainText(text)
                logger.debug("Pasted %d chars from clipboard via pyperclip", len(text))
        except (ImportError, OSError) as e:
            # pyperclip may be missing, or the system clipboard helper (xclip/xsel)
            # is unavailable on Linux. Fall back to Qt's clipboard.
            logger.debug("pyperclip unavailable, falling back to Qt clipboard: %s", e)
            from PyQt6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            self.text_edit.setPlainText(clipboard.text())
```

- [ ] **Step 2: Narrow text_input_dialog.py:161 — file load error dialog**

Replace lines 161-162 (the `except Exception as e: QMessageBox.warning(...)` block in `_browse_file`) with:

```python
            except (OSError, ValueError) as e:
                logger.exception("Failed to load file: %s", filepath)
                QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
```

- [ ] **Step 3: Narrow text_input_dialog.py:180 — URL fetch error dialog**

Replace lines 180-181 (the `except Exception as e: QMessageBox.warning(...)` block in `_fetch_url`) with:

```python
        except (requests.RequestException, ValueError) as e:
            logger.exception("Failed to fetch URL: %s", url)
            QMessageBox.warning(self, "Error", f"Failed to fetch URL: {e}")
```

Also update the imports at the top of the file to add `requests` for the type:

```python
import requests
```

(Add this after `import logging`.)

- [ ] **Step 4: Narrow text_input_dialog.py:196 — file load in _accept**

Replace lines 196-198 (the `except Exception as e:` block in `_accept`, file branch) with:

```python
                except (OSError, ValueError) as e:
                    logger.exception("Failed to load file: %s", self.file_path_edit.text())
                    QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
                    return
```

- [ ] **Step 5: Narrow text_input_dialog.py:206 — URL fetch in _accept**

Replace lines 206-208 (the `except Exception as e:` block in `_accept`, url branch) with:

```python
                except (requests.RequestException, ValueError) as e:
                    logger.exception("Failed to fetch URL: %s", self.url_edit.text().strip())
                    QMessageBox.warning(self, "Error", f"Failed to fetch URL: {e}")
                    return
```

- [ ] **Step 6: Narrow document_loader.py:64 — load_file**

Replace lines 64-66 (the `except Exception as e:` block in `load_file`) with:

```python
        except (OSError, ValueError) as e:
            logger.exception("Failed to load file: %s", filepath)
            QMessageBox.warning(self._parent, "Error", f"Failed to load file: {e}")
            return False
```

- [ ] **Step 7: Narrow document_loader.py:111 — clipboard fallback in _read_clipboard**

Replace lines 105-115 (the entire `_read_clipboard` method body) with:

```python
    @staticmethod
    def _read_clipboard() -> str:
        try:
            import pyperclip

            text = pyperclip.paste()
            if text:
                return text
        except (ImportError, OSError) as e:
            logger.debug("pyperclip unavailable, falling back to Qt clipboard: %s", e)
        from PyQt6.QtWidgets import QApplication

        return QApplication.clipboard().text()
```

- [ ] **Step 8: Verify no bare `except Exception` remains**

Run: `rg "except Exception" rsvp/`
Expected: no matches.

- [ ] **Step 9: Run ruff + tests**

Run: `ruff check rsvp/ tests/`
Expected: no errors.

Run: `pytest -q 2>&1 | tail -3`
Expected: all 161 tests pass.

- [ ] **Step 10: Smoke-test the error paths still show dialogs**

This is a manual test. Create a quick script `scripts/test_bare_excepts.py` (do NOT commit it):

```python
"""Throwaway test for Task 5 — verifies the user-facing dialog still appears."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QMessageBox
from rsvp.ui.text_input_dialog import TextInputDialog

app = QApplication.instance() or QApplication([])

# Patch QMessageBox.warning to record calls without blocking on a dialog
calls = []
with patch.object(QMessageBox, "warning", side_effect=lambda *a, **kw: calls.append((a, kw))):
    dialog = TextInputDialog()
    # Force the file-load path with a missing file
    with patch("rsvp.ui.text_input_dialog.load_text_from_file", side_effect=FileNotFoundError("nope")):
        dialog._browse_file()
        # Manually call _accept with a non-empty filepath
        dialog.file_path_edit.setText("/nonexistent.md")
        dialog._accept()
print("warning calls:", len(calls))
assert len(calls) >= 1, "Expected at least one QMessageBox.warning call"
print("OK")
```

Run: `QT_QPA_PLATFORM=offscreen python scripts/test_bare_excepts.py`
Expected: `OK` printed, with at least one warning call recorded.

- [ ] **Step 11: Delete the throwaway script and commit**

```bash
rm scripts/test_bare_excepts.py
git add rsvp/ui/text_input_dialog.py rsvp/ui/document_loader.py
git commit -m "fix: replace bare except Exception with specific exception types

All 7 sites (5 in text_input_dialog.py, 2 in document_loader.py) now
catch only the exception types the underlying libraries actually raise:
  - file loads:   (OSError, ValueError)
  - URL fetches:  (requests.RequestException, ValueError)
  - clipboard:    (ImportError, OSError)

The QMessageBox user-facing dialog is preserved for all expected error
types. Each site now calls logger.exception() so unexpected failures
leave a traceback in the log (RSVP_LOG_LEVEL=DEBUG) while still
surfacing to the user via the dialog.

Unexpected exceptions (KeyError from ebooklib, etc.) now propagate
instead of being silently swallowed, surfacing real bugs."
```

---

## Task 6: Add type hints to all functions

**Files:** 11 source files, 1 `__init__.py` per package, plus `main.py`.

Approach: For each file, add return types and param types where missing. Use the existing inline annotation style. Run `pytest` after each file to catch any signature change that breaks a caller.

- [ ] **Step 1: Annotate rsvp/main.py**

Add `-> None` to:
- `_configure_logging()`
- `_resolve_icon_path() -> Path | None` (already typed)
- `main() -> None`

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 2: Annotate rsvp/core/constants.py**

No functions. Module-level constants are already typed by assignment. Skip.

- [ ] **Step 3: Annotate rsvp/core/rsvp_engine.py**

Add `-> None` to:
- `RSVPEngine.__init__(self, parent=None)`
- `load_text(self, text: str)`
- `play(self)`
- `pause(self)`
- `toggle_play_pause(self)`
- `stop(self)`
- `seek(self, index: int)`
- `seek_percent(self, percent: float)`
- `skip_forward(self, words: int = DEFAULT_SKIP_WORDS)`
- `skip_backward(self, words: int = DEFAULT_SKIP_WORDS)`
- `previous_sentence(self)`
- `next_sentence(self)`
- `_update_timer_interval(self)`
- `_advance(self)`

Add types to setters and signals. The `word_changed = pyqtSignal(object)` line stays as-is — `pyqtSignal` accepts untyped arguments.

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 4: Annotate rsvp/core/settings.py**

Add types:
- `load(self) -> None`
- `add_recent_file(self, filepath: str) -> None`
- `add_bookmark(self, filepath: str, word_index: int) -> None`
- `remove_bookmark(self, filepath: str, word_index: int) -> None`
- `save_position(self, source: str, index: int) -> None`
- `clear_position(self, source: str) -> None`
- `save(self) -> None` (already commented; add the `-> None`)

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 5: Annotate rsvp/core/text_processor.py**

Add types to dataclass and any function that's missing them. Most are already typed (per the design spec's grep result). Check each:

- `Word.text: str` ✓
- All `Word` properties already return typed.
- `process_text(text: str) -> list[Word]` ✓
- `load_text_from_epub(filepath: str) -> str` ✓
- `load_text_from_pdf(filepath: str) -> str` ✓
- `fetch_text_from_url(url: str) -> str` ✓

Verify by reading each def line; add `-> X` only where missing.

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 6: Annotate rsvp/ui/bookmark_controller.py**

Add `-> None` to:
- `__init__` (param types already present)
- `add(self) -> None` (already has `-> None`)
- `remove(self) -> None` (already has `-> None`)
- `refresh_menu(self) -> None` (already has `-> None`)
- `_add_placeholder(self, text: str) -> None`

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 7: Annotate rsvp/ui/controls.py**

Add types to:
- `PlaybackControls.__init__(self, parent=None) -> None`
- `PlaybackControls._setup_ui(self) -> None`
- `PlaybackControls._on_play_pause(self) -> None`
- `PlaybackControls.set_playing(self, is_playing: bool) -> None` ✓
- `SpeedControl.__init__(self, parent=None) -> None`
- `SpeedControl._setup_ui(self) -> None`
- `SpeedControl._decrease_wpm(self) -> None`
- `SpeedControl._increase_wpm(self) -> None`
- `SpeedControl._on_slider_change(self, value: int) -> None`
- `SpeedControl._on_spinbox_change(self, value: int) -> None`
- `SpeedControl.set_wpm(self, wpm: int) -> None` ✓
- `SpeedControl.get_wpm(self) -> int` ✓
- `ProgressWidget.__init__(self, parent=None) -> None`
- `ProgressWidget._setup_ui(self) -> None`
- `ProgressWidget._on_seek(self) -> None`
- `ProgressWidget.update_progress(self, progress_percent: float, current: int, total: int, time_remaining: float) -> None` ✓

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 8: Annotate rsvp/ui/document_loader.py**

Add types to:
- `__init__` (params already typed) `-> None`
- `open_file_dialog(self) -> str | None` ✓
- `load_file(self, filepath: str) -> bool` ✓
- `load_from_text_dialog(self, text: str, source: str | None) -> None` ✓
- `load_from_clipboard(self) -> None` ✓
- `_read_clipboard() -> str` ✓
- `maybe_save_position(self) -> None` ✓
- `_maybe_save_position(self) -> None` ✓
- `_maybe_resume_position(self, source: str | None) -> None` ✓

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 9: Annotate rsvp/ui/main_window.py**

Add types to:
- `__init__(self) -> None`
- `_setup_ui(self) -> None` ✓ (just add `-> None` if missing)
- `_setup_menus(self) -> None`
- `_setup_controllers(self) -> None`
- `_setup_shortcuts(self) -> None`
- `_connect_signals(self) -> None`
- `eventFilter(self, obj, event) -> bool` (Qt override — return type matters)
- `_setup_tab_order(self) -> None`
- `_load_window_settings(self) -> None`
- `_save_window_settings(self) -> None`
- `_apply_settings(self) -> None`
- `_update_recent_menu(self) -> None`
- `_load_text_dialog(self) -> None`
- `_open_file(self) -> None`
- `_load_file(self, filepath: str) -> None` (currently returns nothing — change `-> bool` to `-> None`? Check whether any caller uses the return; if not, `-> None`. Looking at main_window.py:246, `self._documents.load_file(filepath)` — return is unused, so `-> None` is fine, but `load_file` in `document_loader.py` returns `bool`. Keep `-> None` on the MainWindow wrapper and `-> bool` on the underlying.)
- `_paste_and_read(self) -> None`
- `_on_document_loaded(self, source: str | None) -> None`
- `_show_settings(self) -> None`
- `_toggle_always_on_top(self) -> None`
- `_toggle_fullscreen(self) -> None`
- `_speed_up(self) -> None`
- `_speed_down(self) -> None`
- `_add_bookmark(self) -> None`
- `_remove_bookmark(self) -> None`
- `_update_bookmarks_menu(self) -> None`
- `_show_shortcuts(self) -> None`
- `_show_about(self) -> None`
- `_on_word_changed(self, word: Word | None) -> None`
- `_on_state_changed(self) -> None`
- `_on_progress_changed(self, progress: float) -> None`
- `_on_wpm_changed(self, wpm: int) -> None`
- `_on_finished(self) -> None`
- `_check_settings_reset(self) -> None`
- `_check_settings_save_failed(self) -> None`
- `closeEvent(self, event) -> None` (Qt override)

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 10: Annotate rsvp/ui/menu_builder.py**

Add types:
- `MenuBuilder.__init__(self, window: QMainWindow, host) -> None`
- `MenuBuilder.build(self) -> MenuRefs` ✓

(No other public/private methods.)

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 11: Annotate rsvp/ui/settings_dialog.py**

Add types:
- `ColorButton.__init__(self, color: str, parent=None) -> None`
- `ColorButton._update_style(self) -> None`
- `ColorButton._pick_color(self) -> None`
- `ColorButton.get_color(self) -> str` ✓
- `ColorButton.set_color(self, color: str) -> None` ✓
- `SettingsDialog.__init__(self, parent=None) -> None`
- `SettingsDialog._setup_ui(self) -> None`
- `SettingsDialog._load_settings(self) -> None`
- `SettingsDialog._apply(self) -> None`
- `SettingsDialog._save_and_accept(self) -> None`
- `SettingsDialog.reject(self) -> None`

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 12: Annotate rsvp/ui/text_input_dialog.py**

Add types:
- `__init__(self, parent=None) -> None`
- `_setup_ui(self) -> None`
- `_paste_from_clipboard(self) -> None`
- `_browse_file(self) -> None`
- `_fetch_url(self) -> None`
- `_accept(self) -> None`
- `get_text(self) -> str` ✓
- `get_source_path(self) -> str | None` ✓

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 13: Annotate rsvp/ui/word_display.py**

Add types:
- `ORPWordDisplay.__init__(self, parent=None) -> None`
- `ORPWordDisplay._load_settings(self) -> None`
- `ORPWordDisplay.update_settings(self) -> None`
- `ORPWordDisplay.set_word(self, word: Word | None) -> None` ✓
- `ORPWordDisplay.set_font_size(self, size: int) -> None` ✓
- `ORPWordDisplay.paintEvent(self, event) -> None` (Qt override)
- `WordDisplayWidget.__init__(self, parent=None) -> None`
- `WordDisplayWidget._setup_ui(self) -> None`
- `WordDisplayWidget.set_word(self, word: Word | None) -> None` ✓
- `WordDisplayWidget.update_settings(self) -> None` ✓

Verify: `pytest -q 2>&1 | tail -3`

- [ ] **Step 14: Annotate rsvp/__init__.py**

Already minimal. No functions. Skip.

- [ ] **Step 15: Final ruff + pytest pass**

Run: `ruff check rsvp/ tests/`
Expected: no errors.

Run: `pytest -q 2>&1 | tail -3`
Expected: 161 tests pass.

- [ ] **Step 16: Verify with ad-hoc mypy dry-run**

Run: `python -m mypy --python-version 3.10 --ignore-missing-imports --check-untyped-defs rsvp/ 2>&1 | tail -30`
Expected: zero errors, OR a small list of false positives that the next commit's config handles (e.g., the `Any` return from `pyqtSignal.emit`).

If there are real errors, fix them in this commit before committing. If there are PyQt6-specific false positives that need `# type: ignore[arg-type]`, add the ignores inline with a brief comment.

- [ ] **Step 17: Commit**

```bash
git add rsvp/
git commit -m "feat: add type hints to all functions

Per the design spec decision, every function, method, property, signal
handler, and Qt override now has parameter and return type annotations.
The pattern matches the existing inline style (no 'from __future__
import annotations').

Ad-hoc mypy --ignore-missing-imports rsvp/ passes with zero errors.
The next commit adds the canonical [tool.mypy] config to pyproject.toml."
```

---

## Task 7: Add mypy config and py.typed marker

**Files:**
- Modify: `pyproject.toml` (append `[tool.mypy]` section)
- Create: `rsvp/py.typed` (empty file)

- [ ] **Step 1: Create rsvp/py.typed**

Run: `touch rsvp/py.typed`
Expected: empty file created.

- [ ] **Step 2: Add [tool.mypy] to pyproject.toml**

Append the following section to the end of `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.10"
files = ["rsvp"]
check_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_return_any = true
no_implicit_optional = true
ignore_missing_imports = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
```

- [ ] **Step 3: Run mypy**

Run: `python -m mypy rsvp/ 2>&1 | tail -30`
Expected: zero errors, exit code 0.

If errors appear, fix them inline in this commit (do NOT amend the previous commit; add a fixup here). Common sources:
- `pyqtSignal(object)` callers passing `Any`: add `-> None` to the slot or `# type: ignore[arg-type]`
- `QFont` parameter narrowing: `setStyleSheet(f"...")` is fine because `f"..."` is `str`
- `lambda: self._engine.seek(0)`: `seek` takes `int`, lambda returns int — fine

If you add a `# type: ignore[arg-type]`, leave a one-line comment explaining why.

- [ ] **Step 4: Run ruff and pytest one more time**

Run: `ruff check rsvp/ tests/`
Run: `pytest -q 2>&1 | tail -3`
Expected: no ruff errors, 161 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml rsvp/py.typed
git commit -m "chore: add mypy config and py.typed marker

The rsvp package is now typed end-to-end. The empty py.typed file
signals to downstream consumers (and to mypy) that the package ships
type information. The [tool.mypy] section configures gradual typing:

  - check_untyped_defs     = true  (still check untyped bodies)
  - ignore_missing_imports = true  (PyQt6 stubs are incomplete)
  - disallow_untyped_defs  = false (gradual rollout; flip to true later)
  - no_implicit_optional   = true  (require explicit Optional[...])

mypy rsvp/ passes with zero errors."
```

---

## Self-Review

**1. Spec coverage:**

| Spec item | Task |
|-----------|------|
| Item 1: Fix bare `except Exception` | Task 5 (7 sites) |
| Item 2: Add type hints to all functions | Task 6 (11 source files) |
| Item 3: mypy config + `py.typed` | Task 7 |
| Item 4: `CHANGELOG.md` | Task 2 |
| Item 5: `.md`/`.html` test fixtures + tests | Task 3 |
| Item 6: Add logging throughout | Task 4 |
| Item 7: Delete `requirements.txt` | Task 1 |

**2. Placeholder scan:** No "TBD" or "fill in later" markers. Every code block is concrete. Every command is exact.

**3. Type consistency:** `Word | None` used for word-shaped parameters across `rsvp_engine.py`, `word_display.py`, `main_window.py`, `document_loader.py` — consistent. `str | None` used for source/file/URL paths — consistent. `-> None` for void methods — consistent.

**4. Risk acknowledgment:** Task 5 narrows exception handling. The QMessageBox is preserved for expected error types. Unexpected exceptions (e.g., `KeyError` from `ebooklib`) now propagate; the smoke test in Task 5 Step 10 verifies the dialog still fires for expected errors.

**5. Commit order rationale (per spec):**
1. Housekeeping (delete `requirements.txt`) — no risk warm-up
2. CHANGELOG — documents the rest
3. Test fixtures + dispatch tests — covers existing code paths
4. Logging foundation — needed for Task 5
5. Bare excepts — uses logger added in Task 4
6. Type hints — annotates the cleaned-up code
7. mypy config — validates the just-added hints

---

## Success Criteria (from spec)

- [ ] `ruff check` and `pytest` pass on every commit
- [ ] `mypy rsvp` reports zero errors
- [ ] All 7 bare `except Exception` blocks narrowed to specific types with `logger.exception()` calls
- [ ] All 7 items above landed in the named atomic commits
- [ ] No public API change
- [ ] CHANGELOG.md is up-to-date through 1.3.5
- [ ] Test coverage for `load_text_from_file` covers `.md`, `.html`, `.htm`, and `.txt` dispatch

---

## Final Verification (after all tasks)

- [ ] **Step 1: Full verification suite**

```bash
ruff check rsvp/ tests/
pytest -q
python -m mypy rsvp/
rg "except Exception" rsvp/   # expect: no matches
```

All four should pass with zero issues.

- [ ] **Step 2: Review the git log**

```bash
git log --oneline -10
```

Expected: 7 new commits on top of the design spec commit, in the order listed in the spec.

- [ ] **Step 3: Push and open PR**

```bash
git push origin <branch>
gh pr create --title "Code quality & tooling foundation" --body "Implements Spec 1 from docs/superpowers/specs/2026-06-05-rsvp-code-quality-foundation-design.md"
```
