# Spec: Code Quality & Tooling Foundation

**Date:** 2026-06-05
**Status:** Draft (awaiting user review)
**Scope:** Spec 1 of 3 (see "Scope" below)
**Target PR:** Single PR with atomic commits

## Context

An external code review of `cortexuvula/RSVP` v1.3.5 produced 11 prioritized
recommendations and 5 feature suggestions. This spec covers the foundation
work (7 items) that improves the codebase before new features are added.
Specs 2 and 3 will follow in separate design cycles.

## Scope

**In scope (Spec 1 — this document):**

| # | Item | Priority | Source |
|---|------|----------|--------|
| 1 | Fix bare `except Exception` in UI layer | P1 | Review #1, #2 |
| 2 | Add type hints to all functions, methods, and lambdas | P1 | Review #2 |
| 3 | Add mypy configuration + `py.typed` marker | P2 | Review #3 |
| 4 | Add `CHANGELOG.md` (Keep a Changelog format) | P2 | Review #4 |
| 5 | Add `.md` and `.html` test fixtures + dispatch tests | P2 | Review #7 |
| 6 | Add logging throughout core and UI modules | P2 | Review #10 |
| 7 | Delete redundant `requirements.txt` | P3 | Review #9 |

**Out of scope (later specs):**

- Spec 2 — Architecture & Contributor Docs: settings singleton refactor,
  `QPainter` context-manager fix, `CONTRIBUTING.md`
- Spec 3+ — Features: reading statistics, theme presets, text-to-speech,
  settings export/import, chunk mode

## Design Decisions (from brainstorming)

1. **Type-hint scope:** All functions including private helpers, signal
   handlers, lambdas with signatures, and Qt overrides. Goal: 100%
   annotation on what's reasonable (Qt's `paintEvent`, etc., are
   type-checkable). mypy's `ignore_missing_imports` covers PyQt6 stub
   gaps. `disallow_untyped_defs = false` so the spec lands cleanly even
   if a single signature proves irreducible.
2. **Granularity:** Single PR, ~7 atomic commits ordered so each commit
   builds on the previous.
3. **Test fixtures:** Unit tests in `tests/test_text_processor.py` covering
   `load_text_from_file` dispatch to `.md` and `.html` handlers. No new
   integration test through `DocumentLoader` (per user decision).
4. **CHANGELOG:** Backfill historical entries (1.0.0 → 1.3.5) using
   `git log --oneline` and existing GitHub release notes. Follow Keep a
   Changelog 1.1.0 format.

## Architecture

No architectural changes. The spec tightens the existing code without
introducing new modules, classes, or interfaces.

**File-level changes:**

| File | Change |
|------|--------|
| `requirements.txt` | Delete |
| `CHANGELOG.md` | New (backfilled) |
| `rsvp/py.typed` | New (empty marker) |
| `pyproject.toml` | Add `[tool.mypy]` section |
| `rsvp/main.py` | Add logger, ensure configured before first use |
| `rsvp/core/__init__.py` | Add logger |
| `rsvp/core/constants.py` | Type hints |
| `rsvp/core/rsvp_engine.py` | Add logger, type hints |
| `rsvp/core/settings.py` | Already has logger — add type hints |
| `rsvp/core/text_processor.py` | Add logger, type hints |
| `rsvp/ui/__init__.py` | Add logger |
| `rsvp/ui/bookmark_controller.py` | Add logger, type hints |
| `rsvp/ui/controls.py` | Add logger, type hints |
| `rsvp/ui/document_loader.py` | Add logger, fix bare excepts, type hints |
| `rsvp/ui/main_window.py` | Add logger, type hints |
| `rsvp/ui/menu_builder.py` | Add logger, type hints |
| `rsvp/ui/settings_dialog.py` | Add logger, type hints |
| `rsvp/ui/text_input_dialog.py` | Add logger, fix bare excepts, type hints |
| `rsvp/ui/word_display.py` | Add logger, type hints |
| `tests/fixtures/test.md` | New |
| `tests/fixtures/test.html` | New |
| `tests/test_text_processor.py` | Add `load_text_from_file` dispatch tests |
| `tests/conftest.py` | (no change) |

## Per-Item Design

### Item 1 — Fix bare `except Exception` blocks

**Locations (7 total):**

| File | Line | Method | Purpose |
|------|------|--------|---------|
| `rsvp/ui/text_input_dialog.py` | 132 | `_paste_from_clipboard` | Clipboard fallback |
| `rsvp/ui/text_input_dialog.py` | 161 | `_browse_file` | File load error dialog |
| `rsvp/ui/text_input_dialog.py` | 180 | `_fetch_url` | URL fetch error dialog |
| `rsvp/ui/text_input_dialog.py` | 196 | `_accept` (file branch) | File load error dialog |
| `rsvp/ui/text_input_dialog.py` | 206 | `_accept` (url branch) | URL fetch error dialog |
| `rsvp/ui/document_loader.py` | 64 | `load_file` | File load error dialog |
| `rsvp/ui/document_loader.py` | 111 | `_read_clipboard` | Clipboard fallback |

