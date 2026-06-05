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
