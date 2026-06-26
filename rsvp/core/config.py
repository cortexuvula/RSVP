"""Shared configuration path logic for RSVP application."""

import os
import platform
from pathlib import Path


def get_config_dir(app_name: str = "RSVP") -> Path:
    """Return the platform-appropriate configuration directory for *app_name*.

    Creates the directory (and any parents) if it doesn't exist.
    """
    system = platform.system()

    if system == "Windows":
        base = Path.home() / "AppData" / "Local" / app_name
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / app_name
    else:  # Linux and others
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        base = xdg_config / app_name.lower()

    base.mkdir(parents=True, exist_ok=True)
    return base
