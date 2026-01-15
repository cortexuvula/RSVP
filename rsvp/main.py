"""Main entry point for RSVP application."""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from rsvp.ui.main_window import MainWindow


def main():
    """Run the RSVP application."""
    app = QApplication(sys.argv)
    app.setApplicationName("RSVP Reader")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("RSVP")

    # Enable high DPI scaling
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
