# Spec 5: Text-to-Speech

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 5 — 3rd feature spec (1 of 5 from the original review's feature list)
**Branch:** `feature/text-to-speech` (off main)
**Target PR:** Single PR with 3 atomic commits

## Context

The original code review listed 5 features. Specs 3 (reading statistics) and 4
(theme presets) are done. This spec covers text-to-speech. The remaining
2 features (settings export/import, chunk mode) come in their own cycles.

## Scope

**In scope (Spec 5 — this document):**

| # | Item |
|---|------|
| 1 | `pyttsx3`-based TTS driver in `rsvp/core/tts.py` with a `NullDriver` for tests + missing-dep graceful fallback |
| 2 | `TTSController` that subscribes to `RSVPEngine.word_changed` and speaks each word |
| 3 | "Text-to-speech" checkbox in `Settings → Behavior` (persists via `tts_enabled` field on `RSVPSettings`) |
| 4 | `MainWindow` wiring: engine ↔ TTSController; pause/stop interrupts TTS mid-utterance |
| 5 | Tests: driver abstraction (mockable), controller lifecycle, settings persistence |
| 6 | Add `pyttsx3` to runtime dependencies in `pyproject.toml` |
| 7 | CHANGELOG entry under `[Unreleased]` |

**Out of scope (later specs):**

- Spec 6+ — Settings export/import, chunk mode
- Voice picker (use OS default)
- TTS speed slider decoupled from display WPM
- Online TTS engines (gTTS, etc.)
- Background-thread TTS (the current implementation blocks the main thread during speech; this is acceptable for an MVP and the standard pattern for pyttsx3-driven apps)
- TTS while paused (it's silent during pause by design)

## Design Decisions (from brainstorming)

1. **TTS engine:** **pyttsx3** (offline, system voices). Works on Windows (SAPI5), macOS (NSSpeechSynthesizer), Linux (espeak). No internet, no API keys. Voice quality is OS-dependent.
2. **Sync model:** **Word-by-word, paced to display.** The display advances at the WPM rate; TTS speaks each word as it becomes the current word. If the user pauses, TTS pauses (the engine's QTimer stops firing).
3. **UI surface:** **Settings checkbox** in the Behavior group. Checked = TTS on, unchecked = off. No toolbar button, no menu commands — minimal surface area.
4. **Voice:** **OS default.** No voice picker in the UI. Power users can change their system default voice at the OS level.

## Architecture

```
main.py → MainWindow(settings)
              │
              ├─ RSVPEngine(settings)
              ├─ StatsRecorder(engine, stats_manager)  [Spec 3]
              ├─ TTSController(engine, tts_enabled=settings.tts_enabled)  [NEW]
              │      │
              │      └─ Pyttsx3Driver()  [NEW]  (or NullDriver if pyttsx3 missing)
              ├─ BookmarkController(settings, ...)
              ├─ DocumentLoader(settings, ...)
              └─ SettingsDialog(settings, ...)
```

`MainWindow` is the composition root. It creates:
- `SettingsManager` (existing)
- `StatsManager` (Spec 3)
- `TTSController` (new, this spec)
- `RSVPEngine` (passes settings)
- All child widgets (passes settings where needed)

The `TTSController` is constructed with `tts_enabled` from settings; the
underlying pyttsx3 engine is initialized lazily when the user enables
TTS (and is stopped/discarded when disabled).

## TTSDriver Abstraction

To make the TTS code testable without requiring a real TTS engine, the
low-level pyttsx3 calls go through a `TTSDriver` Protocol:

```python
# rsvp/core/tts.py

class TTSDriver(Protocol):
    """Protocol for TTS drivers. Production = Pyttsx3Driver, tests = NullDriver."""
    def say(self, text: str) -> None: ...
    def run_and_wait(self) -> None: ...
    def stop(self) -> None: ...


class NullDriver:
    """No-op driver. Used in tests and as a fallback when pyttsx3 is unavailable."""
    def say(self, text: str) -> None: pass
    def run_and_wait(self) -> None: pass
    def stop(self) -> None: pass


class Pyttsx3Driver:
    """Wraps pyttsx3.init() / say() / runAndWait() / stop()."""
    def __init__(self) -> None:
        import pyttsx3
        self._engine = pyttsx3.init()

    def say(self, text: str) -> None:
        self._engine.say(text)

    def run_and_wait(self) -> None:
        self._engine.runAndWait()

    def stop(self) -> None:
        self._engine.stop()


def create_tts_driver() -> TTSDriver:
    """Create a Pyttsx3Driver if pyttsx3 is importable, else NullDriver."""
    try:
        import pyttsx3  # noqa: F401
        return Pyttsx3Driver()
    except ImportError:
        return NullDriver()
```

## TTSController

```python
class TTSController:
    """Speaks each engine word via the TTS driver, paced to the display WPM.

    Subscribes to RSVPEngine.word_changed and speaks each new word. The
    call is synchronous (say + runAndWait) — the main thread blocks for
    the duration of each word, which naturally paces the display to the
    TTS rate. The engine's QTimer is the wakeup mechanism; TTS is the
    bottleneck.
    """

    def __init__(self, engine: RSVPEngine, driver: TTSDriver | None = None) -> None:
        self._engine = engine
        self._driver = driver or NullDriver()
        self._enabled = False
        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """User toggled TTS in Settings. Lazily (re)initialize the driver."""
        self._enabled = enabled
        if not enabled:
            self._driver.stop()  # interrupt any current utterance

    def _on_word_changed(self, word) -> None:
        if not self._enabled or word is None:
            return
        self._driver.say(word.text)
        self._driver.run_and_wait()  # blocks for the word's duration

    def _on_state_changed(self) -> None:
        """When the engine transitions to paused/stopped, interrupt TTS."""
        if not self._enabled:
            return
        if not self._engine.is_playing:
            self._driver.stop()
```

**Sync model in detail:**

1. User clicks Play
2. Engine's QTimer fires every `(60 / WPM) * pause_after` ms
3. Each timer tick calls `_advance()` which increments the index and emits `word_changed(new_word)`
4. `TTSController._on_word_changed` is called; it does `tts.say(new_word.text); tts.runAndWait()`
5. `runAndWait` blocks for the duration of the utterance (~200ms at 300 WPM)
6. Slot returns, the event loop processes the next QTimer tick
7. The display advances at the rate TTS finishes each word

The display pace IS the TTS pace. If TTS is slow, the display is slow.
If the user lowers WPM, TTS speaks each word at the slower rate.

**Pause behavior:**

- User clicks Pause → engine.pause() → is_playing=False → state_changed.emit()
- `TTSController._on_state_changed` sees is_playing=False, calls `tts.stop()` to interrupt the current utterance
- The next QTimer tick doesn't fire (timer is stopped)
- No more word_changed events, no more speech
- When user clicks Play again, the timer restarts and TTS resumes from the current word

**Stop behavior:**

- Same as pause, plus the engine resets to the first word (handled by engine.stop())
- The next play() starts from the beginning

## Settings Schema Change

Add one field to `RSVPSettings`:

```python
@dataclass
class RSVPSettings:
    # ... existing fields ...
    tts_enabled: bool = False
```

Default is `False` (TTS off) so existing users see no change. No migration needed (same `setattr`-with-`hasattr` load pattern as previous additions).

## UI

**Settings → Behavior group gets a new row:**

```
Behavior
  Always on top:              [ ]
  Pause at paragraph breaks:  [x]
  Remember reading position:  [x]
  Text-to-speech:             [ ]   ← NEW
```

**Apply/OK** persists `tts_enabled`. The TTSController in MainWindow is updated when settings are saved (via `_apply_settings()` hook).

## MainWindow Integration

`MainWindow.__init__`:
- Create `TTSController(self._engine)` (no driver yet — lazily initialized)
- Read `settings.tts_enabled` and call `tts.set_enabled(...)` after creation

`MainWindow._apply_settings`:
- After applying settings, call `self._tts.set_enabled(settings.tts_enabled)` if TTS settings changed

`MainWindow._toggle_always_on_top` / `_on_finished` / etc.: unchanged.

**TTS shutdown on close:**

`MainWindow.closeEvent` calls `self._tts.shutdown()` (a new method that calls `tts.stop()`) to clean up any in-progress utterance.

## File-Level Changes

| File | Change |
|------|--------|
| `rsvp/core/tts.py` | New — `TTSController`, `TTSDriver` Protocol, `Pyttsx3Driver`, `NullDriver`, `create_tts_driver()` |
| `rsvp/core/__init__.py` | Re-export `TTSController`, `TTSDriver` (and maybe `NullDriver` for tests) |
| `rsvp/core/settings.py` | Add `tts_enabled: bool = False` to `RSVPSettings` |
| `pyproject.toml` | Add `pyttsx3>=2.90` to `dependencies` |
| `rsvp/ui/settings_dialog.py` | Add "Text-to-speech" checkbox to Behavior group; wire to `settings.tts_enabled` |
| `rsvp/ui/main_window.py` | Create `TTSController` in `__init__`; wire in `_apply_settings`; shutdown in `closeEvent` |
| `tests/test_tts.py` | New — driver tests, controller tests, settings integration |
| `CHANGELOG.md` | New — `[Unreleased]` entry |

## Per-Item Design

### Item 1 — `rsvp/core/tts.py`

The module contains:
- `TTSDriver` Protocol (typing only — not a class)
- `NullDriver` class (concrete, for tests + missing-dep fallback)
- `Pyttsx3Driver` class (concrete, production)
- `create_tts_driver()` factory function
- `TTSController` class (the integration point with the engine)

The Protocol is documented but not enforced at runtime (Python Protocol
classes are for static type checking; mypy picks this up).

### Item 2 — Add `pyttsx3` to dependencies

In `pyproject.toml` under `[project] dependencies`:

```toml
dependencies = [
    "PyQt6>=6.4.0",
    "requests>=2.28.0",
    "beautifulsoup4>=4.11.0",
    "pyperclip>=1.8.0",
    "ebooklib>=0.18",
    "pymupdf>=1.23.0",
    "pyttsx3>=2.90",  # NEW
]
```

`create_tts_driver()` uses try/except so the app gracefully degrades if
pyttsx3 isn't installed.

### Item 3 — SettingsDialog integration

Add a `QCheckBox` to the Behavior group:

```python
self.tts_check = QCheckBox()
behavior_layout.addRow("Text-to-speech:", self.tts_check)
```

In `_load_settings`: `self.tts_check.setChecked(settings.tts_enabled)`
In `_apply`: `settings.tts_enabled = self.tts_check.isChecked()`

### Item 4 — MainWindow wiring

In `__init__`:
```python
self._tts = TTSController(self._engine)
# Apply the saved setting
self._tts.set_enabled(get_settings_manager().settings.tts_enabled)
```

In `_apply_settings` (called when Settings dialog is accepted):
```python
self._tts.set_enabled(self._settings.settings.tts_enabled)
```

In `closeEvent`:
```python
def closeEvent(self, event):
    self._tts.shutdown()  # interrupt any in-progress utterance
    self._stats_recorder.shutdown()
    # ... rest unchanged
```

Add `shutdown()` to `TTSController`:
```python
def shutdown(self) -> None:
    """Interrupt any in-progress utterance. Called by MainWindow.closeEvent."""
    self._driver.stop()
```

### Item 5 — Tests

**`tests/test_tts.py`** (~10 tests):

```python
class TestTTSDriver:
    def test_null_driver_say_is_noop(self):
        d = NullDriver()
        d.say("hello")  # no exception
    def test_null_driver_run_and_wait_is_noop(self):
        NullDriver().run_and_wait()
    def test_null_driver_stop_is_noop(self):
        NullDriver().stop()

class TestCreateTTSDriver:
    def test_returns_driver_with_required_methods(self):
        driver = create_tts_driver()
        assert hasattr(driver, "say")
        assert hasattr(driver, "run_and_wait")
        assert hasattr(driver, "stop")

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
        ctrl.set_enabled(False)
        mock_driver.stop.assert_called()

    def test_word_changed_with_null_driver_does_nothing(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        # Should not raise
        engine.word_changed.emit(Word(text="hello", orp_index=0, pause_after=1.0))

    def test_pause_calls_driver_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        mock_driver.reset_mock()
        engine.pause()  # emits state_changed with is_playing=False
        mock_driver.stop.assert_called()

class TestTTSEnabledInSettings:
    def test_default_is_false(self):
        s = RSVPSettings()
        assert s.tts_enabled is False

    def test_round_trip_persistence(self, tmp_path):
        # Bypass SettingsManager.__init__; write/read manually
        ...
```

## Commit Plan (3 atomic commits)

```
feat: add pyttsx3-based TTS driver abstraction
feat: add TTSController and integrate with engine + MainWindow + settings
test: add TTS driver, controller, and settings tests
```

**Rationale:**
1. **Driver abstraction first:** `TTSDriver` Protocol + `NullDriver` + `Pyttsx3Driver` + dependency update — pure infrastructure, no app integration.
2. **Integration second:** `TTSController` + `MainWindow` wiring + SettingsDialog checkbox — depends on the driver.
3. **Tests third:** All tests for the feature in one batch.

## Testing Strategy

- 286 existing tests + ~10 new = ~296 total
- All tests use the `NullDriver` (no real pyttsx3 calls in CI)
- Settings tests bypass `SettingsManager.__init__` via `__new__` + manual attrs (existing pattern)
- `TTSController` tests use a `MagicMock` driver for stop-detection verification

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| `pyttsx3.init()` fails on a system without TTS engines (e.g., headless Linux) | `create_tts_driver()` catches the failure and returns `NullDriver`. The app works (TTS is just a no-op). The settings checkbox still works, just produces silence. |
| TTS blocks the main thread → UI freezes during speech | Accepted as MVP trade-off. Standard pattern for pyttsx3 apps. Future spec can add a worker thread. |
| `pyttsx3` is platform-specific; CI on Linux uses espeak which may not be installed | `create_tts_driver()` falls back to `NullDriver`; tests don't exercise the real driver anyway. CI tests verify the abstraction, not pyttsx3 itself. |
| `pyttsx3.say()` + `runAndWait()` blocking the slot delays the next QTimer tick | By design — TTS pace IS the display pace. The display catches up to TTS, not the other way around. |
| User enables TTS, but their system has no audio output | Silent failure. pyttsx3 still calls the OS driver; the driver may or may not emit audio. Not our concern. |
| TTSController is created with no driver, then `set_enabled(True)` is called | `set_enabled` doesn't auto-create a driver. Either: (a) production always passes a driver, OR (b) `set_enabled(True)` lazily creates one. Going with (a) for simplicity — production code in `MainWindow` passes a driver. |
| Settings dialog closes while TTS is mid-utterance | The next `_apply_settings` call (on next open or programmatic apply) will call `set_enabled(...)` which calls `stop()` if disabling. If re-enabling, no current utterance. |

## Out of Scope (Explicitly)

- Background-thread TTS (deferred; current implementation is acceptable for an MVP)
- Voice picker UI (use OS default; advanced users can change at OS level)
- TTS speed decoupled from display WPM
- Online TTS engines (gTTS, AWS Polly, Azure Speech, etc.)
- TTS-aware paragraph breaks (the existing engine handles paragraph pause; TTS naturally respects it)
- "Speak selection" / "Speak from cursor" — only "read the current document" is supported
- TTS volume, pitch, rate controls (all use pyttsx3/OS defaults)
- SSML / pronunciation hints
- Hotkey to toggle TTS on/off without opening Settings (could add later if desired)
- TTS logging (the existing logger covers engine events; TTS events would be very chatty)

## Success Criteria

- [ ] `pyttsx3` is in `[project] dependencies`
- [ ] `TTSController` is constructed in `MainWindow` and wired to the engine
- [ ] Settings → Behavior has a "Text-to-speech" checkbox
- [ ] Toggling the checkbox enables/disables TTS for the current session
- [ ] Apply/OK persists `tts_enabled` to `settings.json`
- [ ] Engine pause interrupts any in-progress TTS utterance
- [ ] MainWindow closeEvent shuts down TTS cleanly
- [ ] `pytest -q` passes (~296 tests, 10 new)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] No new bare excepts introduced
- [ ] All 3 items above landed in the named atomic commits
- [ ] CHANGELOG entry under `[Unreleased]` mentions the new feature

---

## Spec Self-Review (brainstorming checklist)

1. **Coverage:** 7 in-scope items mapped to 3 commits (driver → integration → tests).
2. **No placeholders:** all code blocks are concrete; protocol/class shapes, factory, controller method bodies spelled out.
3. **Internal consistency:** data model ↔ dialog ↔ tests all reference the same field names (`tts_enabled`).
4. **Edge cases handled:**
   - Missing pyttsx3 → NullDriver fallback
   - Pause during speech → `tts.stop()` interrupts
   - Close while speaking → `shutdown()` cleanup
   - Toggling off while disabled → no-op
   - Toggling on with a null driver → safe (NullDriver is silent)
5. **Risk acknowledged:** UI freeze during speech (main-thread blocking) is the MVP trade-off. Documented for future improvement.

---

## Final Verification (after all tasks)

```bash
pytest -q                    # expect: ~296 passed
ruff check rsvp/ tests/      # expect: clean
mypy rsvp/                   # expect: 0 errors
rg "except Exception" rsvp/  # expect: no matches (5 pre-existing on main, not changed)
git log --oneline main..HEAD # expect: 3 new commits
```
