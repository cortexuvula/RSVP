# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Reading statistics: track all-time totals (words, time, sessions, lifetime avg WPM), per-document breakdown, and last 30 sessions. View via Help → Reading Statistics.
- Theme presets: switch between Dark, Light, Sepia, and Solarized Light via Settings → Display → Theme. Selecting a theme updates the colors and font family; manual edits switch the dropdown to "Custom".

### Changed
- Replace `requirements.txt` with `pyproject.toml` as the canonical dependency source

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
