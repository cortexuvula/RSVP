# RSVP Chunk Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land chunk mode (1/2/3 words at a time, settings-configurable) as a single PR with 3 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-chunk-mode-design.md).

**Architecture:** New `process_text_into_chunks()` function groups words into chunks. `RSVPEngine.load_text()` uses it when `chunk_size > 1`. Settings → Display gets a combo for the user to pick 1/2/3.

**Tech Stack:** Python 3.10+, PyQt6, stdlib `re`. No new runtime dependencies.

---

## File Structure

**Created:**
- `tests/test_chunk_mode.py`

**Modified:**
- `rsvp/core/text_processor.py` — add `process_text_into_chunks()`
- `rsvp/core/rsvp_engine.py` — update `load_text()` to use chunking
- `rsvp/core/settings.py` — add `chunk_size: int = 1` to `RSVPSettings`
- `rsvp/ui/settings_dialog.py` — add chunk-size combo to Display group
- `CHANGELOG.md` — `[Unreleased]` entry

---

## Task 1: process_text_into_chunks + engine integration

**Files:**
- Modify: `rsvp/core/text_processor.py`
- Modify: `rsvp/core/rsvp_engine.py`
- Modify: `rsvp/core/settings.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add `process_text_into_chunks` to `rsvp/core/text_processor.py`**

Append at the end of the file (after `process_text`):

```python
def process_text_into_chunks(text: str, chunk_size: int) -> list[Word]:
    """Group `text` into chunks of `chunk_size` words, aligned to paragraph boundaries.

    Each chunk becomes a Word with:
      - .text: the joined words (e.g., "the quick brown")
      - .orp_index: the ORP of the FIRST word in the chunk (single focal point)
      - .pause_after: the pause multiplier of the LAST word in the chunk
      - .paragraph_break_after: True if this chunk ends a paragraph

    Paragraph breaks (\\n\\n) never fall mid-chunk. The last chunk of a
    paragraph may be shorter than chunk_size if the paragraph's word
    count doesn't divide evenly.

    Empty input returns an empty list. chunk_size <= 1 falls through to
    process_text() (no grouping).
    """
    if chunk_size <= 1:
        return process_text(text)
    if not text or not text.strip():
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    all_chunks: list[Word] = []
    paragraph_end_indices: list[int] = []

    for para in paragraphs:
        normalized = re.sub(r"\s+", " ", para.strip())
        if not normalized:
            continue
        words = normalized.split(" ")
        para_start = len(all_chunks)
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            if not chunk_words:
                continue
            chunk_text = " ".join(chunk_words)
            first_word = chunk_words[0]
            orp_idx = calculate_orp(first_word)
            last_word = chunk_words[-1]
            pause_mult = calculate_pause_multiplier(last_word)
            all_chunks.append(
                Word(
                    text=chunk_text,
                    orp_index=orp_idx,
                    pause_after=pause_mult,
                )
            )
        if len(all_chunks) > para_start:
            paragraph_end_indices.append(len(all_chunks) - 1)

    for idx in paragraph_end_indices[:-1]:
        all_chunks[idx].paragraph_break_after = True

    return all_chunks
```

- [ ] **Step 2: Add `chunk_size` field to `RSVPSettings`**

In `rsvp/core/settings.py`, add to the `RSVPSettings` dataclass (in the Display section):

```python
    chunk_size: int = 1
```

- [ ] **Step 3: Update `RSVPEngine.load_text` to use chunking**

In `rsvp/core/rsvp_engine.py`, update the `load_text` method to read `chunk_size` and use chunking when > 1. Find the existing method and replace the words assignment:

```python
    def load_text(self, text: str) -> None:
        """Load text for RSVP display."""
        self.stop()
        from rsvp.core.text_processor import (
            process_text,
            process_text_into_chunks,
        )

        chunk_size = 1
        if self._settings is not None:
            chunk_size = getattr(self._settings.settings, "chunk_size", 1) or 1
        if chunk_size > 1:
            self._state.words = process_text_into_chunks(text, chunk_size)
        else:
            self._state.words = process_text(text)
        self._state.current_index = 0
        self.state_changed.emit()
        self.progress_changed.emit(0.0)
        if self._state.words:
            self.word_changed.emit(self._state.current_word)
        else:
            self.word_changed.emit(None)
