# RSVP Improvements Design Spec

**Date:** 2026-04-20
**Scope:** 6 items from IMPROVEMENT_REPORT.md (4.1–4.6)
**Approach:** Feature clusters — settings/engine, input formats, UI accessibility, CI

---

## Cluster 1: Settings & Engine

### 4.4 — Error Recovery for Corrupted Settings

**Goal:** When `settings.json` is corrupted, back up the file, reset to defaults, and notify the user.

**SettingsManager changes (`rsvp/core/settings.py`):**

- In `load()`, on `JSONDecodeError` or `IOError`:
  1. Copy corrupted file to `settings.json.bak` (overwrite previous backup)
  2. Log to stderr: `"Settings file corrupted, reset to defaults. Backup: {path}"`
  3. Set instance flag `self._settings_were_reset = True`
  4. Continue with defaults

- Add `was_reset() -> bool`: returns and clears the flag (read-once pattern)

**MainWindow changes (`rsvp/ui/main_window.py`):**

- On startup, after loading settings, check `settings_manager.was_reset()`
- If true, show `QMessageBox.warning()`: "Your settings file was corrupted and has been reset to defaults. A backup was saved to `settings.json.bak`."

### 4.1a — Implement `pause_at_paragraphs`

**Goal:** Insert an extra-long pause at paragraph boundaries during playback.

**Word dataclass (`rsvp/core/text_processor.py`):**

- Add field: `paragraph_break_after: bool = False`

**`process_text()` changes (`rsvp/core/text_processor.py`):**

- Before normalizing whitespace, split text on `\n\n+` to identify paragraph boundaries
- Process each paragraph separately
- Mark the last word of each paragraph with `paragraph_break_after = True`
- Concatenate all Word lists

**Engine changes (`rsvp/core/rsvp_engine.py`):**

- In `_update_timer_interval()`: if `pause_at_paragraphs` is enabled in settings and current word has `paragraph_break_after == True`, multiply interval by 3.0 (~600ms at 300 WPM)

**Settings dialog (`rsvp/ui/settings_dialog.py`):**

- Add checkbox "Pause at paragraph breaks" in Behavior group, bound to `settings.pause_at_paragraphs`

### 4.1b — Implement `auto_save_position`

**Goal:** Save reading position on close/switch; offer to resume when reopening the same file.

**New settings field (`rsvp/core/settings.py`):**

- Add to `RSVPSettings`: `saved_positions: dict[str, int] = field(default_factory=dict)` — maps source path/URL to word index

**SettingsManager methods (`rsvp/core/settings.py`):**

- `save_position(source: str, index: int)` — stores position
- `get_position(source: str) -> int | None` — retrieves saved position
- `clear_position(source: str)` — removes entry

**MainWindow changes (`rsvp/ui/main_window.py`):**

- On file/URL load: if `auto_save_position` is enabled and a saved position exists, show `QMessageBox.question()`: "Resume from word {n} of {total}?" If yes, `engine.seek(saved_index)`
- On `closeEvent` and on loading new text: if there's a current source path and `current_index > 0`, save current position (covers playing, paused, and manually-seeked states)
- On `finished` signal: clear saved position for that source

**Settings dialog (`rsvp/ui/settings_dialog.py`):**

- Add checkbox "Remember reading position" in Behavior group, bound to `settings.auto_save_position`

---

## Cluster 2: Input & Formats

### 4.3 — Expand File Input Support

**Goal:** Support .md, .html, .epub, and .pdf in addition to .txt.

**Architecture:** Refactor `load_text_from_file()` in `text_processor.py` to dispatch by file extension.

| Extension | Strategy | Dependency |
|-----------|----------|-----------|
| `.txt` | UTF-8 read (current) | None |
| `.md` | UTF-8 read + strip markdown syntax | `re` (stdlib) |
| `.html`, `.htm` | Read file + `extract_text_from_html()` | `beautifulsoup4` (existing) |
| `.epub` | Extract XHTML chapters in spine order, each through `extract_text_from_html()`, join with `\n\n` | `ebooklib` (new) |
| `.pdf` | Extract text page by page, join with `\n\n` | `pymupdf` (new) |

**New function: `strip_markdown(text: str) -> str`**

Handles: headers (`#`), bold/italic (`**`, `*`, `__`, `_`), links `[text](url)`, images `![alt](url)`, code blocks, inline code, HTML tags, horizontal rules. Deliberately simpler than a full parser — output just needs to be readable words.

**New function: `load_text_from_epub(filepath: str) -> str`**