**Two distinct patterns:**

**A. Clipboard fallback (2 instances — lines 132, 111):** Fall back from
`pyperclip` to `QApplication.clipboard()` if pyperclip is unavailable or
fails. These should catch specific pyperclip/clipboard errors.

```python
# Before
except Exception:
    pass  # fall back to Qt clipboard

# After
except (ImportError, OSError) as e:
    logger.debug("pyperclip unavailable, falling back to Qt clipboard: %s", e)
    from PyQt6.QtWidgets import QApplication
    return QApplication.clipboard().text()
```

`pyperclip` raises `pyperclip.PyperclipException` (subclass of `OSError`)
on Linux without `xclip`/`xsel`. `ImportError` covers missing package.
`OSError` covers all subprocess-level clipboard failures. We deliberately
do not catch `Exception` so unexpected errors surface.

**B. File/URL load with user dialog (5 instances):** Show `QMessageBox`
when loading fails. Should catch the specific exceptions that the loading
functions actually raise.

```python
# Before
except Exception as e:
    QMessageBox.warning(self, "Error", f"Failed to load file: {e}")

# After
except (OSError, ValueError) as e:
    logger.exception("Failed to load file: %s", filepath)
    QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
```

For URL fetch sites, the tuple becomes `(requests.RequestException, ValueError)`.

**Exception inventory** (what `load_text_from_file` and `fetch_text_from_url`
actually raise):

| Source | Exception | Why |
|--------|-----------|-----|
| `open()` | `OSError` (incl. `FileNotFoundError`) | File missing / permission denied |
| `load_text_from_epub` | `ValueError` (no chapters) + whatever `ebooklib` raises (`KeyError`, etc.) | Malformed EPUB |
| `load_text_from_pdf` | `ValueError` (no pages) + whatever `fitz` raises | Malformed PDF |
| `extract_text_from_html` | `bs4` rarely raises; malformed HTML returns partial text | n/a |
| `fetch_text_from_url` | `requests.RequestException` (incl. `ConnectionError`, `Timeout`, `HTTPError` via `raise_for_status`) | Network/server error |
| `fetch_text_from_url` | `ValueError` (empty / non-http scheme) | Input validation |

**Decision:** Catch `(OSError, ValueError)` for file loads and
`(requests.RequestException, ValueError)` for URL fetches. `KeyError` and
other "malformed file format" exceptions are not explicitly caught because
we want them logged with traceback; they will still surface as a
`QMessageBox` once the bare-`Exception` net is removed. To avoid
user-facing crashes, the site that calls `load_file`/`fetch_text_from_url`
is wrapped in try/except. If a malformed file causes a `KeyError` from
`ebooklib`, the user sees a `QMessageBox.warning` with the exception
message (as before) and the traceback lands in the log.

**Type-narrowing note:** `pyperclip` does not have a typed stub by default;
its `paste()` returns `Any`. We will not narrow that.

### Item 2 — Type hints on all functions

**Scope:** Every function, method, property, `__init__`, signal handler,
and lambda with an explicit signature. Module-level `_CONSTANTS` and class
attributes (e.g., `Word.text: str` already typed) are left as-is.

**Pattern for Qt signals / slots:** Use `from __future__ import annotations`
or inline annotations. Existing code uses inline annotations. Continue that
style.

**Pattern for `None`-returning methods:** Add `-> None` to all
intentionally void methods (currently many are untyped, defaulting to
`None` at runtime but flagged as missing by mypy).

**Pattern for Qt overrides** (e.g., `paintEvent`, `mousePressEvent`):
Annotate with the Qt type. The `qapp` fixture already pulls in `PyQt6`,
so stubs are available. Use `-> None`.

**Pattern for `QObject` subclasses:** Add `super().__init__(parent)`
typing implicitly via the existing `parent=None` parameter.

**Pattern for dataclasses:** Already typed in `rsvp_engine.py`,
`text_processor.py`, `settings.py`. Verify and add missing.

**`Any` usage:** Use `Any` only when:
- A library has no stubs (e.g., `pyperclip.paste()`)
- A function deliberately accepts mixed types
- A Qt signal's `*args` is heterogeneous

**No runtime validation:** Type hints are for static analysis only. No
beartype / pydantic / dataclass-based validators.

### Item 3 — mypy configuration + `py.typed`

**`pyproject.toml` additions:**