```

- [ ] **Step 4: Add CHANGELOG entry under `[Unreleased]`**

In `CHANGELOG.md` (create if missing), add:

```markdown
## [Unreleased]

### Added
- Chunk mode: Settings → Display → Chunk Size lets you pick 1, 2, or 3 words per display. Useful as a stepping stone to full RSVP. Paragraphs are aligned to chunk boundaries; ORP is the first word's ORP.
```

- [ ] **Step 5: Verify text_processor tests still pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_text_processor.py -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: all text processor tests pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add rsvp/core/text_processor.py rsvp/core/rsvp_engine.py rsvp/core/settings.py CHANGELOG.md
git commit -m "feat: add chunk mode — process_text_into_chunks and engine integration

process_text_into_chunks(text, chunk_size) groups words into chunks
of N words, aligned to paragraph boundaries:
  - chunk_size <= 1 falls through to process_text (backward compat)
  - Each chunk is a Word with .text = joined words
  - ORP comes from the first word (single visual focal point)
  - pause_after comes from the last word
  - .paragraph_break_after = True on the last chunk of each paragraph

RSVPEngine.load_text reads settings.chunk_size (default 1) and uses
the chunking function when chunk_size > 1. The engine itself doesn't
need to know about chunks vs single words — it iterates over
_state.words and emits each one as before. The display naturally
shows the multi-word .text.

CHANGELOG entry under [Unreleased] notes the new feature."
```

---

## Task 2: Settings dialog combo

**Files:**
- Modify: `rsvp/ui/settings_dialog.py`

- [ ] **Step 1: Add the chunk-size combo to the Display group**

In `rsvp/ui/settings_dialog.py`, find the Display group in `_setup_ui` (after `self.bg_color_btn`). Add a `QComboBox` for chunk size:

```python
        self.chunk_size_combo = QComboBox()
        self.chunk_size_combo.addItems(["1 word", "2 words", "3 words"])
        display_layout.addRow("Chunk Size:", self.chunk_size_combo)
```

Also add `QComboBox` to the import from `PyQt6.QtWidgets`:

```python
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    ...
)
```

- [ ] **Step 2: Load and save the chunk size**

In `_load_settings`, after `self.bg_color_btn.set_color(settings.background_color)`, add:

```python
        chunk_size = getattr(settings, "chunk_size", 1)
        idx = max(0, min(2, chunk_size - 1))  # 1->0, 2->1, 3->2
        self.chunk_size_combo.setCurrentIndex(idx)
```

In `_apply`, after `settings.background_color = self.bg_color_btn.get_color()`, add:

```python
        settings.chunk_size = self.chunk_size_combo.currentIndex() + 1
```

- [ ] **Step 3: Verify all existing tests still pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: 270 tests pass; ruff clean.

- [ ] **Step 4: Commit**

```bash
git add rsvp/ui/settings_dialog.py
git commit -m "feat: add chunk-size setting to Settings dialog

Settings → Display gets a new 'Chunk Size' combo with 3 options:
  - 1 word (default, preserves existing single-word behavior)
  - 2 words
  - 3 words

The combo's currentIndex maps directly to chunk_size (0->1, 1->2, 2->3).
Load clamps the index to the valid range (0-2) so older settings.json
files lacking the field default to '1 word' (index 0).

Apply/OK persists settings.chunk_size. The next load_text() call on
the engine reads the new value and uses the chunking function."
```

---

## Task 3: Tests

**Files:**
- Create: `tests/test_chunk_mode.py`

- [ ] **Step 1: Create `tests/test_chunk_mode.py`**

