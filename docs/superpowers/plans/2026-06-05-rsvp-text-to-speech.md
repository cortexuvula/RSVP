# RSVP Text-to-Speech Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land text-to-speech (pyttsx3, paced to display, settings-controlled) as a single PR with 3 atomic commits, per the [design spec](../specs/2026-06-05-rsvp-text-to-speech-design.md).

**Architecture:** New `rsvp.core.tts` module with `TTSController` (subscribes to engine signals) and a `TTSDriver` Protocol (production = pyttsx3, tests = NullDriver). `MainWindow` wires the controller. Settings → Behavior gets a "Text-to-speech" checkbox.

**Tech Stack:** Python 3.10+, PyQt6, pyttsx3 (new runtime dep). No test-only deps.

---

## File Structure

**Created:**
- `rsvp/core/tts.py` — `TTSDriver` Protocol, `NullDriver`, `Pyttsx3Driver`, `create_tts_driver()`, `TTSController`
- `tests/test_tts.py`

**Modified:**
- `rsvp/core/__init__.py` — re-export
- `rsvp/core/settings.py` — add `tts_enabled: bool = False` to `RSVPSettings`
- `pyproject.toml` — add `pyttsx3>=2.90` to dependencies
- `rsvp/ui/settings_dialog.py` — add "Text-to-speech" checkbox
- `rsvp/ui/main_window.py` — create `TTSController`, wire it, shutdown in `closeEvent`
- `CHANGELOG.md` — `[Unreleased]` entry

---

## Task 1: TTSDriver abstraction + dependency + settings field

**Files:**
- Create: `rsvp/core/tts.py`
- Modify: `rsvp/core/__init__.py`
- Modify: `rsvp/core/settings.py`
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Create `rsvp/core/tts.py`**

```python
"""Text-to-speech integration: speaks each engine word via pyttsx3."""

import logging
from typing import Protocol

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.text_processor import Word

logger = logging.getLogger(__name__)


class TTSDriver(Protocol):
    """Protocol for TTS drivers. Production = Pyttsx3Driver, tests = NullDriver."""

    def say(self, text: str) -> None: ...
    def run_and_wait(self) -> None: ...
    def stop(self) -> None: ...


class NullDriver:
    """No-op driver. Used in tests and as a fallback when pyttsx3 is unavailable."""

    def say(self, text: str) -> None:
        pass

    def run_and_wait(self) -> None:
        pass

    def stop(self) -> None:
        pass


class Pyttsx3Driver:
    """Wraps pyttsx3.init() / say() / runAndWait() / stop()."""

    def __init__(self) -> None:
        import pyttsx3  # imported here so the dep is optional

        self._engine = pyttsx3.init()

    def say(self, text: str) -> None:
        self._engine.say(text)

    def run_and_wait(self) -> None:
        self._engine.runAndWait()

    def stop(self) -> None:
        self._engine.stop()


def create_tts_driver() -> TTSDriver:
    """Create a Pyttsx3Driver if pyttsx3 is importable, else NullDriver.

    Also returns NullDriver if pyttsx3.init() fails (e.g., no TTS engine
    installed on the system).
    """
    try:
        return Pyttsx3Driver()
    except Exception as e:
        logger.warning("Failed to initialize pyttsx3; TTS will be a no-op: %s", e)
        return NullDriver()


class TTSController:
    """Speaks each engine word via the TTS driver, paced to the display WPM.

    Subscribes to RSVPEngine.word_changed and speaks each new word. The
    call is synchronous (say + run_and_wait) — the main thread blocks for
    the duration of each word, which naturally paces the display to the
    TTS rate. The engine's QTimer is the wakeup mechanism; TTS is the
    bottleneck.
    """

    def __init__(self, engine: RSVPEngine, driver: TTSDriver | None = None) -> None:
        self._engine = engine
        self._driver: TTSDriver = driver if driver is not None else NullDriver()
        self._enabled: bool = False
        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """User toggled TTS in Settings. Stops any current utterance if disabling."""
        self._enabled = enabled
        if not enabled:
            self._driver.stop()

    def shutdown(self) -> None:
        """Interrupt any in-progress utterance. Called by MainWindow.closeEvent."""
        self._driver.stop()

    def _on_word_changed(self, word: Word | None) -> None:
        if not self._enabled or word is None:
            return
        self._driver.say(word.text)
        self._driver.run_and_wait()

    def _on_state_changed(self) -> None:
        if not self._enabled:
            return
        if not self._engine.is_playing:
            self._driver.stop()
```