```toml
[tool.mypy]
python_version = "3.10"
files = ["rsvp"]
check_untyped_defs = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_return_any = true
no_implicit_optional = true
ignore_missing_imports = true  # PyQt6 stubs are incomplete
disallow_untyped_defs = false  # Gradual typing — public API first
disallow_incomplete_defs = false  # Same
```

**Marker file:** `rsvp/py.typed` (empty file) signals to downstream
consumers (and to mypy) that the package is typed.

**Exclusions:** Tests, build artifacts, `docs/`, `scripts/`. Tests are
untyped by design (per project convention).

**Gradual rollout:** `disallow_untyped_defs = false` lets the spec land
incrementally. The implementation plan adds all annotations in this spec
(per user decision), so mypy will validate ≥80% by spec end. A follow-up
spec can flip the flag to `true`.

**CI integration:** Not in this spec. The `.github/workflows/build.yml`
already runs `ruff` and tests; adding `mypy` is a one-line addition that
can land as a tiny follow-up if desired (out of scope here to keep the
spec focused).

### Item 4 — CHANGELOG.md

**Format:** [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).

**Sections per release:** `### Added`, `### Changed`, `### Deprecated`,
`### Removed`, `### Fixed`, `### Security`. Use only those with content.

**Backfill strategy:** For each release from 1.0.0 → 1.3.5, summarize
from `git log` and the existing GitHub release notes. Versions are
unambiguous in the commit log (each is a `chore: bump version to X.Y.Z`
commit followed by `feat:`/`fix:` commits). A separate "Unreleased"
section sits at top.

**Top-level structure:**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- (items added in this spec land here)

## [1.3.5] - 2026-05-15
### Added
...
```

**Backfill data sources:**
- `git log --oneline` for commit messages
- `git tag --list` for release boundaries
- GitHub release notes (auto-generated) at
  `https://github.com/cortexuvula/RSVP/releases`

### Item 5 — Test fixtures + dispatch tests

**New fixtures:**

`tests/fixtures/test.md` — small markdown sample covering:
- Headers (`# H1`, `## H2`)
- Bold (`**bold**`)
- Italic (`*italic*`)
- Inline code (`` `code` ``)
- Code block (``` ```python\nprint()\n``` ```)
- Links (`[text](url)`)
- Image (kept as alt text)
- Lists (`- item`)
- HTML embedded (e.g., `<sub>2</sub>`)

`tests/fixtures/test.html` — small HTML sample covering:
- `<p>` paragraphs
- `<h1>`–`<h3>` headers
- `<script>` and `<style>` blocks (to be stripped)
- HTML entities (e.g., `&amp;`, `&lt;`)
- `<a href="...">` links
- `<img alt="...">` (alt text kept)
- `<br>`, `<hr>` block elements

**New tests in `tests/test_text_processor.py`:**

```python
class TestLoadTextFromFile:
    """Tests for the format dispatch in load_text_from_file."""

    def test_dispatches_markdown(self, tmp_path):
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
```

The `test.epub` and `test.pdf` fixtures already exist; their tests live
in the existing `test_text_processor.py` (verified during planning).

### Item 6 — Logging throughout

**Conventions:**

```python
# At top of every module, after imports:
import logging
logger = logging.getLogger(__name__)
```

**Log levels used:**

| Level | When |
|-------|------|
| `DEBUG` | Engine state changes (seek, pause, resume), clipboard fallback paths |
| `INFO` | Document loads (file, URL, paste, clipboard) — include word count |
| `WARNING` | Recoverable errors (settings corruption, file load failure with user dialog) |
| `ERROR` | (not used — UI dialogs are how errors surface to users) |
| `EXCEPTION` | Inside `except` blocks that catch and re-raise to UI; equivalent to `ERROR` + traceback |

**Configure-once principle:** `rsvp/main.py:_configure_logging()` already
configures logging from the `RSVP_LOG_LEVEL` env var. The spec does NOT
add a second configuration point. Tests can override `RSVP_LOG_LEVEL` or
use `caplog` to capture.

**Module-by-module logging additions:**

| Module | Adds |
|--------|------|
| `rsvp/main.py` | Already has `_configure_logging` — keep, type-hint |
| `rsvp/core/__init__.py` | Module logger (re-export) |
| `rsvp/core/constants.py` | (no logging — pure constants) |
| `rsvp/core/rsvp_engine.py` | `DEBUG` on play/pause/seek; `INFO` on text load |
| `rsvp/core/settings.py` | Already has logger — keep |
| `rsvp/core/text_processor.py` | `DEBUG` on format dispatch in `load_text_from_file` |
| `rsvp/ui/bookmark_controller.py` | `INFO` on bookmark add/remove |
| `rsvp/ui/controls.py` | `DEBUG` on slider drag end, WPM change |
| `rsvp/ui/document_loader.py` | `INFO` on file load, `EXCEPTION` on load error |
| `rsvp/ui/main_window.py` | `INFO` on window open/close, `DEBUG` on menu actions |
| `rsvp/ui/menu_builder.py` | (no logging — pure builder) |
| `rsvp/ui/settings_dialog.py` | `INFO` on settings change, `EXCEPTION` on save failure |
| `rsvp/ui/text_input_dialog.py` | `INFO` on URL fetch, `EXCEPTION` on fetch/load error |
| `rsvp/ui/word_display.py` | `DEBUG` on ORP calculation only |