```python
"""Tests for chunk mode (process_text_into_chunks + engine + settings)."""

import pytest

from rsvp.core.constants import PAUSE_SENTENCE
from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import RSVPSettings, SettingsManager
from rsvp.core.text_processor import (
    calculate_orp,
    process_text,
    process_text_into_chunks,
)


class TestProcessTextIntoChunks:
    def test_chunk_size_1_falls_through(self):
        result = process_text_into_chunks("one two three four", 1)
        assert [w.text for w in result] == ["one", "two", "three", "four"]
        # Should be the same as process_text
        assert [w.text for w in result] == [w.text for w in process_text("one two three four")]

    def test_chunk_size_2(self):
        result = process_text_into_chunks("one two three four", 2)
        assert [w.text for w in result] == ["one two", "three four"]

    def test_chunk_size_3_with_short_last(self):
        result = process_text_into_chunks("one two three four five", 3)
        assert [w.text for w in result] == ["one two three", "four five"]

    def test_empty_input_returns_empty(self):
        assert process_text_into_chunks("", 3) == []
        assert process_text_into_chunks("   ", 3) == []
        assert process_text_into_chunks("\n\n", 3) == []

    def test_paragraph_alignment(self):
        text = "one two three\n\nfour five"
        result = process_text_into_chunks(text, 2)
        # 2 paragraphs, 2 words each -> 2 chunks
        assert [w.text for w in result] == ["one two", "four five"]
        # First chunk ends a paragraph
        assert result[0].paragraph_break_after is True
        # Last chunk also ends a paragraph
        assert result[-1].paragraph_break_after is True

    def test_paragraph_with_uneven_chunks(self):
        text = "one two three four five\n\nsix"
        result = process_text_into_chunks(text, 2)
        # First paragraph: "one two", "three four", "five" (3 chunks)
        # Second paragraph: "six" (1 chunk)
        assert [w.text for w in result] == ["one two", "three four", "five", "six"]
        # Chunks ending paragraphs: index 2 (end of first para), index 3 (end of second/last para)
        assert result[2].paragraph_break_after is True
        assert result[3].paragraph_break_after is True

    def test_orp_from_first_word(self):
        result = process_text_into_chunks("the quick brown", 2)
        # First word "the" has ORP index 1
        assert result[0].orp_index == calculate_orp("the")
        # In the chunk "the quick", the ORP is at position 1
        assert result[0].text[1] == "h"

    def test_pause_from_last_word(self):
        # "world." ends with "." -> PAUSE_SENTENCE
        result = process_text_into_chunks("hello world. how are you", 2)
        assert result[0].pause_after == PAUSE_SENTENCE

    def test_no_mid_chunk_paragraph_breaks(self):
        # Paragraph has 3 words; chunk_size=2 -> chunks are [3-words], []
        # 3-words fits in one chunk, so no mid-chunk split
        text = "one two three\n\nfour"
        result = process_text_into_chunks(text, 2)
        # First para "one two three" -> 1 chunk "one two three"
        # Second para "four" -> 1 chunk "four"
        assert [w.text for w in result] == ["one two three", "four"]


class TestEngineWithChunks:
    @pytest.fixture
    def engine_with_chunks(self, qapp, tmp_path):
        """Create an RSVPEngine with a SettingsManager that has chunk_size set."""
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._settings_were_reset = False
        mgr._save_failed = False
        mgr._config_path = tmp_path / "settings.json"
        return RSVPEngine(settings=mgr)

    def test_load_text_with_chunk_size_2(self, engine_with_chunks):
        engine = engine_with_chunks
        engine._settings.settings.chunk_size = 2
        engine.load_text("one two three four five six")
        # 3 chunks: "one two", "three four", "five six"
        assert engine.word_count == 3
        assert engine.state.words[0].text == "one two"
        assert engine.state.words[1].text == "three four"
        assert engine.state.words[2].text == "five six"

    def test_load_text_with_default_chunk_size_1(self, engine_with_chunks):
        engine = engine_with_chunks
        # Default chunk_size=1
        engine.load_text("one two three four")
        assert engine.word_count == 4
        assert engine.state.words[0].text == "one"

    def test_paragraph_pause_preserved_with_chunks(self, engine_with_chunks):
        engine = engine_with_chunks
        engine._settings.settings.chunk_size = 2
        engine.load_text("one two\n\nthree four")
        # 2 chunks; first ends a paragraph
        assert engine.state.words[0].paragraph_break_after is True
        assert engine.state.words[1].paragraph_break_after is True

    def test_chunks_emit_word_changed_normally(self, engine_with_chunks, qapp):
        engine = engine_with_chunks
        engine._settings.settings.chunk_size = 2
        # Spy on word_changed
        engine.load_text("one two three four")
        # Each chunk is a Word; word_changed fires for the current_word
        assert engine.state.current_word.text == "one two"


class TestSettingsDialogChunkSize:
    def test_dialog_has_chunk_size_combo(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert hasattr(dlg, "chunk_size_combo")
        assert dlg.chunk_size_combo.count() == 3

    def test_chunk_size_combo_default_is_1(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert dlg.chunk_size_combo.currentIndex() == 0  # 1 word

    def test_apply_persists_chunk_size(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        dlg.chunk_size_combo.setCurrentIndex(2)  # 3 words
        dlg._apply()
        assert isolated_settings.settings.chunk_size == 3

    def test_load_clamps_out_of_range(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        isolated_settings.settings.chunk_size = 99  # Out of range
        dlg = SettingsDialog()
        # Should clamp to index 2 (the max)
        assert dlg.chunk_size_combo.currentIndex() == 2
```

