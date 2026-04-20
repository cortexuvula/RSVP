# RSVP v1.2.0 Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 6 improvements from IMPROVEMENT_REPORT.md (items 4.1–4.6): settings error recovery, pause at paragraphs, auto-save position, multi-format file input, keyboard accessibility, and CI improvements.

**Architecture:** Four feature clusters implemented bottom-up. Cluster 1 (settings/engine) lands first because later clusters depend on it. Each task follows TDD: write failing test → implement → verify → commit.

**Tech Stack:** Python 3.10+, PyQt6, pytest, pytest-qt, beautifulsoup4, ebooklib (new), pymupdf (new)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `rsvp/core/settings.py` | Modify | Error recovery, saved_positions field, position methods |
| `rsvp/core/text_processor.py` | Modify | paragraph_break_after field, strip_markdown, format dispatch, epub/pdf loaders |
| `rsvp/core/rsvp_engine.py` | Modify | Paragraph pause in timer interval |
| `rsvp/ui/main_window.py` | Modify | Reset notification, auto-save position UI, eventFilter, tab order |
| `rsvp/ui/controls.py` | Modify | Focus policies on SpeedControl |
| `rsvp/ui/settings_dialog.py` | Modify | Behavior checkboxes |
| `rsvp/ui/text_input_dialog.py` | Modify | File filter strings |
| `rsvp/__init__.py` | Modify | Version bump |
| `pyproject.toml` | Modify | Dependencies, version |
| `.github/workflows/build.yml` | Modify | Coverage, macOS matrix |
| `tests/test_settings.py` | Modify | Error recovery tests, position tests |
| `tests/test_text_processor.py` | Modify | Paragraph detection, markdown, format dispatch, epub, pdf tests |
| `tests/test_rsvp_engine.py` | Modify | Paragraph pause tests |
| `tests/fixtures/` | Create | Test fixture files (.md, .html, .epub, .pdf) |

---

## Task 1: Settings Error Recovery (4.4)

**Files:**
- Modify: `rsvp/core/settings.py:38-83`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests for backup and reset flag**

Add to `tests/test_settings.py`:

```python
import sys

class TestSettingsErrorRecovery:
    """Tests for corrupted settings recovery."""

    @pytest.fixture
    def manager(self, tmp_path):
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._config_path = tmp_path / "settings.json"
        mgr._settings_were_reset = False
        return mgr

    def test_corrupted_json_creates_backup(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        backup = manager._config_path.parent / "settings.json.bak"
        assert backup.exists()
        assert backup.read_text() == "not json{{{"

    def test_corrupted_json_sets_reset_flag(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.was_reset() is True

    def test_was_reset_clears_after_read(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.was_reset() is True
        assert manager.was_reset() is False

    def test_was_reset_false_on_clean_load(self, manager):
        manager._config_path.write_text(json.dumps({"wpm": 400}))
        manager.load()
        assert manager.was_reset() is False

    def test_corrupted_json_logs_to_stderr(self, manager, capsys):
        manager._config_path.write_text("not json{{{")
        manager.load()
        captured = capsys.readouterr()
        assert "corrupted" in captured.err.lower() or "reset" in captured.err.lower()

    def test_corrupted_json_uses_defaults(self, manager):
        manager._config_path.write_text("not json{{{")
        manager.load()
        assert manager.settings.wpm == 300
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py::TestSettingsErrorRecovery -v`
Expected: FAIL — `was_reset` method doesn't exist, no backup created

- [ ] **Step 3: Implement error recovery in SettingsManager**

In `rsvp/core/settings.py`, update `__init__`:

```python
def __init__(self):
    self._settings = RSVPSettings()
    self._settings_were_reset = False
    self._config_path = self._get_config_path()
    self.load()
```

Update `load()`:

```python
def load(self):
    """Load settings from file."""
    if self._config_path.exists():
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(self._settings, key):
                        setattr(self._settings, key, value)
        except (json.JSONDecodeError, IOError):
            import shutil
            import sys
            backup_path = self._config_path.with_suffix('.json.bak')
            try:
                shutil.copy2(self._config_path, backup_path)
            except IOError:
                pass
            print(
                f"Settings file corrupted, reset to defaults. Backup: {backup_path}",
                file=sys.stderr,
            )
            self._settings_were_reset = True
```

Add `was_reset()` method after `load()`:

```python
def was_reset(self) -> bool:
    """Check if settings were reset due to corruption. Clears the flag after reading."""
    result = self._settings_were_reset
    self._settings_were_reset = False
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py -v`
Expected: All pass including new and existing tests

- [ ] **Step 5: Commit**

```bash
git add rsvp/core/settings.py tests/test_settings.py
git commit -m "feat: add error recovery for corrupted settings (4.4)"
```

---

## Task 2: Paragraph Break Detection in Text Processor (4.1a core)

**Files:**
- Modify: `rsvp/core/text_processor.py:7-99`
- Modify: `tests/test_text_processor.py`

