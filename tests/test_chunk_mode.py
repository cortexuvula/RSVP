"""Tests for chunk mode (process_text_into_chunks + engine + settings)."""

import pytest

from rsvp.core.constants import PAUSE_SENTENCE
from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import RSVPSettings, SettingsManager
from rsvp.core.text_processor import (
    calculate_orp,
    process_text,
    process_text_into_chunks,
)


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Construct a SettingsManager with an isolated config path.

    Patches get_settings_manager in the consumer modules (engine, settings_dialog)
    rather than the source. Python's from-import binding means consumer modules
    hold a local reference that doesn't see patches on the source.
    """
    from rsvp.core import rsvp_engine as engine_mod
    from rsvp.core import settings as settings_mod
    from rsvp.ui import settings_dialog as dialog_mod

    mgr = SettingsManager.__new__(SettingsManager)
    mgr._settings = RSVPSettings()
    mgr._settings_were_reset = False
    mgr._save_failed = False
    mgr._config_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "get_settings_manager", lambda: mgr)
    monkeypatch.setattr(engine_mod, "get_settings_manager", lambda: mgr)
    monkeypatch.setattr(dialog_mod, "get_settings_manager", lambda: mgr)
    return mgr


class TestProcessTextIntoChunks:
    def test_chunk_size_1_falls_through(self):
        result = process_text_into_chunks("one two three four", 1)
        assert [w.text for w in result] == ["one", "two", "three", "four"]
        # Should be the same as process_text
        assert [w.text for w in result] == [w.text for w in process_text("one two three four")]

    def test_chunk_size_2(self):
        result = process_text_into_chunks("one two three four", 2)
        assert [w.text for w in result] == ["one two", "three four"]

    def test_chunk_size_3_with_short_last(self):
        result = process_text_into_chunks("one two three four five", 3)
        assert [w.text for w in result] == ["one two three", "four five"]

    def test_empty_input_returns_empty(self):
        assert process_text_into_chunks("", 3) == []
        assert process_text_into_chunks("   ", 3) == []
        assert process_text_into_chunks("\n\n", 3) == []

    def test_paragraph_alignment(self):
        # First para: 3 words -> 2 chunks ("one two", "three")
        # Second para: 2 words -> 1 chunk ("four five")
        # Following process_text's convention, only the FIRST paragraph's last
        # chunk gets paragraph_break_after=True (the last paragraph doesn't
        # need a pause since the timer stops at the end).
        text = "one two three\n\nfour five"
        result = process_text_into_chunks(text, 2)
        assert [w.text for w in result] == ["one two", "three", "four five"]
        # Chunk 1 ("three") ends the first paragraph
        assert result[1].paragraph_break_after is True
        # Chunk 2 ("four five") is the last chunk; no break flag (matches process_text)
        assert result[2].paragraph_break_after is False

    def test_paragraph_with_uneven_chunks(self):
        text = "one two three four five\n\nsix"
        result = process_text_into_chunks(text, 2)
        assert [w.text for w in result] == ["one two", "three four", "five", "six"]
        # First paragraph ends at index 2 ("five")
        assert result[2].paragraph_break_after is True
        # Second paragraph ends at index 3 ("six") — but it's the last, so no break
        assert result[3].paragraph_break_after is False

    def test_orp_from_first_word(self):
        result = process_text_into_chunks("the quick brown", 2)
        # First word "the" has ORP index 1
        assert result[0].orp_index == calculate_orp("the")
        # In the chunk "the quick", the ORP is at position 1
        assert result[0].text[1] == "h"

    def test_pause_from_last_word(self):
        # "world." ends with "." -> PAUSE_SENTENCE
        result = process_text_into_chunks("hello world. how are you", 2)
        assert result[0].pause_after == PAUSE_SENTENCE

    def test_no_mid_chunk_paragraph_breaks(self):
        # 3-word paragraph with chunk_size=2 -> 2 chunks ("one two", "three")
        # The 3 words fit in 2 chunks with no mid-chunk split
        text = "one two three\n\nfour"
        result = process_text_into_chunks(text, 2)
        # First para "one two three" -> 2 chunks; second para "four" -> 1 chunk
        assert [w.text for w in result] == ["one two", "three", "four"]
        # Chunk 1 ("three") ends first paragraph
        assert result[1].paragraph_break_after is True
        # Chunk 2 ("four") is the last; no break
        assert result[2].paragraph_break_after is False


class TestEngineWithChunks:
    def test_load_text_with_chunk_size_2(self, qapp, isolated_settings):
        isolated_settings.settings.chunk_size = 2
        engine = RSVPEngine()
        engine.load_text("one two three four five six")
        # 3 chunks: "one two", "three four", "five six"
        assert engine.word_count == 3
        assert engine.state.words[0].text == "one two"
        assert engine.state.words[1].text == "three four"
        assert engine.state.words[2].text == "five six"

    def test_load_text_with_default_chunk_size_1(self, qapp, isolated_settings):
        engine = RSVPEngine()
        engine.load_text("one two three four")
        assert engine.word_count == 4
        assert engine.state.words[0].text == "one"

    def test_paragraph_pause_preserved_with_chunks(self, qapp, isolated_settings):
        isolated_settings.settings.chunk_size = 2
        engine = RSVPEngine()
        engine.load_text("one two\n\nthree four")
        # 2 chunks; first ends a paragraph (chunk 0 = "one two")
        assert engine.state.words[0].paragraph_break_after is True
        # Chunk 1 ("three four") is the last; no break
        assert engine.state.words[1].paragraph_break_after is False

    def test_chunks_emit_word_changed_normally(self, qapp, isolated_settings):
        isolated_settings.settings.chunk_size = 2
        engine = RSVPEngine()
        engine.load_text("one two three four")
        # Each chunk is a Word; current_word is the first chunk
        assert engine.state.current_word.text == "one two"


class TestSettingsDialogChunkSize:
    def test_dialog_has_chunk_size_combo(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert hasattr(dlg, "chunk_size_combo")
        assert dlg.chunk_size_combo.count() == 3

    def test_chunk_size_combo_default_is_1(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        assert dlg.chunk_size_combo.currentIndex() == 0  # 1 word

    def test_apply_persists_chunk_size(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        dlg = SettingsDialog()
        dlg.chunk_size_combo.setCurrentIndex(2)  # 3 words
        dlg._apply()
        assert isolated_settings.settings.chunk_size == 3

    def test_load_clamps_out_of_range(self, qapp, isolated_settings):
        from rsvp.ui.settings_dialog import SettingsDialog

        isolated_settings.settings.chunk_size = 99  # Out of range
        dlg = SettingsDialog()
        # Should clamp to index 2 (the max)
        assert dlg.chunk_size_combo.currentIndex() == 2