- [ ] **Step 2: Re-export from `rsvp/core/__init__.py`**

Add to the imports block:

```python
from rsvp.core.tts import (
    TTSController,
    TTSDriver,
    NullDriver,
    Pyttsx3Driver,
    create_tts_driver,
)
```

And to `__all__` (alphabetical position):

```python
    "NullDriver",
    "Pyttsx3Driver",
    "TTSController",
    "TTSDriver",
    "create_tts_driver",
```

- [ ] **Step 3: Add `tts_enabled` field to `RSVPSettings`**

In `rsvp/core/settings.py`, add to the Behavior section of the `RSVPSettings` dataclass:

```python
    # Behavior settings
    pause_at_paragraphs: bool = True
    auto_save_position: bool = True
    tts_enabled: bool = False
```

- [ ] **Step 4: Add `pyttsx3` to dependencies**

In `pyproject.toml` under `[project] dependencies`:

```toml
dependencies = [
    "PyQt6>=6.4.0",
    "requests>=2.28.0",
    "beautifulsoup4>=4.11.0",
    "pyperclip>=1.8.0",
    "ebooklib>=0.18",
    "pymupdf>=1.23.0",
    "pyttsx3>=2.90",
]
```

- [ ] **Step 5: Add CHANGELOG entry under `[Unreleased]`**

In `CHANGELOG.md` (create it if missing), add:

```markdown
## [Unreleased]

### Added
- Text-to-speech (TTS): offline, uses the OS default voice via pyttsx3. Each displayed word is spoken as it appears; pause interrupts mid-utterance. Toggle in Settings → Behavior.
```

- [ ] **Step 6: Install pyttsx3 and verify**

Run: `/opt/homebrew/bin/python3.12 -m pip install --break-system-packages pyttsx3 2>&1 | tail -3`
Then: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_settings.py -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: existing settings tests pass; ruff clean.

- [ ] **Step 7: Commit**

```bash
git add rsvp/core/tts.py rsvp/core/__init__.py rsvp/core/settings.py pyproject.toml CHANGELOG.md
git commit -m "feat: add pyttsx3-based TTS driver abstraction

New rsvp.core.tts module with:
  - TTSDriver Protocol (typing only)
  - NullDriver (no-op, for tests + missing-dep fallback)
  - Pyttsx3Driver (real pyttsx3 wrapper)
  - create_tts_driver() factory (catches ImportError + init failure)
  - TTSController (subscribes to engine.word_changed and
    state_changed, speaks each word synchronously)

Added tts_enabled: bool = False to RSVPSettings. Default off so
existing users see no change. No migration needed (setattr-with-
hasattr load pattern handles missing fields).

Added pyttsx3>=2.90 to runtime dependencies. create_tts_driver()
gracefully falls back to NullDriver if pyttsx3 isn't installed or
the OS has no TTS engine (e.g., headless Linux without espeak).

TTSController API:
  - set_enabled(True/False) - user toggle; calls stop() when disabling
  - shutdown() - clean interrupt; called by MainWindow.closeEvent
  - _on_word_changed - speaks the new word (synchronous)
  - _on_state_changed - interrupts TTS when engine pauses/stops

CHANGELOG entry under [Unreleased] notes the new feature."
```

---

## Task 2: SettingsDialog checkbox + MainWindow wiring

**Files:**
- Modify: `rsvp/ui/settings_dialog.py`
- Modify: `rsvp/ui/main_window.py`

- [ ] **Step 1: Add "Text-to-speech" checkbox to SettingsDialog**

In `rsvp/ui/settings_dialog.py`, find the Behavior group `_setup_ui` section. After `self.auto_save_check = QCheckBox()` and before the next widget, add:

```python
        self.tts_check = QCheckBox()
        behavior_layout.addRow("Text-to-speech:", self.tts_check)
```

In `_load_settings`, after `self.auto_save_check.setChecked(settings.auto_save_position)`, add:

```python
        self.tts_check.setChecked(settings.tts_enabled)
```