- [ ] **Step 1: Write failing tests for paragraph_break_after**

Add to `tests/test_text_processor.py`:

```python
class TestParagraphBreakDetection:
    """Tests for paragraph break detection in process_text."""

    def test_no_paragraph_breaks(self):
        words = process_text("Hello world")
        assert all(w.paragraph_break_after is False for w in words)

    def test_single_paragraph_break(self):
        words = process_text("First paragraph.\n\nSecond paragraph.")
        # "paragraph." (index 1) should be marked
        assert words[1].paragraph_break_after is True
        assert words[1].text == "paragraph."
        # Other words should not be marked
        assert words[0].paragraph_break_after is False
        assert words[2].paragraph_break_after is False
        assert words[3].paragraph_break_after is False

    def test_multiple_paragraph_breaks(self):
        words = process_text("One.\n\nTwo.\n\nThree.")
        assert words[0].paragraph_break_after is True  # "One."
        assert words[1].paragraph_break_after is True  # "Two."
        assert words[2].paragraph_break_after is False  # "Three." (last paragraph)

    def test_last_paragraph_not_marked(self):
        words = process_text("First para.\n\nSecond para.")
        last_word = words[-1]
        assert last_word.paragraph_break_after is False

    def test_extra_blank_lines(self):
        words = process_text("One.\n\n\n\nTwo.")
        assert words[0].paragraph_break_after is True

    def test_blank_line_with_spaces(self):
        words = process_text("One.\n   \nTwo.")
        assert words[0].paragraph_break_after is True

    def test_preserves_existing_word_properties(self):
        words = process_text("Hello.\n\nWorld!")
        assert words[0].text == "Hello."
        assert words[0].pause_after == 2.5
        assert words[0].orp_index == 1
        assert words[1].text == "World!"
        assert words[1].pause_after == 2.5

    def test_empty_paragraph_skipped(self):
        words = process_text("\n\nHello\n\n")
        assert len(words) == 1
        assert words[0].text == "Hello"
        assert words[0].paragraph_break_after is False

    def test_single_word_paragraph(self):
        words = process_text("One.\n\nTwo.\n\nThree.")
        assert len(words) == 3
        assert words[0].text == "One."
        assert words[0].paragraph_break_after is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestParagraphBreakDetection -v`
Expected: FAIL — Word dataclass doesn't have `paragraph_break_after` field

- [ ] **Step 3: Add paragraph_break_after to Word and update process_text**

In `rsvp/core/text_processor.py`, update the `Word` dataclass:

```python
@dataclass
class Word:
    """Represents a word with its optimal recognition point (ORP)."""
    text: str
    orp_index: int
    pause_after: float
    paragraph_break_after: bool = False

    @property
    def before_orp(self) -> str:
        """Text before the ORP character."""
        return self.text[:self.orp_index]

    @property
    def orp_char(self) -> str:
        """The ORP character."""
        return self.text[self.orp_index] if self.orp_index < len(self.text) else ""

    @property
    def after_orp(self) -> str:
        """Text after the ORP character."""
        return self.text[self.orp_index + 1:] if self.orp_index < len(self.text) else ""
```

Replace `process_text()`:

```python
def process_text(text: str) -> list[Word]:
    """
    Process text into a list of Word objects.

    Splits text on whitespace and calculates ORP and pause for each word.
    Detects paragraph boundaries (double newlines) and marks the last word
    of each paragraph (except the final one) with paragraph_break_after=True.
    """
    if not text or not text.strip():
        return []

    paragraphs = re.split(r'\n\s*\n', text)

    all_words: list[Word] = []
    paragraph_end_indices: list[int] = []

    for para in paragraphs:
        normalized = re.sub(r'\s+', ' ', para.strip())
        if not normalized:
            continue
        para_start = len(all_words)
        for raw_word in normalized.split():
            if raw_word:
                orp = calculate_orp(raw_word)
                pause = calculate_pause_multiplier(raw_word)
                all_words.append(Word(text=raw_word, orp_index=orp, pause_after=pause))
        if len(all_words) > para_start:
            paragraph_end_indices.append(len(all_words) - 1)

    for idx in paragraph_end_indices[:-1]:
        all_words[idx].paragraph_break_after = True

    return all_words
```

- [ ] **Step 4: Run all text processor tests**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py -v`
Expected: All pass — both new paragraph tests and existing tests

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add rsvp/core/text_processor.py tests/test_text_processor.py
git commit -m "feat: detect paragraph breaks in text processing (4.1a)"
```

---

## Task 3: Paragraph Pause in Engine + Settings Dialog (4.1a engine/UI)

**Files:**
- Modify: `rsvp/core/rsvp_engine.py:215-226`
- Modify: `rsvp/ui/settings_dialog.py:97-105`
- Modify: `tests/test_rsvp_engine.py`

- [ ] **Step 1: Write failing tests for paragraph pause**

