# Spec 2: Architecture & Contributor Docs

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 2 of 3 (see "Scope" below)
**Branch:** `feature/architecture-contributor-docs` (off main)
**Target PR:** Single PR with 4 atomic commits

## Context

Spec 1 (code quality & tooling foundation) lands logging, type hints, mypy, and the
"quick wins" from the code review. Spec 2 addresses the remaining P3 architecture
items from the same review plus a contributor guide, and Spec 3+ will add
features (reading statistics, themes, TTS, etc.).

## Scope

**In scope (Spec 2 — this document):**

| # | Item | Source |
|---|------|--------|
| 1 | Replace `get_settings_manager()` singleton with constructor DI | Review #7 |
| 2 | Ensure `QPainter.end()` is called in `ORPWordDisplay.paintEvent` | Review #6 |
| 3 | Add `CONTRIBUTING.md` | Review #8 |
| 4 | Add DI smoke tests verifying injection works | Spec 2 decision |

**Out of scope (later specs):**

- Spec 3+ — Features: reading statistics, theme presets, text-to-speech,
  settings export/import, chunk mode
- Adding `mypy` to CI (one-line `.github/workflows/build.yml` change —
  intentionally deferred to a separate "tooling in CI" spec)
- Replacing the `QFont` / `QPainter` parameter-name shims with cast helpers
  (cosmetic; deferred)

## Design Decisions (from brainstorming)

1. **Settings DI shape:** True DI — every class that needs settings
   accepts a `SettingsManager` via `__init__`. `get_settings_manager()` is
   removed entirely (zero callers remain). MainWindow is the single
   composition root: it constructs the `SettingsManager` in `__init__` and
   passes it to all children. main.py does not need to know about
   `SettingsManager`.
2. **QPainter safety:** `try/finally` around the paint body. No new
   context-manager pattern, no `begin()`/`end()` reordering — minimal
   diff, idiomatic Python.
3. **CONTRIBUTING.md:** Single-file guide covering dev setup, test/lint/
   mypy commands, code style conventions, commit format, and PR
   process. Cross-references `README.md` and `CHANGELOG.md` (both new
   in Spec 1).
4. **DI smoke tests:** Three new tests in `tests/test_settings.py`
   verifying the injection seam works for the three primary entry
   points (RSVPEngine, MainWindow, WordDisplayWidget).

## Architecture

The DI refactor reshapes the lifetime of `SettingsManager`:

**Before (singleton):**
```
main.py → MainWindow → [RSVPEngine, BookmarkController, DocumentLoader, ...]
                            │
                            └─ each calls get_settings_manager() which
                               returns a module-level global
```

**After (constructor DI):**
```
main.py → MainWindow(settings: SettingsManager)
                │
                ├─ RSVPEngine(settings)
                ├─ WordDisplayWidget(settings)
                ├─ BookmarkController(settings, ...)
                ├─ DocumentLoader(settings, ...)
                └─ SettingsDialog(settings)
```

Each class stores the injected `SettingsManager` as `self._settings`
and uses it directly. No global. No `get_settings_manager()`.

**File-level changes:**

| File | Change |
|------|--------|
| `rsvp/main.py` | No change (MainWindow is still the entry point) |
| `rsvp/core/settings.py` | Remove `get_settings_manager()` and the module-level `_settings_manager` global |
| `rsvp/core/__init__.py` | Remove `get_settings_manager` from imports and `__all__` |
| `rsvp/core/rsvp_engine.py` | Accept `SettingsManager` in `__init__`; use `self._settings` in `_update_timer_interval` |
| `rsvp/ui/word_display.py` | `ORPWordDisplay` and `WordDisplayWidget` accept `SettingsManager`; pass to children |
| `rsvp/ui/bookmark_controller.py` | Accept `SettingsManager`; use `self._settings` |
| `rsvp/ui/document_loader.py` | Accept `SettingsManager`; use `self._settings` |
| `rsvp/ui/settings_dialog.py` | Accept `SettingsManager`; use `self._settings` |
| `rsvp/ui/main_window.py` | Construct `SettingsManager` in `__init__`; pass to all children |
| `rsvp/ui/word_display.py` (paintEvent) | Wrap paint body in `try/finally: painter.end()` |
| `CONTRIBUTING.md` | New file |
| `tests/test_settings.py` | Add 3 DI smoke tests |

## Per-Item Design

### Item 1 — Settings DI Refactor

**Pattern (applied uniformly):**

```python
# Before
class Foo:
    def __init__(self, parent=None):
        super().__init__(parent)
        # ...

    def bar(self):
        get_settings_manager().do_thing()

# After
class Foo:
    def __init__(self, parent=None, settings: SettingsManager) -> None:
        super().__init__(parent)
        self._settings = settings
        # ...

    def bar(self) -> None:
        self._settings.do_thing()
```

