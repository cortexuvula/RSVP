"""Main entry point for RSVP application."""

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from rsvp import __version__
from rsvp.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure logging for the application."""
    level_name = os.environ.get("RSVP_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("rsvp").setLevel(level)


def _resolve_icon_path() -> Path | None:
    """Locate icon.png in both dev runs and PyInstaller bundles."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    candidates = []
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "assets" / "icon.png")
    repo_root = Path(__file__).resolve().parent.parent
    candidates.append(repo_root / "assets" / "icon.png")
    for path in candidates:
        if path.is_file():
            return path
    return None


def main() -> None:
    """Run the RSVP application."""
    _configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("RSVP Reader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RSVP")
    logger.info("RSVP Reader starting (version %s)", __version__)

    icon_path = _resolve_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    # Enable high DPI scaling
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