In `_apply`, after `settings.auto_save_position = self.auto_save_check.isChecked()`, add:

```python
        settings.tts_enabled = self.tts_check.isChecked()
```

- [ ] **Step 2: Create and wire TTSController in MainWindow**

In `rsvp/ui/main_window.py`:

Add to imports (after the existing `from rsvp.core.stats import ...` line):

```python
from rsvp.core.tts import TTSController, create_tts_driver
```

In `__init__`, after `self._stats_recorder = StatsRecorder(...)`, add:

```python
        self._tts = TTSController(self._engine, driver=create_tts_driver())
        self._tts.set_enabled(get_settings_manager().settings.tts_enabled)
```

In `_apply_settings` (which is called when Settings dialog is accepted), after `self.word_display.update_settings()`, add:

```python
        self._tts.set_enabled(self._settings.settings.tts_enabled)
```

Wait — the current main_window.py on this branch uses `get_settings_manager()` (singleton pattern), not `self._settings` (DI). Update accordingly:

```python
        self._tts.set_enabled(get_settings_manager().settings.tts_enabled)
```

In `closeEvent`, add at the top (before saving window state):

```python
        self._tts.shutdown()
```

- [ ] **Step 3: Verify all existing tests still pass**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -3 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1`
Expected: 270 tests pass (no new tests yet); ruff clean.

- [ ] **Step 4: Commit**

```bash
git add rsvp/ui/settings_dialog.py rsvp/ui/main_window.py
git commit -m "feat: add TTSController and integrate with engine + MainWindow + settings

Settings → Behavior gets a 'Text-to-speech' checkbox. Apply/OK
persists settings.tts_enabled; the next MainWindow._apply_settings
call propagates the new value to the TTSController.

MainWindow is the composition root:
  - Creates TTSController in __init__ (with create_tts_driver()
    factory, gracefully falls back to NullDriver on missing deps)
  - set_enabled() in _apply_settings propagates the saved value
  - closeEvent calls shutdown() to interrupt any in-progress
    utterance cleanly

The TTSController subscribes to engine.word_changed and speaks each
new word synchronously (say + run_and_wait). The main thread blocks
for the duration of each word, which naturally paces the display to
the TTS rate. On engine pause, state_changed fires, the controller
calls tts.stop() to interrupt the current utterance mid-word.

No new bare excepts introduced. The TTSController uses NullDriver
when pyttsx3 is unavailable, so CI runs that lack espeak still
test cleanly."
```

---

## Task 3: Tests

**Files:**
- Create: `tests/test_tts.py`

- [ ] **Step 1: Create `tests/test_tts.py`**

```python
"""Tests for the TTS module."""

from unittest.mock import MagicMock

import pytest

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import RSVPSettings
from rsvp.core.text_processor import Word
from rsvp.core.tts import (
    NullDriver,
    TTSController,
    create_tts_driver,
)


class TestNullDriver:
    """NullDriver methods are no-ops and should never raise."""

    def test_say_is_noop(self):
        NullDriver().say("hello")  # no exception

    def test_run_and_wait_is_noop(self):
        NullDriver().run_and_wait()

    def test_stop_is_noop(self):
        NullDriver().stop()


class TestCreateTTSDriver:
    def test_returns_object_with_required_methods(self):
        driver = create_tts_driver()
        assert hasattr(driver, "say")
        assert hasattr(driver, "run_and_wait")
        assert hasattr(driver, "stop")

    def test_returns_usable_object(self):
        """The returned driver should not raise on basic method calls.

        On systems where pyttsx3.init() succeeds, this is a Pyttsx3Driver.
        On others, it's a NullDriver. Either way, the call should not
        raise and the methods should exist.
        """
        driver = create_tts_driver()
        driver.say("test")  # no exception
        driver.stop()  # no exception