For the `TestSettingsDialogChunkSize` tests, add an `isolated_settings` fixture:

```python
@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Construct a SettingsManager with an isolated config path."""
    from rsvp.core import settings as settings_mod

    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "get_settings_manager", lambda: mgr)
    return mgr
```

- [ ] **Step 2: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_chunk_mode.py -v 2>&1 | tail -25`
Expected: ~16 tests pass.

- [ ] **Step 3: Run full verification**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1 && /opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -1`
Expected: ~286 tests pass, ruff clean, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_chunk_mode.py
git commit -m "test: add chunk mode tests (text_processor, engine, settings)

tests/test_chunk_mode.py (~16 tests):

TestProcessTextIntoChunks (9):
  - chunk_size=1 falls through to process_text
  - chunk_size=2 groups words in pairs
  - chunk_size=3 with shorter last chunk
  - empty input returns empty list
  - paragraph alignment (no mid-chunk breaks)
  - paragraph with uneven chunks
  - ORP from first word of chunk
  - pause_after from last word
  - no mid-chunk paragraph breaks

TestEngineWithChunks (4):
  - load_text with chunk_size=2 produces 2-word chunks
  - default chunk_size=1 still works
  - paragraph pause preserved with chunks
  - chunks emit word_changed normally

TestSettingsDialogChunkSize (4):
  - dialog has a chunk_size_combo with 3 options
  - default is '1 word' (index 0)
  - apply persists chunk_size
  - load clamps out-of-range values"
```

---

## Self-Review

**1. Spec coverage:** 8 in-scope items mapped to 3 commits (function+engine → UI → tests).

**2. Placeholder scan:** No "TBD" or "fill in later" markers. All code blocks are concrete.

**3. Type consistency:** `chunk_size: int = 1` used consistently across `settings.py`, `text_processor.py`, `rsvp_engine.py`, `settings_dialog.py`.

**4. Edge cases handled:**
- `chunk_size <= 1` falls through to `process_text` (backward compat)
- Empty input → empty list
- Paragraph with `chunk_size` words → 1 chunk
- Last chunk shorter than `chunk_size` (uneven paragraph)
- ORP from first word (single focal point)
- Pause multiplier from last word
- No mid-chunk paragraph breaks

**5. Risk acknowledgment:**
- WPM effectively multiplied by chunk size
- ORP focal point at the start of the chunk
- Stats count per chunk (not per word)
- Mid-reading chunk size change is not supported (takes effect on next load)

---

## Success Criteria (from spec)

- [ ] `chunk_size: int = 1` field on `RSVPSettings`
- [ ] `process_text_into_chunks()` function works for chunk sizes 1, 2, 3
- [ ] Paragraphs are aligned to chunk boundaries (no mid-chunk paragraph breaks)
- [ ] ORP comes from the first word of each chunk
- [ ] `RSVPEngine.load_text()` uses chunking when `chunk_size > 1`
- [ ] Settings → Display has a chunk-size combo with options "1 word" / "2 words" / "3 words"
- [ ] Apply/OK persists `chunk_size` to `settings.json`
- [ ] `pytest -q` passes (~286 tests, 16 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~286 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