Add to `tests/test_rsvp_engine.py`:

```python
class TestRSVPEngineParagraphPause:
    """Tests for paragraph pause in timer interval."""

    def test_paragraph_break_multiplies_interval(self, qapp):
        engine = RSVPEngine()
        engine.load_text("End.\n\nStart")
        # "End." is at index 0 with paragraph_break_after=True
        assert engine.state.words[0].paragraph_break_after is True
        engine._state.wpm = 300
        engine._update_timer_interval()
        # 200ms * 2.5 (period) * 3.0 (paragraph) = 1500ms
        assert engine._timer.interval() == 1500

    def test_no_paragraph_break_no_extra_pause(self, qapp):
        engine = RSVPEngine()
        engine.load_text("Hello world")
        engine._state.wpm = 300
        engine._update_timer_interval()
        # 200ms * 1.0 = 200ms (no paragraph break)
        assert engine._timer.interval() == 200

    def test_paragraph_pause_disabled_in_settings(self, qapp):
        from rsvp.core.settings import get_settings_manager
        manager = get_settings_manager()
        original = manager.settings.pause_at_paragraphs
        try:
            manager.settings.pause_at_paragraphs = False
            engine = RSVPEngine()
            engine.load_text("End.\n\nStart")
            engine._state.wpm = 300
            engine._update_timer_interval()
            # 200ms * 2.5 = 500ms (no paragraph multiplier)
            assert engine._timer.interval() == 500
        finally:
            manager.settings.pause_at_paragraphs = original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_rsvp_engine.py::TestRSVPEngineParagraphPause -v`
Expected: FAIL — engine doesn't apply paragraph multiplier

- [ ] **Step 3: Implement paragraph pause in engine**

In `rsvp/core/rsvp_engine.py`, add the settings import at top:

```python
from rsvp.core.settings import get_settings_manager
```

Update `_update_timer_interval()`:

```python
def _update_timer_interval(self):
    """Update timer interval based on WPM and current word."""
    base_interval = 60000 / self._state.wpm  # Base ms per word

    current = self._state.current_word
    if current:
        interval = base_interval * current.pause_after
        if current.paragraph_break_after and get_settings_manager().settings.pause_at_paragraphs:
            interval *= 3.0
    else:
        interval = base_interval

    self._timer.setInterval(int(interval))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_rsvp_engine.py -v`
Expected: All pass

- [ ] **Step 5: Add behavior checkboxes to SettingsDialog**

In `rsvp/ui/settings_dialog.py`, update `_setup_ui()` — add after the always_on_top checkbox (inside the behavior group):

```python
self.pause_paragraphs_check = QCheckBox()
behavior_layout.addRow("Pause at paragraph breaks:", self.pause_paragraphs_check)

self.auto_save_check = QCheckBox()
behavior_layout.addRow("Remember reading position:", self.auto_save_check)
```

Update `_load_settings()` — add:

```python
self.pause_paragraphs_check.setChecked(settings.pause_at_paragraphs)
self.auto_save_check.setChecked(settings.auto_save_position)
```

Update `_apply()` — add:

```python
settings.pause_at_paragraphs = self.pause_paragraphs_check.isChecked()
settings.auto_save_position = self.auto_save_check.isChecked()
```

