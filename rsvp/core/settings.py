"""Settings management for RSVP application."""

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field

from rsvp.core.config import get_config_dir
from rsvp.core.themes import DEFAULT_THEME_NAME

logger = logging.getLogger(__name__)


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
    tts_enabled: bool = False

    # Window settings
    window_width: int = 800
    window_height: int = 600
    window_x: int | None = None
    window_y: int | None = None
    always_on_top: bool = False

    # Theme
    theme_name: str = DEFAULT_THEME_NAME

    # Recent files
    recent_files: list[str] = field(default_factory=list)
    max_recent_files: int = 10

    # Bookmarks: dict mapping filepath to list of word indices
    bookmarks: dict[str, list[int]] = field(default_factory=dict)

    # Saved reading positions: maps source path/URL to word index
    saved_positions: dict[str, int] = field(default_factory=dict)


class SettingsManager:
    """Manager for loading and saving settings."""

    def __init__(self) -> None:
        self._settings = RSVPSettings()
        self._settings_were_reset = False
        self._save_failed = False
        self._config_path = get_config_dir() / "settings.json"
        self.load()

    @property
    def settings(self) -> RSVPSettings:
        """Get current settings."""
        return self._settings

    def load(self) -> None:
        """Load settings from file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self._settings, key):
                            setattr(self._settings, key, value)
            except (OSError, json.JSONDecodeError):
                backup_path = self._config_path.with_suffix(".json.bak")
                try:
                    shutil.copy2(self._config_path, backup_path)
                except OSError as e:
                    logger.warning("Could not back up corrupted settings file: %s", e)
                logger.warning(
                    "Settings file corrupted, reset to defaults. Backup: %s",
                    backup_path,
                )
                self._settings = RSVPSettings()
                self._settings_were_reset = True

    def was_reset(self) -> bool:
        """Check if settings were reset due to corruption. Clears the flag after reading."""
        result = self._settings_were_reset
        self._settings_were_reset = False
        return result

    def save_failed(self) -> bool:
        """Check if the last save attempt failed. Clears the flag after reading."""
        result = self._save_failed
        self._save_failed = False
        return result

    def save(self) -> None:
        """Save settings to file atomically.

        Writes to a temp file first, then uses os.replace() for an atomic
        rename so that a crash mid-write never leaves a truncated file.
        """
        config_dir = self._config_path.parent
        tmp_fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(asdict(self._settings), f, indent=2)
            os.replace(tmp_path, self._config_path)
        except OSError as e:
            self._save_failed = True
            logger.warning("Failed to save settings to %s: %s", self._config_path, e)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def add_recent_file(self, filepath: str) -> None:
        """Add a file to the recent files list."""
        if filepath in self._settings.recent_files:
            self._settings.recent_files.remove(filepath)

        self._settings.recent_files.insert(0, filepath)

        self._settings.recent_files = self._settings.recent_files[: self._settings.max_recent_files]

        self.save()

    def add_bookmark(self, filepath: str, word_index: int) -> None:
        """Add a bookmark for a file."""
        if filepath not in self._settings.bookmarks:
            self._settings.bookmarks[filepath] = []

        if word_index not in self._settings.bookmarks[filepath]:
            self._settings.bookmarks[filepath].append(word_index)
            self._settings.bookmarks[filepath].sort()
            self.save()

    def remove_bookmark(self, filepath: str, word_index: int) -> None:
        """Remove a bookmark."""
        if filepath in self._settings.bookmarks:
            if word_index in self._settings.bookmarks[filepath]:
                self._settings.bookmarks[filepath].remove(word_index)
                self.save()

    def get_bookmarks(self, filepath: str) -> list[int]:
        """Get bookmarks for a file."""
        return self._settings.bookmarks.get(filepath, [])

    def save_position(self, source: str, index: int) -> None:
        """Save reading position for a source."""
        self._settings.saved_positions[source] = index
        self.save()

    def get_position(self, source: str) -> int | None:
        """Get saved reading position for a source."""
        return self._settings.saved_positions.get(source)

    def clear_position(self, source: str) -> None:
        """Clear saved reading position for a source."""
        self._settings.saved_positions.pop(source, None)
        self.save()