**Log message format:** `f-string` interpolation is used in the existing
`settings.py` (`logger.warning("...: %s", value)`). The spec continues
this lazy-formatting style to avoid formatting cost when the level is
disabled.

**No log file:** Output goes to stderr only. A log file would require
path management and could grow unbounded. Users who want logs can set
`RSVP_LOG_LEVEL=DEBUG` and redirect stderr.

### Item 7 — Delete `requirements.txt`

`requirements.txt` (101 bytes) duplicates `pyproject.toml`. The canonical
source is `pyproject.toml`. Delete `requirements.txt`.

If a lockfile is later desired (`pip-compile` output), it would be
`requirements.lock` and live in a separate location. Not in this spec.

## Commit Plan (Atomic, in this order)

```
chore: remove redundant requirements.txt
docs: add CHANGELOG.md (backfilled from git log)
test: add .md and .html fixtures and dispatch tests
feat: add logging to core and ui modules
fix: replace bare except Exception with specific exception types
feat: add type hints to all functions
chore: add mypy config and py.typed marker
```

**Rationale for ordering:**

1. `requirements.txt` removal is a pure no-op for tests, no risk — good warm-up.
2. CHANGELOG documents everything that follows.
3. Test fixtures come before the code changes they cover (good test discipline
   even if we're adding fixtures for existing dispatch logic, not new logic).
4. Logging foundation comes before the bare-except fix so the except fix
   can use `logger.exception()` and the new logger is in place.
5. Bare excepts use the logger we just added.
6. Type hints come after the code is in its final form (with logging) so
   we're annotating clean code.
7. mypy config validates the just-added type hints.

## Testing Strategy

- **No new test framework.** Use existing `pytest` + `pytest-qt`.
- **Run `ruff` and `pytest` after each commit** to ensure no regression.
- **Type-hint commit includes a mypy dry-run** to confirm the mypy config
  (added in the next commit) will pass — but does not run mypy as a gate
  until commit 7.
- **Final mypy run** after commit 7 should report zero errors in
  `rsvp/` (target: zero or near-zero; any remaining mypy errors get
  fixed inline).

## Risk and Mitigation

| Risk | Mitigation |
|------|------------|
| Narrowing `except Exception` to specific types exposes previously-swallowed bugs in the user-facing dialog | The QMessageBox is preserved for all expected error types. Unexpected exceptions still surface as a dialog because they propagate. User sees a meaningful error message either way. |
| Adding type hints to Qt signal handlers confuses mypy due to incomplete PyQt6 stubs | `ignore_missing_imports = true` and per-line `# type: ignore[arg-type]` only where genuinely needed (documented in code with a brief comment). |
| Backfilled CHANGELOG entries are inaccurate | Backfill is conservative — only items with unambiguous commit history. Anything unclear goes in a "## Notes" appendix at the bottom of the changelog for human review. |
| Logging in hot paths (e.g., word_display paint) adds overhead | `DEBUG` calls are no-ops when level is `WARNING` (default). Paint-event DEBUG gated behind explicit env var. |

## Out of Scope (Explicitly)

- mypy in CI (small follow-up, but not part of this spec)
- Settings singleton refactor (Spec 2)
- `QPainter` context-manager fix (Spec 2)
- `CONTRIBUTING.md` (Spec 2)
- All feature work (Spec 3+)
- Renaming `requirements.txt` to a lockfile
- Adding log files / rotating logs / structured logging
- Per-call logging for settings reads (only changes are logged)

## Success Criteria

- [ ] `ruff check` and `pytest` pass on every commit
- [ ] `mypy rsvp` reports zero errors (any `# type: ignore` comments are
  justified in code with a one-line comment)
- [ ] All 7 bare `except Exception` blocks narrowed to specific types with `logger.exception()` calls
- [ ] All 7 items above landed in the named atomic commits
- [ ] No public API change (no breaking change to consumers)
- [ ] CHANGELOG.md is up-to-date through 1.3.5
- [ ] Test coverage for `load_text_from_file` covers `.md`, `.html`, `.htm`, and `.txt` dispatch