**Class-by-class signature changes:**

| Class | New `__init__` signature |
|-------|--------------------------|
| `RSVPEngine` | `__init__(self, parent=None, settings: SettingsManager) -> None` |
| `BookmarkController` | `__init__(self, parent_widget, engine, submenu, status_setter, current_file_getter, settings: SettingsManager) -> None` |
| `DocumentLoader` | `__init__(self, parent_widget, engine, status_setter, title_setter, on_loaded, current_file_getter, settings: SettingsManager) -> None` |
| `SettingsDialog` | `__init__(self, parent=None, settings: SettingsManager) -> None` |
| `ORPWordDisplay` | `__init__(self, parent=None, settings: SettingsManager) -> None` |
| `WordDisplayWidget` | `__init__(self, parent=None, settings: SettingsManager) -> None` |
| `MainWindow` | `__init__(self, settings: SettingsManager) -> None` |

**Composition root (MainWindow):**

```python
class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager) -> None:
        super().__init__()
        self._settings = settings
        self._current_file: str | None = None
        self._engine = RSVPEngine(settings=settings)
        self._setup_ui()  # creates WordDisplayWidget(settings=settings)
        # ... etc
```

**`main.py` is unchanged** — `MainWindow()` is still constructed the same
way (it now creates the SettingsManager internally, so the caller doesn't
have to). For tests, `MainWindow(settings=fake_manager)` is the seam.

**Removal of `get_settings_manager()`:**

- Delete the function in `core/settings.py`
- Delete `_settings_manager` module-level global
- Remove `get_settings_manager` from `core/__init__.py` import and `__all__`
- No replacement / no deprecation shim — this is a personal project with a
  single consumer, and the new pattern is strictly better

**Test impact:**

Most tests don't construct widgets directly (they use `tmp_path` for
`SettingsManager` and `QApplication` for widgets). The new test cases
in commit 4 verify the injection works. The existing test suite should
continue to pass without changes (no test currently calls
`get_settings_manager()` outside of `test_settings.py`, which tests
`SettingsManager` directly).

**Loggers:** The DI refactor is purely structural. No logging changes
needed — the existing `logger` instances in each module remain.

### Item 2 — QPainter.end() safety

**Current code (`rsvp/ui/word_display.py:50`):**

```python
def paintEvent(self, event) -> None:
    """Paint the word with ORP highlighting."""
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fill background
    painter.fillRect(self.rect(), self._bg_color)

    if not self._word:
        painter.end()
        return

    # ... 30+ lines of drawing code ...
    painter.end()
```

**Problem:** If an exception is raised between `painter = QPainter(self)`
and the final `painter.end()` (e.g., font metrics throw on a degenerate
glyph, or `setPen` is called with an invalid color), the painter is not
closed. Qt's `QPainter.__exit__` (via Python's `__del__`) will call
`end()` when the wrapper is garbage-collected, but the order of
destruction under an exception is non-deterministic. In practice this
manifests as "QPainter: Paint device returned engine that is being
deleted" warnings on shutdown.

**Fix (try/finally):**

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
        # ... rest of drawing code unchanged ...
    finally:
        painter.end()
```

The early-return `if not self._word: return` no longer needs its own
`painter.end()` because the `finally` clause always runs.

**Why not a context manager?** Qt's `QPainter` doesn't natively support
`with` (no `__enter__`/`__exit__`). Adding one would require either a
subclass or a helper, both of which add complexity for no real benefit
over `try/finally`. The spec stays with `try/finally`.

### Item 3 — CONTRIBUTING.md

**File content (one-shot, written verbatim):**

````markdown
# Contributing to RSVP Reader

Thanks for your interest in RSVP Reader! This guide covers everything
you need to make, test, and submit changes.

## Quick Start

```bash
# Clone and install (editable, with dev extras)
git clone https://github.com/cortexuvula/RSVP.git
cd RSVP
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running the App

```bash
rsvp
# or, equivalently:
python -m rsvp.main
```

## Development Workflow

### Tests

```bash
# Full suite (headless, requires Python 3.10+)
QT_QPA_PLATFORM=offscreen pytest -q

# Single file or test
QT_QPA_PLATFORM=offscreen pytest tests/test_rsvp_engine.py -v
```

Coverage is configured via `pytest-cov` and reported in CI.

### Lint

```bash
ruff check rsvp/ tests/
ruff format --check rsvp/ tests/
```

`ruff` is the only linter. It runs in CI on every push and PR.

### Type Check

```bash
mypy rsvp/
```

`mypy` runs against the `rsvp/` package. Configuration is in
`pyproject.toml` under `[tool.mypy]`. PyQt6 stubs are incomplete, so
`disable_error_code = ["union-attr"]` is set; `# type: ignore[arg-type]`
comments are used at the two remaining PyQt6 stub gaps (in
`rsvp/ui/menu_builder.py`) with one-line justifications.