- [ ] **Step 6: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add rsvp/core/rsvp_engine.py rsvp/ui/settings_dialog.py tests/test_rsvp_engine.py
git commit -m "feat: implement pause at paragraph breaks (4.1a)"
```

---

## Task 4: Auto-Save Position — Settings Layer (4.1b core)

**Files:**
- Modify: `rsvp/core/settings.py:8-36, 107-127`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests for position methods**

Add to `tests/test_settings.py`:

```python
class TestSettingsPositionTracking:
    """Tests for save/get/clear position methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        mgr = SettingsManager.__new__(SettingsManager)
        mgr._settings = RSVPSettings()
        mgr._settings_were_reset = False
        mgr._config_path = tmp_path / "settings.json"
        return mgr

    def test_save_and_get_position(self, manager):
        manager.save_position("/file.txt", 42)
        assert manager.get_position("/file.txt") == 42

    def test_get_position_unknown_source(self, manager):
        assert manager.get_position("/nonexistent.txt") is None

    def test_save_position_overwrites(self, manager):
        manager.save_position("/file.txt", 10)
        manager.save_position("/file.txt", 50)
        assert manager.get_position("/file.txt") == 50

    def test_clear_position(self, manager):
        manager.save_position("/file.txt", 42)
        manager.clear_position("/file.txt")
        assert manager.get_position("/file.txt") is None

    def test_clear_position_nonexistent(self, manager):
        manager.clear_position("/nonexistent.txt")  # should not crash

    def test_save_position_persists(self, manager):
        manager.save_position("/file.txt", 42)
        assert manager._config_path.exists()
        data = json.loads(manager._config_path.read_text())
        assert data["saved_positions"] == {"/file.txt": 42}

    def test_multiple_sources(self, manager):
        manager.save_position("/a.txt", 10)
        manager.save_position("/b.txt", 20)
        assert manager.get_position("/a.txt") == 10
        assert manager.get_position("/b.txt") == 20

    def test_default_saved_positions_empty(self):
        s = RSVPSettings()
        assert s.saved_positions == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py::TestSettingsPositionTracking -v`
Expected: FAIL — `saved_positions` field and methods don't exist

- [ ] **Step 3: Add saved_positions field and methods**

In `rsvp/core/settings.py`, add to `RSVPSettings` after the bookmarks field:

```python
    # Saved reading positions: maps source path/URL to word index
    saved_positions: dict[str, int] = field(default_factory=dict)
```

Add methods to `SettingsManager` after `get_bookmarks()`:

```python
    def save_position(self, source: str, index: int):
        """Save reading position for a source."""
        self._settings.saved_positions[source] = index
        self.save()

    def get_position(self, source: str) -> int | None:
        """Get saved reading position for a source."""
        return self._settings.saved_positions.get(source)

    def clear_position(self, source: str):
        """Clear saved reading position for a source."""
        self._settings.saved_positions.pop(source, None)
        self.save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_settings.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add rsvp/core/settings.py tests/test_settings.py
git commit -m "feat: add saved reading positions to settings (4.1b)"
```

---

## Task 5: Auto-Save Position — UI Layer (4.1b UI)

**Files:**
- Modify: `rsvp/ui/main_window.py`

- [ ] **Step 1: Add position save helper**

Add to `MainWindow` class:

```python
def _maybe_save_position(self):
    """Save current reading position if auto-save is enabled."""
    manager = get_settings_manager()
    if not manager.settings.auto_save_position:
        return
    if self._current_file and self._engine.current_index > 0:
        manager.save_position(self._current_file, self._engine.current_index)
```

- [ ] **Step 2: Add position resume helper**

Add to `MainWindow` class:

```python
def _maybe_resume_position(self, source: str):
    """Offer to resume from saved position if available."""
    manager = get_settings_manager()
    if not manager.settings.auto_save_position or not source:
        return
    saved_index = manager.get_position(source)
    if saved_index is not None and saved_index > 0 and saved_index < self._engine.word_count:
        reply = QMessageBox.question(
            self,
            "Resume Reading",
            f"Resume from word {saved_index} of {self._engine.word_count}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._engine.seek(saved_index)
```

- [ ] **Step 3: Wire into _load_text_dialog**

Update `_load_text_dialog()` — add after `self.status_label.setText(...)`:

```python
            self._maybe_resume_position(source)
```

- [ ] **Step 4: Wire into _load_file**

Update `_load_file()` — add before the except block, after `self.status_label.setText(...)`:

```python
            self._maybe_resume_position(filepath)
```

- [ ] **Step 5: Save position before loading new text and on close**

Update `_load_text_dialog()` — add at the very start of the method, before `dialog = TextInputDialog(self)`:

```python
        self._maybe_save_position()
```

Update `_load_file()` — add at the very start of the method, before `try:`:

```python
        self._maybe_save_position()
```

Update `closeEvent()`:

```python
def closeEvent(self, event):
    """Handle window close."""
    self._maybe_save_position()
    self._save_window_settings()
    event.accept()
```

- [ ] **Step 6: Clear position on finish**

Update `_on_finished()`:

```python
def _on_finished(self):
    """Handle finished signal."""
    self.status_label.setText("Finished reading")
    if self._current_file:
        get_settings_manager().clear_position(self._current_file)
```

- [ ] **Step 7: Add reset notification on startup**

Update `__init__()` — add after `self._load_window_settings()`:

```python
        self._check_settings_reset()
```

Add the method:

```python
def _check_settings_reset(self):
    """Show notification if settings were reset due to corruption."""
    if get_settings_manager().was_reset():
        QMessageBox.warning(
            self,
            "Settings Reset",
            "Your settings file was corrupted and has been reset to defaults. "
            "A backup was saved to settings.json.bak.",
        )
```

- [ ] **Step 8: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add rsvp/ui/main_window.py
git commit -m "feat: implement auto-save reading position and reset notification (4.1b, 4.4)"
```

---

## Task 6: Markdown Stripping (4.3 part 1)

**Files:**
- Modify: `rsvp/core/text_processor.py`
- Modify: `tests/test_text_processor.py`

- [ ] **Step 1: Write failing tests for strip_markdown**

Add to `tests/test_text_processor.py`:

```python
from rsvp.core.text_processor import strip_markdown

class TestStripMarkdown:
    """Tests for Markdown syntax stripping."""

    def test_strips_h1(self):
        assert strip_markdown("# Hello World").strip() == "Hello World"

    def test_strips_h3(self):
        assert strip_markdown("### Section Title").strip() == "Section Title"

    def test_strips_bold(self):
        assert "important" in strip_markdown("This is **important** text")
        assert "**" not in strip_markdown("This is **important** text")

    def test_strips_italic(self):
        assert "emphasis" in strip_markdown("This is *emphasis* here")
        assert strip_markdown("This is *emphasis* here").count("*") == 0

    def test_strips_underscore_bold(self):
        result = strip_markdown("This is __bold__ text")
        assert "bold" in result
        assert "__" not in result

    def test_strips_links_keeps_text(self):
        result = strip_markdown("Click [here](https://example.com) please")
        assert "here" in result
        assert "https://example.com" not in result
        assert "[" not in result

    def test_strips_images_keeps_alt(self):
        result = strip_markdown("An image ![alt text](img.png) follows")
        assert "alt text" in result
        assert "img.png" not in result

    def test_strips_inline_code(self):
        result = strip_markdown("Run `npm install` now")
        assert "npm install" in result
        assert "`" not in result

    def test_strips_code_blocks(self):
        md = "Before\n```python\nprint('hello')\n```\nAfter"
        result = strip_markdown(md)
        assert "Before" in result
        assert "After" in result
        assert "```" not in result

    def test_strips_horizontal_rules(self):
        result = strip_markdown("Above\n---\nBelow")
        assert "Above" in result
        assert "Below" in result
        assert "---" not in result

    def test_strips_html_tags(self):
        result = strip_markdown("Some <em>html</em> content")
        assert "html" in result
        assert "<em>" not in result

    def test_preserves_plain_text(self):
        text = "This is plain text with no markdown."
        assert strip_markdown(text).strip() == text

    def test_empty_string(self):
        assert strip_markdown("") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestStripMarkdown -v`
Expected: FAIL — `strip_markdown` not importable

- [ ] **Step 3: Implement strip_markdown**

Add to `rsvp/core/text_processor.py` after `calculate_pause_multiplier()` and before `process_text()`:

```python
def strip_markdown(text: str) -> str:
    """Strip Markdown syntax, keeping readable text."""
    # Code blocks (fenced)
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Images (keep alt text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # Links (keep link text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Bold + italic combined
    text = re.sub(r'\*{3}([^*]+)\*{3}', r'\1', text)
    text = re.sub(r'_{3}([^_]+)_{3}', r'\1', text)
    # Bold
    text = re.sub(r'\*{2}([^*]+)\*{2}', r'\1', text)
    text = re.sub(r'_{2}([^_]+)_{2}', r'\1', text)
    # Italic
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'_([^_\s]+)_', r'\1', text)
    # Horizontal rules
    text = re.sub(r'^[\-\*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestStripMarkdown -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add rsvp/core/text_processor.py tests/test_text_processor.py
git commit -m "feat: add strip_markdown function (4.3)"
```

---

## Task 7: File Format Dispatch + HTML File Loading (4.3 part 2)

**Files:**
- Modify: `rsvp/core/text_processor.py:121-124`
- Modify: `tests/test_text_processor.py`

- [ ] **Step 1: Write failing tests for format dispatch**

Add to `tests/test_text_processor.py`:

```python
class TestFileFormatDispatch:
    """Tests for load_text_from_file format routing."""

    def test_loads_txt(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Plain text content", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert result == "Plain text content"

    def test_loads_markdown(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Title" in result
        assert "**" not in result
        assert "#" not in result

    def test_loads_html(self, tmp_path):
        f = tmp_path / "test.html"
        f.write_text("<html><body><p>Hello world</p></body></html>", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Hello world" in result
        assert "<p>" not in result

    def test_loads_htm(self, tmp_path):
        f = tmp_path / "test.htm"
        f.write_text("<p>HTM content</p>", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "HTM content" in result

    def test_unknown_extension_reads_as_text(self, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("raw content", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert result == "raw content"

    def test_case_insensitive_extension(self, tmp_path):
        f = tmp_path / "test.MD"
        f.write_text("# Header\n\nContent", encoding="utf-8")
        result = load_text_from_file(str(f))
        assert "Header" in result
        assert "#" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestFileFormatDispatch -v`
Expected: FAIL — markdown files are read as raw text, HTML files are read as raw text

- [ ] **Step 3: Refactor load_text_from_file for dispatch**

In `rsvp/core/text_processor.py`, add `from pathlib import Path` to the imports at the top (after `from typing import Optional`).

Replace `load_text_from_file()`:

```python
def load_text_from_file(filepath: str) -> str:
    """Load text from a file, dispatching by extension."""
    ext = Path(filepath).suffix.lower()

    if ext == '.md':
        with open(filepath, 'r', encoding='utf-8') as f:
            return strip_markdown(f.read())
    elif ext in ('.html', '.htm'):
        with open(filepath, 'r', encoding='utf-8') as f:
            return extract_text_from_html(f.read())
    elif ext == '.epub':
        return load_text_from_epub(filepath)
    elif ext == '.pdf':
        return load_text_from_pdf(filepath)
    else:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
```

Add stub functions (will be implemented in Tasks 8 and 9):

```python
def load_text_from_epub(filepath: str) -> str:
    """Load text from an EPUB file."""
    raise ValueError("EPUB support requires 'ebooklib'. Install with: pip install ebooklib")


def load_text_from_pdf(filepath: str) -> str:
    """Load text from a PDF file."""
    raise ValueError("PDF support requires 'pymupdf'. Install with: pip install pymupdf")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py -v`
Expected: All pass (dispatch tests + existing tests)

- [ ] **Step 5: Commit**

```bash
git add rsvp/core/text_processor.py tests/test_text_processor.py
git commit -m "feat: add file format dispatch for .md and .html (4.3)"
```

---

## Task 8: EPUB Support (4.3 part 3)

**Files:**
- Modify: `rsvp/core/text_processor.py`
- Modify: `pyproject.toml`
- Create: `tests/fixtures/test.epub`
- Modify: `tests/test_text_processor.py`

- [ ] **Step 1: Install ebooklib**

```bash
pip install ebooklib>=0.18
```

- [ ] **Step 2: Create a minimal test EPUB fixture**

```python
# Run this once to create the fixture
import ebooklib
from ebooklib import epub

book = epub.EpubBook()
book.set_identifier('test123')
book.set_title('Test Book')
book.set_language('en')

c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
c1.content = '<html><body><h1>Chapter One</h1><p>First chapter content here.</p></body></html>'

c2 = epub.EpubHtml(title='Chapter 2', file_name='ch2.xhtml', lang='en')
c2.content = '<html><body><h1>Chapter Two</h1><p>Second chapter content here.</p></body></html>'

book.add_item(c1)
book.add_item(c2)
book.spine = ['nav', c1, c2]
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

epub.write_epub('tests/fixtures/test.epub', book)
```

Run: `mkdir -p tests/fixtures && python -c "..."` (the above script)

- [ ] **Step 3: Write failing test for EPUB loading**

Add to `tests/test_text_processor.py`:

```python
import os

class TestLoadEpub:
    """Tests for EPUB file loading."""

    @pytest.fixture
    def epub_path(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "test.epub")
        if not os.path.exists(path):
            pytest.skip("test.epub fixture not found")
        return path

    def test_loads_epub_text(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "Chapter One" in result
        assert "First chapter content" in result

    def test_epub_has_multiple_chapters(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "Chapter One" in result
        assert "Chapter Two" in result
        assert "Second chapter content" in result

    def test_epub_strips_html(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "<html>" not in result
        assert "<body>" not in result
        assert "<h1>" not in result

    def test_epub_chapters_separated(self, epub_path):
        result = load_text_from_file(epub_path)
        assert "\n\n" in result
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestLoadEpub -v`
Expected: FAIL — `load_text_from_epub` raises ValueError stub

- [ ] **Step 5: Implement load_text_from_epub**

In `rsvp/core/text_processor.py`, replace the `load_text_from_epub` stub:

```python
def load_text_from_epub(filepath: str) -> str:
    """Load text from an EPUB file."""
    try:
        import ebooklib
        from ebooklib import epub
    except ImportError:
        raise ValueError("EPUB support requires 'ebooklib'. Install with: pip install ebooklib")

    book = epub.read_epub(filepath)
    chapters = []

    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_content().decode('utf-8', errors='replace')
            text = extract_text_from_html(content)
            if text.strip():
                chapters.append(text.strip())

    if not chapters:
        raise ValueError("No readable text found in EPUB file")

    return '\n\n'.join(chapters)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestLoadEpub -v`
Expected: All pass

- [ ] **Step 7: Add ebooklib to pyproject.toml**

In `pyproject.toml`, add to `dependencies`:

```toml
    "ebooklib>=0.18",
```

- [ ] **Step 8: Commit**

```bash
git add rsvp/core/text_processor.py tests/test_text_processor.py tests/fixtures/test.epub pyproject.toml
git commit -m "feat: add EPUB file support (4.3)"
```

---

## Task 9: PDF Support (4.3 part 4)

**Files:**
- Modify: `rsvp/core/text_processor.py`
- Modify: `pyproject.toml`
- Create: `tests/fixtures/test.pdf`
- Modify: `tests/test_text_processor.py`

- [ ] **Step 1: Install pymupdf**

```bash
pip install pymupdf>=1.23.0
```

- [ ] **Step 2: Create a minimal test PDF fixture**

```python
# Run this once to create the fixture
import fitz

doc = fitz.open()
page1 = doc.new_page()
page1.insert_text((72, 72), "Page one content for testing.", fontsize=12)
page2 = doc.new_page()
page2.insert_text((72, 72), "Page two content for testing.", fontsize=12)
doc.save("tests/fixtures/test.pdf")
doc.close()
```

Run: `python -c "..."` (the above script)

- [ ] **Step 3: Write failing test for PDF loading**

Add to `tests/test_text_processor.py`:

```python
class TestLoadPdf:
    """Tests for PDF file loading."""

    @pytest.fixture
    def pdf_path(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "test.pdf")
        if not os.path.exists(path):
            pytest.skip("test.pdf fixture not found")
        return path

    def test_loads_pdf_text(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "Page one content" in result

    def test_pdf_has_multiple_pages(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "Page one content" in result
        assert "Page two content" in result

    def test_pdf_pages_separated(self, pdf_path):
        result = load_text_from_file(pdf_path)
        assert "\n\n" in result
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestLoadPdf -v`
Expected: FAIL — `load_text_from_pdf` raises ValueError stub

- [ ] **Step 5: Implement load_text_from_pdf**

In `rsvp/core/text_processor.py`, replace the `load_text_from_pdf` stub:

```python
def load_text_from_pdf(filepath: str) -> str:
    """Load text from a PDF file."""
    try:
        import fitz
    except ImportError:
        raise ValueError("PDF support requires 'pymupdf'. Install with: pip install pymupdf")

    doc = fitz.open(filepath)
    pages = []

    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())

    doc.close()

    if not pages:
        raise ValueError("No readable text found in PDF file")

    return '\n\n'.join(pages)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/test_text_processor.py::TestLoadPdf -v`
Expected: All pass

- [ ] **Step 7: Add pymupdf to pyproject.toml**

In `pyproject.toml`, add to `dependencies`:

```toml
    "pymupdf>=1.23.0",
```

- [ ] **Step 8: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 9: Commit**

```bash
git add rsvp/core/text_processor.py tests/test_text_processor.py tests/fixtures/test.pdf pyproject.toml
git commit -m "feat: add PDF file support (4.3)"
```

---

## Task 10: Update File Dialog Filters (4.3 part 5)

**Files:**
- Modify: `rsvp/ui/text_input_dialog.py:127-134`
- Modify: `rsvp/ui/main_window.py:308-315`

- [ ] **Step 1: Update TextInputDialog file filter**

In `rsvp/ui/text_input_dialog.py`, update `_browse_file()` — change the filter string:

```python
    def _browse_file(self):
        """Open file browser."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "All Supported (*.txt *.md *.html *.htm *.epub *.pdf);;"
            "Text (*.txt);;"
            "Markdown (*.md);;"
            "HTML (*.html *.htm);;"
            "EPUB (*.epub);;"
            "PDF (*.pdf);;"
            "All Files (*)"
        )
