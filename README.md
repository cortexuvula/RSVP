# RSVP Reader

A cross-platform Rapid Serial Visual Presentation (RSVP) speed reading application built with Python and PyQt6.

## Features

- **RSVP Display**: Shows text one word at a time with Optimal Recognition Point (ORP) highlighting
- **Adjustable Speed**: Control reading speed from 50 to 2000 words per minute
- **Multiple Input Sources**: Load text from files (.txt, .epub, .pdf, .md, .html), URLs, or clipboard
- **Smart Pausing**: Automatically pauses longer at sentence and clause boundaries
- **Progress Tracking**: Visual progress bar with time remaining estimate
- **Bookmarks**: Save and return to positions in files
- **Theme Presets**: Built-in Dark, Light, Sepia, and Solarized Light themes, plus fully custom colors and fonts
- **Text-to-Speech**: Optional offline narration of each word via system TTS (pyttsx3), runs on a background thread so the UI stays responsive
- **Reading Statistics**: Tracks all-time totals (words read, time, sessions, lifetime average WPM), per-document breakdowns, and the last 30 sessions
- **Customizable Display**: Adjust fonts, colors, and display settings
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

### From Source

```bash
# Clone the repository
git clone <repository-url>
cd RSVP

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Requirements

- Python 3.10 or higher
- PyQt6

### Development

```bash
# Install dev dependencies (pytest, ruff, etc.)
pip install -e ".[dev]"

# Run the test suite (Qt offscreen needed in headless environments)
QT_QPA_PLATFORM=offscreen pytest tests/ --cov=rsvp

# Lint and format
ruff check .
ruff format .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development setup, code style, and PR process.

## Usage

### Running the Application

```bash
# Run directly
python -m rsvp.main

# Or if installed
rsvp
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| S | Stop |
| Left/Right | Skip 10 words back/forward |
| Shift+Left/Right | Previous/Next sentence |
| Up/Down | Increase/Decrease speed |
| Home/End | Go to start/end |
| Ctrl+O | Load Text (file, URL, or clipboard) |
| Ctrl+Shift+O | Open File (direct file picker) |
| Ctrl+V | Paste and Read |
| Ctrl+B | Add Bookmark |
| Ctrl+Shift+B | Remove Bookmark |
| Ctrl+, | Settings |
| Ctrl+Q | Exit |
| F1 | Keyboard Shortcuts help |
| F11 | Fullscreen |
| Escape | Pause and return focus to display |

> Tip: Press **F1** inside the app for an in-app shortcuts reference.
>
> **Text-to-Speech** and **Reading Statistics** have no keyboard shortcuts — enable TTS under *Settings → Behavior*, and open statistics via *Help → Reading Statistics*.

### Text-to-Speech (TTS)

Enable narration under **Settings → Behavior → Text-to-speech**. When enabled, each displayed word is spoken aloud using your operating system's default voice via `pyttsx3` — no internet connection required. Playback runs on a background thread, so reading speed and the UI are unaffected. If no system TTS engine is available, the feature degrades gracefully to silent operation.

### Reading Statistics

Open via **Help → Reading Statistics** to view:

- **All-time totals**: total words read, total reading time, session count, and lifetime average WPM
- **Top documents**: ranked by words read
- **Recent sessions**: the last 30 sessions with average and peak WPM

Statistics persist to `stats.json` in the config directory (see [Configuration](#configuration)). Use the **Reset Statistics...** button in the dialog to clear history.

### Themes

Choose a look under **Settings → Display → Theme**. Built-in presets:

| Theme | Text | ORP | Background | Font |
|-------|------|-----|------------|------|
| Dark (default) | White | Red | Dark gray | Arial |
| Light | Dark | Red | Off-white | Arial |
| Sepia | Sepia brown | Sienna | Cream | Georgia |
| Solarized Light | Solar text | Yellow | Solar base 3 | Arial |

Selecting any preset loads its colors and font; editing a color or font switches the dropdown to **Custom**, preserving your choices.

## Building Standalone Executables

### Using PyInstaller

```bash
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --name "RSVP Reader" --windowed --onefile rsvp/main.py
```

The executable will be created in the `dist` directory.

### Platform-Specific Builds

#### Windows
```bash
pyinstaller --name "RSVP Reader" --windowed --onefile --icon=icon.ico rsvp/main.py
```

#### macOS
```bash
pyinstaller --name "RSVP Reader" --windowed --onefile --icon=icon.icns rsvp/main.py
```

#### Linux
```bash
pyinstaller --name "rsvp-reader" --windowed --onefile rsvp/main.py
```

## Configuration

Settings are stored in platform-specific locations:
- **Windows**: `%LOCALAPPDATA%\RSVP\settings.json`
- **macOS**: `~/Library/Application Support/RSVP/settings.json`
- **Linux**: `~/.config/rsvp/settings.json`

## How RSVP Works

RSVP (Rapid Serial Visual Presentation) displays text one word at a time at a fixed position on screen. This eliminates the eye movements required in traditional reading, potentially allowing for faster reading speeds.

### Optimal Recognition Point (ORP)

Each word has an Optimal Recognition Point - the character position where the eye naturally focuses. This application highlights the ORP in a different color and centers each word on this point, making it easier for the brain to quickly recognize words.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Security

Found a security issue? See [SECURITY.md](SECURITY.md) for how to report it privately.
