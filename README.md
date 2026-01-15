# RSVP Reader

A cross-platform Rapid Serial Visual Presentation (RSVP) speed reading application built with Python and PyQt6.

## Features

- **RSVP Display**: Shows text one word at a time with Optimal Recognition Point (ORP) highlighting
- **Adjustable Speed**: Control reading speed from 50 to 2000 words per minute
- **Multiple Input Sources**: Load text from files, URLs, or clipboard
- **Smart Pausing**: Automatically pauses longer at sentence and clause boundaries
- **Progress Tracking**: Visual progress bar with time remaining estimate
- **Bookmarks**: Save and return to positions in files
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

- Python 3.9 or higher
- PyQt6

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
| Left/Right | Skip 10 words |
| Shift+Left/Right | Previous/Next sentence |
| Up/Down | Increase/Decrease speed |
| Home/End | Go to start/end |
| Ctrl+O | Load text |
| Ctrl+V | Paste and read |
| Ctrl+B | Add bookmark |
| Ctrl+, | Settings |
| F11 | Fullscreen |
| Escape | Pause |

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

MIT License
