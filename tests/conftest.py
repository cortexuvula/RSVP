"""Pytest configuration and fixtures."""

import pytest

from rsvp.core.rsvp_engine import RSVPEngine


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication for tests that need Qt."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def force_playing(engine: RSVPEngine) -> None:
    """Force the engine into a 'playing' internal state for unit tests.

    This centralises the coupling to ``_state.is_playing`` so that tests
    don't reach into the private attribute independently.
    """
    engine._state.is_playing = True
