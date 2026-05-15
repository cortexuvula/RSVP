"""Main entry point for RSVP application."""

import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from rsvp import __version__
from rsvp.ui.main_window import MainWindow


def _configure_logging():
    """Configure logging for the application."""
    level_name = os.environ.get("RSVP_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


def main():
    """Run the RSVP application."""
    _configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("RSVP Reader")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("RSVP")

    # Enable high DPI scaling
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
