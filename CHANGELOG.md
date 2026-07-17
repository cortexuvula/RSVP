# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.6.0] - 2026-07-17

### Fixed
- TTS stop race: `set_enabled(False)` and pause/stop now call `_worker.stop()` directly instead of via a queued signal. The queued signal could never interrupt the worker while it was blocked inside `pyttsx3.runAndWait()`, so disabling TTS mid-utterance failed until the utterance finished on its own. Aligns with the proven `shutdown()` pattern.
- `_toggle_always_on_top` signature mismatch with the `MenuHost` protocol — the method ignored the `checked` bool Qt passes via `triggered(bool)` and re-read `isChecked()` instead, then persisted a stale value.
- Theme-font test no longer depends on OS font availability (CI Windows runners don't ship "Georgia"); now asserts the dialog *requests* the theme's font via `setCurrentFont`.
- URL fetch failures now log the full traceback at the point of failure in `_FetchWorker.run()`, so errors are traceable even if the worker thread is torn down before the error signal is delivered.

### Changed
- Pin major-version upper bounds on all runtime dependencies (`PyQt6<7`, `requests<3`, `beautifulsoup4<5`, `pyperclip<2`, `ebooklib<1`, `pymupdf<2`, `pyttsx3<3`) so breaking releases can't silently land via `pip install`.
- Remove the dead `get_settings_manager()` singleton (zero production call sites since the Spec 2 DI refactor). Settings are now constructed once at the app entry point in `main.py` and threaded down via dependency injection.
- `MenuHost.engine` declared as a read-only `@property` in the protocol to match `MainWindow`'s existing exposure.

### Added
- mypy type-checking step in the CI lint job (catches signature/None-safety issues that type hints are meant to prevent).
- Python 3.10 and 3.12 added to the CI test matrix (previously only 3.11), matching the versions declared in `pyproject.toml`.
- `SECURITY.md` documenting how to report vulnerabilities privately via GitHub advisories, with response-time commitments and the security-relevant attack surface (SSRF-hardened URL fetching, file parsing, atomic persistence).
- README now documents TTS, reading statistics, theme presets, and the full keyboard shortcuts table (including Ctrl+Shift+O, Ctrl+Shift+B, Ctrl+Q, F1).

### CI/Dependencies
- Consolidated bump of all GitHub Actions to latest versions: `actions/checkout` v6, `actions/setup-python` v6, `actions/upload-artifact` v7, `actions/download-artifact` v8, `codecov/codecov-action` v6. Closed 5 stale Dependabot PRs.
- Lint job now installs project dependencies so mypy checks against real types (PyQt6, etc.) rather than treating them as `Any`.

## [1.5.0] - 2026-06-11

### Added
- SSRF protection in URL fetching: DNS-resolved IPs are checked against private/reserved ranges (loopback, RFC 1918, link-local, CG-NAT, IETF assignments, IPv6-mapped IPv4)
- Atomic file writes for settings and stats via `tempfile.mkstemp()` + `os.replace()` — prevents corruption from mid-write crashes
- Shared config directory helper (`rsvp/core/config.py`) used by both `SettingsManager` and `StatsManager`
- `MenuHost(Protocol)` in menu_builder.py — explicit interface contract for the host object
- New test files: `test_document_loader.py`, `test_text_input_dialog.py`
- CRLF line ending normalization in `process_text()` for cross-platform text handling
- UTF-8 fallback with `errors="replace"` for non-UTF-8 files
- `_read_file_with_fallback()` encoding test coverage
- `force_playing()` test helper in conftest.py to centralize private-state coupling

### Changed
- TTS playback now runs on a dedicated QThread — UI stays responsive during speech
- URL fetching in TextInputDialog runs on a background QThread instead of blocking the UI
- TTS stop/dispatch routes through worker thread signals for thread safety
- Settings and stats `save()` no longer re-raise OSError — errors are logged and flagged instead
- `SettingsDialog` requires explicit `settings=` parameter (no more singleton fallback)
- `calculate_orp()` uses proportional formula `min(length // 3, 4)` instead of hardcoded if/elif
- `strip_markdown()` strips all formatting characters (`*_~``) instead of greedy regex matching
- `SettingsDialog.reject()` only saves to disk if settings were actually modified
- IPv4-mapped IPv6 addresses (e.g. `::ffff:127.0.0.1`) are now checked against IPv4 reserved ranges
- `FILE_DIALOG_FILTER` extracted to shared constant in `rsvp/core/constants.py`
- Type annotations added to UI widget methods in controls.py and word_display.py

### Fixed
- Duplicate logger initialization in `bookmark_controller.py`
- Duplicate entries in `rsvp/core/__init__.py` `__all__` list
- Stats recorder now correctly sets `finished=True` when reading reaches the last word
- TextInputDialog caches fetched text to avoid redundant synchronous re-fetch on accept
- Concurrent fetch guard prevents multiple simultaneous URL fetches in TextInputDialog

## [1.4.0] - 2026-06-06

### Added
- Text-to-speech (TTS): offline, uses the OS default voice via pyttsx3. Each displayed word is spoken as it appears; pause interrupts mid-utterance. Toggle in Settings → Behavior.
- Reading statistics: track all-time totals (words, time, sessions, lifetime avg WPM), per-document breakdown, and last 30 sessions. View via Help → Reading Statistics.
- Theme presets: switch between Dark, Light, Sepia, and Solarized Light via Settings → Display → Theme. Selecting a theme updates the colors and font family; manual edits switch the dropdown to "Custom".

### Changed
- Replace `requirements.txt` with `pyproject.toml` as the canonical dependency source
- Replace `get_settings_manager()` singleton with constructor dependency injection across `MainWindow`, `RSVPEngine`, document/bookmark controllers, settings dialog, and word display, enabling per-test isolated settings fixtures

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