```

- [ ] **Step 2: Update MainWindow file filter**

In `rsvp/ui/main_window.py`, update `_open_file()` — change the filter string:

```python
    def _open_file(self):
        """Open a file directly."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "All Supported (*.txt *.md *.html *.htm *.epub *.pdf);;"
            "Text (*.txt);;"
            "Markdown (*.md);;"
            "HTML (*.html *.htm);;"
            "EPUB (*.epub);;"
            "PDF (*.pdf);;"
            "All Files (*)"
        )

        if filepath:
            self._load_file(filepath)
```

- [ ] **Step 3: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add rsvp/ui/text_input_dialog.py rsvp/ui/main_window.py
git commit -m "feat: update file dialogs for all supported formats (4.3)"
```

---

## Task 11: Focus-Aware Keyboard Navigation (4.5)

**Files:**
- Modify: `rsvp/ui/controls.py:110-148`
- Modify: `rsvp/ui/main_window.py:79-211`

- [ ] **Step 1: Set focus policies on SpeedControl**

In `rsvp/ui/controls.py`, update `SpeedControl._setup_ui()`:

After `self.slider.setTickPosition(...)` (line 129), add:

```python
        self.slider.setFocusPolicy(Qt.FocusPolicy.TabFocus)
```

After `self.spinbox.setSuffix(...)` (line 139), add:

```python
        self.spinbox.setFocusPolicy(Qt.FocusPolicy.TabFocus)
```

Set NoFocus on the +/- buttons — after `self.decrease_btn.setFixedSize(30, 30)` (line 119), add:

```python
        self.decrease_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
```

After `self.increase_btn.setFixedSize(30, 30)` (line 145), add:

```python
        self.increase_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
```

Add visual focus indicator — at the end of `_setup_ui()`:

```python
        self.slider.setStyleSheet("QSlider:focus { border: 1px solid #4A9EFF; }")
```

- [ ] **Step 2: Remove arrow-key shortcuts from menus and shortcuts**

In `rsvp/ui/main_window.py`, update `_setup_menus()`:

Remove the shortcut lines from speed_up_action and speed_down_action. Change:

```python
        speed_up_action = QAction("Speed &Up", self)
        speed_up_action.setShortcut("Up")
        speed_up_action.triggered.connect(self._speed_up)
        playback_menu.addAction(speed_up_action)

        speed_down_action = QAction("Speed &Down", self)
        speed_down_action.setShortcut("Down")
        speed_down_action.triggered.connect(self._speed_down)
        playback_menu.addAction(speed_down_action)
```

To:

```python
        speed_up_action = QAction("Speed &Up (+/Up)", self)
        speed_up_action.triggered.connect(self._speed_up)
        playback_menu.addAction(speed_up_action)

        speed_down_action = QAction("Speed &Down (-/Down)", self)
        speed_down_action.triggered.connect(self._speed_down)
        playback_menu.addAction(speed_down_action)
```

In `_setup_shortcuts()`, remove the Left/Right and Escape QShortcuts. Change to:

```python
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Shift+Left"), self, self._engine.previous_sentence)
        QShortcut(QKeySequence("Shift+Right"), self, self._engine.next_sentence)
        QShortcut(QKeySequence("Home"), self, lambda: self._engine.seek(0))
        QShortcut(QKeySequence("End"), self, lambda: self._engine.seek(self._engine.word_count - 1))
```

- [ ] **Step 3: Add eventFilter and install it**

Add the import to the top of `main_window.py`:

```python
from PyQt6.QtCore import Qt, QEvent
```

In `__init__`, after `self._load_window_settings()` and before `self._check_settings_reset()`, add:

```python
        self.installEventFilter(self)
        self._setup_tab_order()
```

Add the eventFilter method:

```python
    def eventFilter(self, obj, event):
        """Handle focus-aware keyboard navigation."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
                focus = self.focusWidget()
                if focus in (self.speed_control.slider, self.speed_control.spinbox):
                    return False
                if key == Qt.Key.Key_Up:
                    self._speed_up()
                elif key == Qt.Key.Key_Down:
                    self._speed_down()
                elif key == Qt.Key.Key_Left:
                    self._engine.skip_backward()
                elif key == Qt.Key.Key_Right:
                    self._engine.skip_forward()
                return True
            if key == Qt.Key.Key_Escape:
                self._engine.pause()
                self.word_display.setFocus()
                return True
        return super().eventFilter(obj, event)