### Debug Logging

```bash
RSVP_LOG_LEVEL=DEBUG rsvp
```

Levels: `DEBUG` (verbose, engine state, clipboard fallback), `INFO`
(document loads, settings changes), `WARNING` (default, recoverable
errors only). Output goes to stderr.

## Code Style

- **Type hints:** every public and private function, method, property,
  and signal handler has parameter and return type annotations. New
  code follows the same convention. Mypy runs in `--check-untyped-defs`
  mode; untyped code is allowed during gradual rollout but new code
  should be fully annotated.
- **Dataclasses** for value objects (see `rsvp/core/text_processor.py`
  `Word`, `rsvp/core/rsvp_engine.py` `RSVPState`, `rsvp/core/settings.py`
  `RSVPSettings`).
- **Logging:** every module has `logger = logging.getLogger(__name__)`
  at the top. Use `logger.debug` for state, `logger.info` for
  user-visible events (document load, bookmark change, settings apply),
  `logger.warning` / `logger.exception` for recoverable errors.
- **Exception handling:** catch the specific exception types the
  underlying library actually raises. Never use bare `except Exception`
  in UI code. The QMessageBox user-facing dialog is preserved for
  expected errors; unexpected exceptions propagate so bugs surface.
- **Constants:** all module-level constants live in
  `rsvp/core/constants.py`. No magic numbers in code.

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

- `feat:` — new user-facing feature
- `fix:` — bug fix
- `refactor:` — internal change with no behavior change
- `test:` — new or changed tests
- `docs:` — documentation only
- `chore:` — build, CI, dependency changes
- `ci:` — CI configuration

Subject line ≤72 chars, imperative mood ("add", not "added"). Body
explains the *why*; the diff shows the *what*.

## Pull Request Process

1. Create a feature branch off `main`: `git checkout -b feature/<thing>`
2. Make your changes in atomic commits (one logical change per commit)
3. Ensure all four checks pass locally: `pytest`, `ruff check`,
   `mypy rsvp/`, and `rg "except Exception" rsvp/` returns no matches
4. Push and open a PR against `main`
5. Fill in the PR template (or write a 2-3 line summary if no template
   exists yet)
6. Wait for CI to pass; address review feedback with fixup commits or
   `git commit --fixup` if the maintainer prefers a clean history
7. Squash-merge once approved (or rebase-merge if you prefer a linear
   history without squash)

## Project Layout

```
rsvp/
  core/          pure logic, no Qt widgets (except signals)
    constants.py all module-level constants
    rsvp_engine.py RSVP playback engine (QObject + signals)
    settings.py  SettingsManager, RSVPSettings dataclass
    text_processor.py ORP, pause, dispatch, URL/file loading
  ui/            Qt widgets and dialogs
    main_window.py    composition root for the window
    bookmark_controller.py
    document_loader.py
    controls.py       PlaybackControls, SpeedControl, ProgressWidget
    settings_dialog.py
    text_input_dialog.py
    menu_builder.py
    word_display.py   ORPWordDisplay, WordDisplayWidget
  main.py        entry point
tests/
  fixtures/      test.md, test.html, test.epub, test.pdf
  conftest.py    shared fixtures (qapp)
  test_<module>.py
```

## See Also

- `README.md` — user-facing documentation
- `CHANGELOG.md` — release history
- `docs/superpowers/specs/` — design specs for completed work
- `docs/superpowers/plans/` — implementation plans
````

### Item 4 — DI Smoke Tests

**New tests in `tests/test_settings.py`:**

```python
class TestSettingsInjection:
    """Verify SettingsManager can be injected without using the singleton."""

    def test_engine_accepts_injected_settings(self, tmp_path, qapp):
        from rsvp.core.rsvp_engine import RSVPEngine
        from rsvp.core.settings import SettingsManager

        manager = SettingsManager.__new__(SettingsManager)
        # bypass __init__ which reads from the user's real config dir;
        # manually wire up an isolated config file
        manager._settings = __import__("rsvp.core.settings", fromlist=["RSVPSettings"]).RSVPSettings()
        manager._config_path = tmp_path / "settings.json"
        manager._settings_were_reset = False
        manager._save_failed = False

        engine = RSVPEngine(settings=manager)
        # The injected manager is the one used; mutate it and verify
        # the engine sees the change.
        engine._settings.settings.pause_at_paragraphs = False
        assert manager.settings.pause_at_paragraphs is False

    def test_word_display_accepts_injected_settings(self, tmp_path, qapp):
        from rsvp.ui.word_display import WordDisplayWidget
        from rsvp.core.settings import SettingsManager, RSVPSettings

        manager = SettingsManager.__new__(SettingsManager)
        manager._settings = RSVPSettings(font_family="Courier", font_size=24)
        manager._config_path = tmp_path / "settings.json"
        manager._settings_were_reset = False
        manager._save_failed = False

        widget = WordDisplayWidget(settings=manager)
        # The widget used the injected settings
        assert widget.word_display._font.family() == "Courier"
        assert widget.word_display._font.pointSize() == 24

    def test_get_settings_manager_removed(self):
        """The singleton accessor must be gone after the DI refactor."""
        import rsvp.core.settings as settings_mod
        assert not hasattr(settings_mod, "get_settings_manager")
```

