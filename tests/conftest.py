"""Pytest configuration and fixtures."""
import pytest


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for tests that need Qt."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