```

Add the tab order method:

```python
    def _setup_tab_order(self):
        """Set up Tab key navigation order."""
        self.setTabOrder(self.speed_control.slider, self.speed_control.spinbox)
        self.setTabOrder(self.speed_control.spinbox, self.word_display)
```

- [ ] **Step 4: Update shortcuts help dialog**

In `_show_shortcuts()`, update the Escape row and add Tab:

```python
<tr><td><b>Tab</b></td><td>Cycle focus (speed controls)</td></tr>
<tr><td><b>Escape</b></td><td>Pause and return focus to display</td></tr>
```

- [ ] **Step 5: Run full test suite**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add rsvp/ui/controls.py rsvp/ui/main_window.py
git commit -m "feat: add focus-aware keyboard navigation (4.5)"
```

---

## Task 12: CI Improvements (4.2 + 4.6)

**Files:**
- Modify: `.github/workflows/build.yml`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest-cov to dev dependencies**

In `pyproject.toml`, update `[project.optional-dependencies]`:

```toml
dev = [
    "pytest>=7.0.0",
    "pytest-qt>=4.0.0",
    "pytest-cov>=4.0.0",
    "pyinstaller>=5.0.0",
]
```

- [ ] **Step 2: Update build.yml test job with coverage and macOS matrix**

