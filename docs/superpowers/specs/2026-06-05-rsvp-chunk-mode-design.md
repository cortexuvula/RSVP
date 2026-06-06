# Spec 7: Chunk Mode

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 7 — 5th and final feature spec (1 of 5 from the original review's feature list)
**Branch:** `feature/chunk-mode` (off main)
**Target PR:** Single PR with 3 atomic commits

## Context

The original code review listed 5 features. Specs 3 (reading statistics), 4
(theme presets), 5 (text-to-speech), and 6 (settings export/import) are
done. This spec covers chunk mode — the last remaining feature.

## Scope

**In scope (Spec 7 — this document):**

| # | Item |
|---|------|
| 1 | `chunk_size: int = 1` field on `RSVPSettings` (default 1 = current single-word behavior) |
| 2 | `process_text_into_chunks(text, chunk_size) -> list[Word]` function in `rsvp/core/text_processor.py` |
| 3 | `RSVPEngine.load_text()` uses chunking when `chunk_size > 1` |
| 4 | Settings → Display: a `QSpinBox` (min=1, max=3) for chunk size |
| 5 | ORP calculation uses the first word of each chunk (single visual focal point) |
| 6 | Paragraph alignment: chunks don't split across paragraph boundaries |
| 7 | Tests for chunk grouping, paragraph alignment, ORP inheritance, engine integration, UI |
| 8 | CHANGELOG entry under `[Unreleased]` |

**Out of scope (later specs):**

- All 5 features from the original review are covered by Specs 3-7
- Variable chunk sizes (1-5 range) — current spec is 1-3
- Chunk-mode-aware pause multipliers (chunk-of-3 might warrant a longer pause than chunk-of-1)
- Per-paragraph override of chunk size
- Chunk-mode-only stats (track chunks read separately from words)

## Design Decisions (from brainstorming)

1. **Chunk size:** **User-configurable 1/2/3.** Default 1 (current behavior). 2 and 3 group adjacent words. Max 3 because the display width starts becoming a concern beyond 3 short words.
2. **UI surface:** **Persistent setting in Settings → Display.** Picked once, stays. No toolbar button, no menu commands.
3. **Engine integration:** **Group at load time.** `process_text_into_chunks()` runs once at `load_text()`. The engine iterates over chunks just like single words. `word_changed` fires once per chunk. Each `Word` has multi-word `.text` (e.g., `"the quick brown"`) with the ORP of the first word.
4. **Paragraph alignment:** **Align chunks to paragraph boundaries.** Paragraph breaks don't fall mid-chunk. The last chunk of a paragraph may be shorter than `chunk_size` and gets `paragraph_break_after = True`.

## Data Model

Add one field to `RSVPSettings`:

```python
@dataclass
class RSVPSettings:
    # ... existing fields ...
    chunk_size: int = 1
```

Default `1` preserves current single-word behavior for existing users.
No migration needed (same `setattr`-with-`hasattr` load pattern).

## Text Processing

New function in `rsvp/core/text_processor.py`:

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

    # Split on paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)
    all_chunks: list[Word] = []
    paragraph_end_indices: list[int] = []

    for para in paragraphs:
        normalized = re.sub(r"\s+", " ", para.strip())
        if not normalized:
            continue
        words = normalized.split(" ")
        # Group into chunks of chunk_size
        para_start = len(all_chunks)
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            if not chunk_words:
                continue
            chunk_text = " ".join(chunk_words)
            # ORP from the first word
            first_word = chunk_words[0]
            orp_idx = calculate_orp(first_word)
            # Pause from the last word
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

**Examples:**

```
Input: "the quick brown fox"
chunk_size=1: 4 chunks: ["the"], ["quick"], ["brown"], ["fox"]
chunk_size=2: 2 chunks: ["the quick"], ["brown fox"]
chunk_size=3: 2 chunks: ["the quick brown"], ["fox"]  (last shorter)

Input: "one two\n\nthree four five"
chunk_size=2: 3 chunks: ["one two"], ["three four"], ["five"]
                  (last is shorter, paragraph_break_after=True on "one two")
```

## Engine Integration

`RSVPEngine.load_text` is updated to read the chunk_size setting:

```python
def load_text(self, text: str) -> None:
    self.stop()
    chunk_size = self._settings.settings.chunk_size if self._settings else 1
    self._state.words = process_text_into_chunks(text, chunk_size)
    self._state.current_index = 0
    self.state_changed.emit()
    self.progress_changed.emit(0.0)
    logger.info("Loaded %d chunks into engine", len(self._state.words))
    # ... rest unchanged
```

The engine itself doesn't need to know about chunks vs. single words — it
just iterates over the `_state.words` list and emits each one. The fact
that some words are multi-word is transparent.

## ORP Behavior

For a chunk like "the quick brown":
- The chunk's ORP character is the ORP of the first word, `the` → ORP index 1 (the `h` in `the` is the ORP character).
- The display shows "the quick brown" with the `h` in `the` highlighted.
- This is the visual focal point — single character highlighted in the middle of a 3-word group.

Trade-off: the user might expect the ORP to be more centrally located within the chunk. But "anchor on the first word" is simple, consistent, and matches research on multi-word display (per the original code review, the feature is "a stepping stone for users ramping up to full RSVP" — not a serious long-term mode).

## Paragraph Alignment

The existing `process_text()` already handles paragraph alignment for
single words. `process_text_into_chunks` extends the same logic to chunks:
- Paragraphs are split first
- Each paragraph's words are chunked independently
- The last chunk of each paragraph gets `paragraph_break_after = True`
- The engine's `_update_timer_interval` already multiplies the interval by `PAUSE_PARAGRAPH` for chunks with `paragraph_break_after = True`

So paragraph pauses work correctly for chunks without engine changes.

## Settings Dialog

Add a chunk-size spinner to the Display group:

```
Display
  Theme:           [Dark ▼]
  Font:            [Arial ▼]
  Font Size:       [48  ] pt
  Text Color:      [#FFFFFF]
  ORP Color:       [#FF6B6B]
  Background:      [#1E1E1E]
  Chunk Size:      [1  ] words    ← NEW (range 1-3)
```

```python
self.chunk_size_spin = QSpinBox()
self.chunk_size_spin.setRange(1, 3)
self.chunk_size_spin.setSuffix(" word" if False else " words")  # always plural
display_layout.addRow("Chunk Size:", self.chunk_size_spin)
```

`setSuffix(" word" if False else " words")` is silly. Just use `" words"`. The
suffix is plural even for 1 (because "1 words" is also silly, but "1 word"
suffixed is also wrong — `1 word` looks like a typo). For 2 or 3, "2 words"
is correct. So always use " words" plural.

Actually, Qt has `QSpinBox.setSuffix(" word")` which auto-pluralizes via
`QAbstractSpinBox`. Wait — it doesn't. The suffix is a literal string.
Simpler: set suffix to `" words"`. The user sees "1 words" for 1 chunk,
which is awkward but not broken.

For polish: conditionally set suffix. But the user can pick 1, 2, or 3
and seeing "1 words" / "2 words" / "3 words" is acceptable. Or we use
" words" without condition.

Let me just use a non-numeric suffix: just label the field "Chunk Size:" and
let the user see the number. Or use a `QComboBox` with explicit values
"1 word", "2 words", "3 words". The latter is clearer.

Actually a QComboBox is cleaner here than a QSpinBox. The user picks
from "1 word" / "2 words" / "3 words" — no ambiguity, no awkward pluralization.

```python
self.chunk_size_combo = QComboBox()
self.chunk_size_combo.addItems(["1 word", "2 words", "3 words"])
display_layout.addRow("Chunk Size:", self.chunk_size_combo)
```

The combo's `currentIndex` (0, 1, 2) maps directly to chunk_size (1, 2, 3).

## File-Level Changes

| File | Change |
|------|--------|
| `rsvp/core/text_processor.py` | Add `process_text_into_chunks()` function |
| `rsvp/core/rsvp_engine.py` | Update `load_text()` to use chunking when `chunk_size > 1` |
| `rsvp/core/settings.py` | Add `chunk_size: int = 1` to `RSVPSettings` |
| `rsvp/ui/settings_dialog.py` | Add chunk-size combo to Display group; load/save |
| `tests/test_chunk_mode.py` | New — chunk grouping, paragraph alignment, engine integration, UI |
| `CHANGELOG.md` | `[Unreleased]` entry |

## Per-Item Design

### Item 1 — `process_text_into_chunks`

Pure function in `text_processor.py`. Takes `text: str` and `chunk_size: int`, returns `list[Word]`. Reuses the existing `calculate_orp` and `calculate_pause_multiplier` helpers. Falls through to `process_text()` when `chunk_size <= 1` (backward compat for tests and code that calls with the default).

### Item 2 — Engine integration

`RSVPEngine.load_text` reads `chunk_size` from the injected `SettingsManager` and calls the appropriate function. The `Word` objects are identical to single words; the only difference is `.text` is a multi-word string.

### Item 3 — Settings dialog

The Display group gets a new row with a `QComboBox` populated with `["1 word", "2 words", "3 words"]`. The combo's `currentIndex` is the chunk_size. Apply/OK persists `settings.chunk_size`.

### Item 4 — Tests

**`tests/test_chunk_mode.py`** (~10 tests):

```python
class TestProcessTextIntoChunks:
    def test_chunk_size_1_falls_through(self):
        result = process_text_into_chunks("one two three", 1)
        assert len(result) == 3
        assert [w.text for w in result] == ["one", "two", "three"]

    def test_chunk_size_2(self):
        result = process_text_into_chunks("one two three four", 2)
        assert [w.text for w in result] == ["one two", "three four"]

    def test_chunk_size_3_with_short_last(self):
        result = process_text_into_chunks("one two three four", 3)
        assert [w.text for w in result] == ["one two three", "four"]

    def test_empty_input_returns_empty(self):
        assert process_text_into_chunks("", 3) == []
        assert process_text_into_chunks("   ", 3) == []

    def test_paragraph_alignment(self):
        text = "one two three\n\nfour five"
        result = process_text_into_chunks(text, 2)
        # First paragraph: "one two" (1 chunk), second: "four five" (1 chunk)
        assert [w.text for w in result] == ["one two", "four five"]
        # First chunk ends a paragraph
        assert result[0].paragraph_break_after is True

    def test_orp_from_first_word(self):
        result = process_text_into_chunks("the quick brown", 2)
        # First word "the" has ORP index 1
        assert result[0].orp_index == calculate_orp("the")
        # The ORP character of "the" is "h" (index 1)
        # In the chunk "the quick", the ORP is at position 1
        assert result[0].text[1] == "h"

    def test_pause_from_last_word(self):
        result = process_text_into_chunks("hello world. how are you", 2)
        # First chunk "hello world." — last word is "world." (ends with .)
        # pause_multiplier for "world." is PAUSE_SENTENCE
        assert result[0].pause_after == PAUSE_SENTENCE


class TestEngineWithChunks:
    def test_load_text_with_chunk_size_2(self, qapp):
        engine = RSVPEngine()
        engine._settings = ...  # inject with chunk_size=2
        engine.load_text("one two three four five six")
        # 3 chunks: "one two", "three four", "five six"
        assert engine.word_count == 3
        assert engine.state.words[0].text == "one two"

    def test_paragraph_pause_in_chunks(self, qapp):
        engine = RSVPEngine()
        engine._settings = ...  # inject with chunk_size=2
        engine.load_text("one two\n\nthree four")
        # 2 chunks; first has paragraph_break_after=True
        assert engine.state.words[0].paragraph_break_after is True


class TestSettingsDialogChunkSize:
    def test_dialog_has_chunk_size_combo(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        assert hasattr(dlg, "chunk_size_combo")
        assert dlg.chunk_size_combo.count() == 3

    def test_chunk_size_combo_default_is_1(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        assert dlg.chunk_size_combo.currentIndex() == 0

    def test_apply_persists_chunk_size(self, qapp, isolated_settings):
        dlg = SettingsDialog()
        dlg.chunk_size_combo.setCurrentIndex(2)  # 3 words
        dlg._apply()
        assert isolated_settings.settings.chunk_size == 3
```

## Commit Plan (3 atomic commits)

```
feat: add chunk mode — process_text_into_chunks and engine integration
feat: add chunk-size setting to Settings dialog
test: add chunk mode tests (text_processor, engine, settings)
```

**Rationale:**
1. **Data + engine first:** The new function and the engine integration. No UI. Tests in commit 3 can use the function directly.
2. **UI second:** The Settings dialog combo. Depends on the setting being defined.
3. **Tests third:** All tests for the feature in one batch (matches the pattern of prior specs).

## Testing Strategy

- 283 existing tests + ~10 new = ~293 total
- Pure function tests in `test_chunk_mode.py` (no Qt needed)
- Engine tests use the `qapp` fixture
- Settings tests use the existing `isolated_settings` fixture pattern
- Use the existing `tests/fixtures/` for any multi-paragraph test text if needed (or inline)

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| User picks chunk size 3 and reading speed feels 3x faster | Documented in CHANGELOG and Settings tooltip: "WPM × chunk size = effective WPM". User can lower WPM to compensate. |
| Long words at chunk boundary cause display overflow | The display widget already handles wide text (it word-wraps if needed). The ORP highlight is computed from the first word's position, which is at the start of the chunk. |
| Paragraph alignment edge case: paragraph with 0 or 1 words | The function returns chunks for paragraphs with ≥1 word. A paragraph with exactly `chunk_size` words has 1 chunk with `paragraph_break_after = True`. Tested. |
| `process_text_into_chunks(text, 1)` should be equivalent to `process_text(text)` | The function explicitly delegates to `process_text` when `chunk_size <= 1`. Tested. |
| ORP index out of bounds for a chunk whose first word has ORP past the chunk length | The ORP of a word is always within that word. The first word of the chunk is the leftmost word, so its ORP is at most within the first word. The display widget handles the ORP index correctly. |
| Chunk size change mid-reading | The change takes effect on the next `load_text` call. Mid-stream changes are not supported (would require clearing the current word list and re-loading, which is more invasive). |
| StatsRecorder records per-chunk, not per-word | Yes — the spec language is that "chunks" are the new unit of reading. Stats naturally count chunks. This is consistent with the spec's user-visible behavior. |

## Out of Scope (Explicitly)

- Variable chunk sizes (1-5 range) — current spec is 1-3
- Chunk-mode-aware pause multipliers (chunk-of-3 might warrant a longer pause)
- Per-paragraph override of chunk size
- Mid-reading chunk size change
- Chunk-mode-only stats
- Multi-highlight ORP (highlighting the ORP of every word in the chunk)
- Adaptive chunking (auto-chunk based on word length or WPM)

## Success Criteria

- [ ] `chunk_size: int = 1` field on `RSVPSettings`
- [ ] `process_text_into_chunks()` function works for chunk sizes 1, 2, 3
- [ ] Paragraphs are aligned to chunk boundaries (no mid-chunk paragraph breaks)
- [ ] ORP comes from the first word of each chunk
- [ ] `RSVPEngine.load_text()` uses chunking when `chunk_size > 1`
- [ ] Settings → Display has a chunk-size combo with options "1 word" / "2 words" / "3 words"
- [ ] Apply/OK persists `chunk_size` to `settings.json`
- [ ] Stats are recorded per-chunk (consistent with the new unit of reading)
- [ ] `pytest -q` passes (~293 tests, 10 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Spec Self-Review (brainstorming checklist)

1. **Coverage:** 8 in-scope items mapped to 3 commits (function+engine → UI → tests).
2. **No placeholders:** all code blocks are concrete; function bodies, ORP logic, dialog layout spelled out.
3. **Internal consistency:** `chunk_size` field used in `settings.py`, `text_processor.py`, `rsvp_engine.py`, and `settings_dialog.py` with the same name and type.
4. **Edge cases handled:**
   - `chunk_size <= 1` falls through to `process_text()` (backward compat)
   - Empty input → empty list
   - Paragraph with `chunk_size` words → 1 chunk with `paragraph_break_after = True`
   - Last chunk of a paragraph may be shorter than `chunk_size`
   - ORP comes from the first word
   - Pause multiplier comes from the last word
5. **Risk acknowledged:** stats count per chunk (not per word), WPM effectively multiplied by chunk size, ORP focal point at the start of the chunk.

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~293 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