1. `ebooklib.epub.read_epub(filepath)`
2. Get items in spine order
3. For each `EpubHtml` item, extract content via `extract_text_from_html()`
4. Join with `\n\n`

**New function: `load_text_from_pdf(filepath: str) -> str`**

1. `fitz.open(filepath)`
2. For each page: `page.get_text()`
3. Join with `\n\n`

**Dependency changes (`pyproject.toml`):**

- Add `ebooklib >= 0.18`
- Add `pymupdf >= 1.23.0`

**TextInputDialog changes (`rsvp/ui/text_input_dialog.py`):**

- Update file browser filter to: `"All Supported (*.txt *.md *.html *.htm *.epub *.pdf);;Text (*.txt);;Markdown (*.md);;HTML (*.html *.htm);;EPUB (*.epub);;PDF (*.pdf);;All Files (*)"`

**Error handling:**

- Each format loader raises `ValueError` with user-friendly message on failure
- Calling UI code already shows `QMessageBox.critical()` on exceptions

**Tests (`tests/test_text_processor.py`):**

- `test_load_markdown_strips_headers`
- `test_load_markdown_strips_bold_italic`
- `test_load_markdown_preserves_text`
- `test_load_html_file`
- `test_load_epub` (minimal test fixture)
- `test_load_pdf` (minimal test fixture)
- `test_file_extension_dispatch`

---

## Cluster 3: UI & Accessibility

### 4.5 — Focus-Aware Keyboard Navigation

**Goal:** Speed slider is Tab-focusable; arrow keys operate the focused widget, global shortcuts otherwise. Escape returns focus to display.

**Controls changes (`rsvp/ui/controls.py`):**

- `SpeedControl.slider` and `SpeedControl.spinbox` get `Qt.FocusPolicy.TabFocus`
- Playback buttons keep `NoFocus` (BUG-03 fix preserved)

**MainWindow changes (`rsvp/ui/main_window.py`):**

Replace global arrow-key `QShortcut` objects with an `eventFilter`:

```
eventFilter(obj, event):
    if event is KeyPress:
        if key in (Up, Down, Left, Right):
            if focus is on SpeedControl slider/spinbox:
                return False  (let widget handle it)
            else:
                handle as global shortcut, return True
        if key is Escape:
            set focus to word_display, return True
    return False
```

- Non-arrow shortcuts (Space, S, Home, End, Shift+arrows, F11) remain as `QShortcut` — no conflict
- Shift+Left/Right (sentence nav) always works globally

**Visual focus indicator:**

- Stylesheet on SpeedControl: `QSlider:focus { border: 1px solid #4A9EFF; }`

**Tab order:**

- `setTabOrder()`: `speed_control.slider` → `speed_control.spinbox` → `word_display`
- Short cycle of 2 focusable controls + display

---

## Cluster 4: CI

### 4.2 — Test Coverage Reporting

**Changes to `.github/workflows/build.yml`:**

- Pytest command becomes: `QT_QPA_PLATFORM=offscreen pytest tests/ -v --cov=rsvp --cov-report=xml --cov-report=term-missing`
- `term-missing` prints coverage summary with uncovered lines in CI log
- `xml` produces `coverage.xml` for optional future Codecov integration

**Dependency (`pyproject.toml`):**

- Ensure `pytest-cov >= 4.0.0` is in `dev` optional dependencies

### 4.6 — Add macOS CI Target

**Changes to `.github/workflows/build.yml` — test job:**

- Add strategy matrix: `os: [ubuntu-latest, macos-latest]`, `python-version: ['3.11']`
- Condition the `apt-get install` step with `if: runner.os == 'Linux'`
- macOS uses `QT_QPA_PLATFORM=offscreen` (same as Linux)
- No Windows test target — Qt on Windows CI requires display server emulation; the build job already validates Windows

---

## Cross-Cutting Concerns

**Version:** Bump to 1.2.0 after all changes land.

**Settings migration:** `saved_positions` is a new field with a default value. Existing `settings.json` files without this key will get the default (empty dict) on load — no explicit migration needed. Same for `pause_at_paragraphs` and `auto_save_position` which already exist.

**Test strategy:** Each cluster adds tests for its new functionality. Existing tests must continue to pass — the `process_text()` refactor (paragraph detection) must preserve existing Word output for text without paragraph breaks.

**`auto_save_position` + new formats:** Position is keyed by source path string. File paths work directly. URLs work directly. Pasted text has no source path — position is not saved (intentional; pasted text is ephemeral).
