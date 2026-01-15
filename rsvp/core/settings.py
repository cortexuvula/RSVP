"""Settings management for RSVP application."""
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


@dataclass
class RSVPSettings:
    """Application settings."""
    # Display settings
    wpm: int = 300
    font_family: str = "Arial"
    font_size: int = 48
    text_color: str = "#FFFFFF"
    background_color: str = "#1E1E1E"
    orp_color: str = "#FF6B6B"

    # Behavior settings
    pause_at_paragraphs: bool = True
    auto_save_position: bool = True

    # Window settings
    window_width: int = 800
    window_height: int = 600
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    always_on_top: bool = False

    # Recent files
    recent_files: list[str] = field(default_factory=list)
    max_recent_files: int = 10

    # Bookmarks: dict mapping filepath to list of word indices
    bookmarks: dict[str, list[int]] = field(default_factory=dict)


class SettingsManager:
    """Manager for loading and saving settings."""

    def __init__(self):
        self._settings = RSVPSettings()
        self._config_path = self._get_config_path()
        self.load()

    def _get_config_path(self) -> Path:
        """Get the path to the config file."""
        # Use appropriate config directory for each platform
        import platform

        system = platform.system()

        if system == "Windows":
            base = Path.home() / "AppData" / "Local" / "RSVP"
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support" / "RSVP"
        else:  # Linux and others
            xdg_config = Path(
                __import__('os').environ.get('XDG_CONFIG_HOME', Path.home() / '.config')
            )
            base = xdg_config / "rsvp"

        base.mkdir(parents=True, exist_ok=True)
        return base / "settings.json"

    @property
    def settings(self) -> RSVPSettings:
        """Get current settings."""
        return self._settings

    def load(self):
        """Load settings from file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Update settings with loaded values
                    for key, value in data.items():
                        if hasattr(self._settings, key):
                            setattr(self._settings, key, value)
            except (json.JSONDecodeError, IOError):
                # Use defaults if config is corrupted
                pass

    def save(self):
        """Save settings to file."""
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._settings), f, indent=2)
        except IOError:
            pass

    def add_recent_file(self, filepath: str):
        """Add a file to the recent files list."""
        # Remove if already exists
        if filepath in self._settings.recent_files:
            self._settings.recent_files.remove(filepath)

        # Add to front
        self._settings.recent_files.insert(0, filepath)

        # Trim to max
        self._settings.recent_files = self._settings.recent_files[:self._settings.max_recent_files]

        self.save()

    def add_bookmark(self, filepath: str, word_index: int):
        """Add a bookmark for a file."""
        if filepath not in self._settings.bookmarks:
            self._settings.bookmarks[filepath] = []

        if word_index not in self._settings.bookmarks[filepath]:
            self._settings.bookmarks[filepath].append(word_index)
            self._settings.bookmarks[filepath].sort()
            self.save()

    def remove_bookmark(self, filepath: str, word_index: int):
        """Remove a bookmark."""
        if filepath in self._settings.bookmarks:
            if word_index in self._settings.bookmarks[filepath]:
                self._settings.bookmarks[filepath].remove(word_index)
                self.save()

    def get_bookmarks(self, filepath: str) -> list[int]:
        """Get bookmarks for a file."""
        return self._settings.bookmarks.get(filepath, [])


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
