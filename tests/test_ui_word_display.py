"""Smoke tests for word display widgets."""

import pytest

from rsvp.core.text_processor import Word

pytest.importorskip("pytestqt", reason="pytest-qt required for UI tests")


@pytest.fixture
def word_display(qtbot):
    from rsvp.ui.word_display import WordDisplayWidget

    w = WordDisplayWidget()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def orp_display(qtbot):
    from rsvp.ui.word_display import ORPWordDisplay

    w = ORPWordDisplay()
    qtbot.addWidget(w)
    return w


class TestORPWordDisplay:
    def test_instantiates(self, orp_display):
        assert orp_display is not None
        assert orp_display.minimumHeight() >= 100

    def test_paints_with_no_word(self, orp_display, qtbot):
        orp_display.set_word(None)
        orp_display.resize(400, 200)
        orp_display.show()
        qtbot.waitExposed(orp_display)
        # Should not crash on paint
        orp_display.repaint()

    def test_paints_with_word(self, orp_display, qtbot):
        word = Word(text="example", orp_index=2, pause_after=1.0)
        orp_display.set_word(word)
        orp_display.resize(400, 200)
        orp_display.show()
        qtbot.waitExposed(orp_display)
        orp_display.repaint()

    def test_set_word_stores_value(self, orp_display):
        word = Word(text="hello", orp_index=1, pause_after=1.0)
        orp_display.set_word(word)
        assert orp_display._word is word

    def test_update_settings_reloads(self, orp_display):
        orp_display.update_settings()
        # Should pick up current settings without crashing
        assert orp_display._font is not None


class TestWordDisplayWidget:
    def test_instantiates(self, word_display):
        assert word_display is not None

    def test_set_word_delegates(self, word_display):
        word = Word(text="hi", orp_index=0, pause_after=1.0)
        word_display.set_word(word)
        assert word_display.word_display._word is word

    def test_update_settings_delegates(self, word_display):
        # Should not raise
        word_display.update_settings()