class TestTTSController:
    def test_disabled_by_default(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        assert ctrl.enabled is False

    def test_set_enabled_true(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        ctrl.set_enabled(True)
        assert ctrl.enabled is True

    def test_set_enabled_false_calls_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        mock_driver.reset_mock()
        ctrl.set_enabled(False)
        mock_driver.stop.assert_called()

    def test_word_changed_with_null_driver_does_nothing(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        # Should not raise even when a word is emitted
        engine.word_changed.emit(Word(text="hello", orp_index=0, pause_after=1.0))

    def test_word_changed_speaks_when_enabled(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        mock_driver.reset_mock()
        engine.word_changed.emit(Word(text="hello", orp_index=0, pause_after=1.0))
        mock_driver.say.assert_called_once_with("hello")
        mock_driver.run_and_wait.assert_called_once()

    def test_pause_calls_driver_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        engine.load_text("hello world")
        mock_driver.reset_mock()
        engine.play()
        engine.pause()
        mock_driver.stop.assert_called()

    def test_pause_does_not_call_stop_when_disabled(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        # NOT enabled
        engine.load_text("hello world")
        engine.play()
        engine.pause()
        mock_driver.stop.assert_not_called()

    def test_shutdown_calls_driver_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        mock_driver.reset_mock()
        ctrl.shutdown()
        mock_driver.stop.assert_called()


class TestTTSEnabledInSettings:
    def test_default_is_false(self):
        s = RSVPSettings()
        assert s.tts_enabled is False

    def test_can_be_set_to_true(self):
        s = RSVPSettings(tts_enabled=True)
        assert s.tts_enabled is True
```

- [ ] **Step 2: Run the new tests**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest tests/test_tts.py -v 2>&1 | tail -20`
Expected: 14 tests pass.

- [ ] **Step 3: Run full verification**

Run: `QT_QPA_PLATFORM=offscreen /opt/homebrew/bin/python3.12 -m pytest -q 2>&1 | tail -2 && /opt/homebrew/bin/python3.12 -m ruff check rsvp/ tests/ 2>&1 | tail -1 && /opt/homebrew/bin/python3.12 -m mypy rsvp/ 2>&1 | tail -1`
Expected: ~284 tests pass, ruff clean, mypy clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tts.py
git commit -m "test: add TTS driver, controller, and settings tests

tests/test_tts.py (14 tests):
  - NullDriver methods are no-ops and don't raise
  - create_tts_driver() returns a usable object on any system
  - TTSController disabled by default
  - set_enabled(true/false) toggles + calls stop() when disabling
  - word_changed speaks via the driver when enabled
  - pause calls driver.stop() (interrupts TTS mid-utterance)
  - pause does NOT call stop() when TTS is disabled
  - shutdown calls driver.stop() (cleanup on close)
  - RSVPSettings.tts_enabled defaults to False
  - RSVPSettings.tts_enabled can be set to True

Tests use MagicMock for the driver so we can verify stop() is called
at the right times without requiring a real TTS engine."
```

---

## Self-Review

**1. Spec coverage:** 7 in-scope items mapped to 3 commits (driver + dep → integration → tests).

**2. Placeholder scan:** No "TBD" or "fill in later" markers. All code blocks are concrete.

**3. Type consistency:** `TTSDriver` Protocol used consistently; `TTSController` and `create_tts_driver()` return types match.

**4. Edge cases handled:**
- Missing pyttsx3 → NullDriver fallback (try/except in `create_tts_driver`)
- Pause during speech → `tts.stop()` interrupts
- Close while speaking → `shutdown()` cleanup
- Toggling off while disabled → no-op (stop still called, but no-op on NullDriver)
- Disabled controller + word_changed → silent (early return)

**5. Risk acknowledgment:**
- Main-thread blocking during speech is documented as MVP trade-off
- pyttsx3 platform variance handled by NullDriver fallback
- Tests don't exercise real pyttsx3 (use MagicMock + NullDriver)

---

## Success Criteria (from spec)

- [ ] `pyttsx3` is in `[project] dependencies`
- [ ] `TTSController` is constructed in `MainWindow` and wired to the engine
- [ ] Settings → Behavior has a "Text-to-speech" checkbox
- [ ] Toggling the checkbox enables/disables TTS for the current session
- [ ] Apply/OK persists `tts_enabled` to `settings.json`
- [ ] Engine pause interrupts any in-progress TTS utterance
- [ ] MainWindow closeEvent shuts down TTS cleanly
- [ ] `pytest -q` passes (~284 tests, 14 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] No new bare excepts introduced
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~284 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches
git log --oneline main..HEAD # expect: 3 new commits
```