**Why the manual `__new__` + attribute setup?** `SettingsManager.__init__`
calls `self.load()` which reads from the platform's user config directory
(Windows: `%APPDATA%/RSVP`, macOS: `~/Library/Application Support/RSVP`,
Linux: `$XDG_CONFIG_HOME/rsvp`). For tests, we want a fully isolated
manager that doesn't touch the user's real config. Bypassing `__init__`
and manually setting the three attributes the manager needs (`_settings`,
`_config_path`, and the two flag attributes) gives us a clean test
fixture.

The three tests verify:
1. RSVPEngine can be constructed with an injected SettingsManager
2. WordDisplayWidget can be constructed with an injected SettingsManager
3. The `get_settings_manager()` function is gone (proves the refactor is complete)

## Commit Plan (Atomic, in this order)

```
docs: add CONTRIBUTING.md
fix: ensure QPainter.end() is called in ORPWordDisplay.paintEvent
refactor: replace get_settings_manager() singleton with constructor DI
test: add DI smoke tests for SettingsManager injection
```

**Rationale for ordering:**

1. `CONTRIBUTING.md` is purely additive, no risk, no dependencies.
2. `QPainter` fix is one file, isolated, doesn't touch the settings code.
3. The DI refactor is the structural change — biggest diff, most risk.
   Comes after the smaller items so any regression is easy to bisect.
4. DI smoke tests verify the refactor; they go last so they
   exercise the just-merged code.

## Testing Strategy

- **Each commit's `pytest` and `ruff check` must pass.**
- The DI refactor commit (3) should be reviewed for: every `get_settings_manager()`
  caller is replaced with `self._settings.foo`, the function is removed from
  `core/__init__.py` and `core/settings.py`, all `__init__` signatures have
  the new `settings` parameter, MainWindow's `__init__` constructs the
  SettingsManager and threads it through to all children.
- The DI smoke test commit (4) verifies the injection works for the
  three primary entry points and that `get_settings_manager` is gone.

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| DI refactor breaks MainWindow construction (e.g., a child is created without `settings`) | Existing test suite (`tests/test_ui_main_window.py`) constructs `MainWindow` and exercises the lifecycle. If anything's missing, it fails immediately. |
| `__new__` bypass in DI smoke tests is fragile if `SettingsManager` adds new init attributes | The tests use the same setup; if `SettingsManager.__init__` adds an attribute, the test setup will need updating. Acceptable — that's the price of a test fixture. |
| `QPainter.end()` in `finally` could mask the original exception | Qt's `QPainter.end()` returns `bool`; if `end()` itself raises (rare), the original exception is replaced. Acceptable — the alternative is a leak warning on every paint exception. |
| Removing `get_settings_manager()` breaks a downstream user | This is a personal project; no downstream users. The `pyproject.toml` version will bump to 1.4.0 (signaling breaking change) in this spec's release. |

## Out of Scope (Explicitly)

- Adding `mypy` to CI (`.github/workflows/build.yml` one-line change) —
  deferred to a small follow-up spec
- Replacing the `QFont` / `QPainter` parameter-name shims — cosmetic,
  deferred
- Refactoring `WordDisplayWidget` to be a plain QWidget vs. a
  QWidget-with-`word_display` child (current dual-class structure works,
  not worth churning)
- Threading SettingsManager through `pyqtSignal.connect` lambdas (they
  capture `self`, which has `self._settings` — no change needed)

## Success Criteria

- [ ] `get_settings_manager` no longer exists anywhere in `rsvp/`
- [ ] Every class that previously called `get_settings_manager()` accepts
      a `SettingsManager` via `__init__` and stores it as `self._settings`
- [ ] MainWindow constructs the SettingsManager in `__init__` (the only
      composition root)
- [ ] `ORPWordDisplay.paintEvent` wraps the paint body in
      `try/finally: painter.end()`
- [ ] `CONTRIBUTING.md` exists at the repo root and is cross-linked
      from `README.md` (one-line addition)
- [ ] `pytest -q` passes (273 tests + 3 new = 276)
- [ ] `ruff check rsvp/ tests/` passes
- [ ] `mypy rsvp/` passes
- [ ] `rg "except Exception" rsvp/` returns no matches
- [ ] All 4 items above landed in the named atomic commits