Replace the entire `test` job in `.github/workflows/build.yml`:

```yaml
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ['3.11']

    runs-on: ${{ matrix.os }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install Linux dependencies
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y \
            libxcb-cursor0 \
            libxkbcommon-x11-0 \
            libxcb-icccm4 \
            libxcb-keysyms1 \
            libxcb-xkb1 \
            libegl1 \
            libxcb-shape0 \
            libxcb-xinerama0

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests with coverage
        run: |
          QT_QPA_PLATFORM=offscreen pytest tests/ -v --cov=rsvp --cov-report=xml --cov-report=term-missing
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build.yml pyproject.toml
git commit -m "ci: add coverage reporting and macOS test target (4.2, 4.6)"
```

---

## Task 13: Version Bump to 1.2.0

**Files:**
- Modify: `rsvp/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump version in pyproject.toml**

Change `version = "1.1.0"` to `version = "1.2.0"`.

- [ ] **Step 2: Bump version in __init__.py**

Change `__version__ = "1.1.0"` to `__version__ = "1.2.0"`.

- [ ] **Step 3: Update about dialog version**

In `rsvp/ui/main_window.py`, update `_show_about()`:

Change `"<p>Version 1.1.0</p>"` to `"<p>Version 1.2.0</p>"`.

- [ ] **Step 4: Run full test suite one final time**

Run: `QT_QPA_PLATFORM=offscreen pytest tests/ -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add rsvp/__init__.py pyproject.toml rsvp/ui/main_window.py
git commit -m "chore: bump version to 1.2.0"
```
