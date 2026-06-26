"""Tests for the TTS module."""

import threading
from unittest.mock import MagicMock

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.settings import RSVPSettings
from rsvp.core.text_processor import Word
from rsvp.core.tts import (
    NullDriver,
    TTSController,
    create_tts_driver,
)


class TestNullDriver:
    """NullDriver methods are no-ops and should never raise."""

    def test_say_is_noop(self):
        NullDriver().say("hello")  # no exception

    def test_run_and_wait_is_noop(self):
        NullDriver().run_and_wait()

    def test_stop_is_noop(self):
        NullDriver().stop()


class TestCreateTTSDriver:
    def test_returns_object_with_required_methods(self):
        driver = create_tts_driver()
        assert hasattr(driver, "say")
        assert hasattr(driver, "run_and_wait")
        assert hasattr(driver, "stop")

    def test_returns_usable_object(self):
        """The returned driver should not raise on basic method calls.

        On systems where pyttsx3.init() succeeds, this is a Pyttsx3Driver.
        On others, it's a NullDriver. Either way, the call should not
        raise and the methods should exist.
        """
        driver = create_tts_driver()
        driver.say("test")  # no exception
        driver.stop()  # no exception


class TestTTSController:
    def test_disabled_by_default(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        assert ctrl.enabled is False
        ctrl.shutdown()

    def test_set_enabled_true(self, qapp):
        engine = RSVPEngine()
        ctrl = TTSController(engine, driver=NullDriver())
        ctrl.set_enabled(True)
        assert ctrl.enabled is True
        ctrl.shutdown()

    def test_set_enabled_false_calls_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        mock_driver.reset_mock()
        ctrl.set_enabled(False)
        # Process events so the queued _stop_requested signal reaches the worker thread
        qapp.processEvents()
        mock_driver.stop.assert_called()
        ctrl.shutdown()

    def test_word_changed_with_null_driver_does_nothing(self, qapp):
        engine = RSVPEngine()
        # Constructing the controller subscribes it to engine signals;
        # the only check is that emitting a word doesn't raise.
        ctrl = TTSController(engine, driver=NullDriver())
        assert ctrl is not None
        # Should not raise even when a word is emitted
        engine.word_changed.emit(Word(text="hello", orp_index=0, pause_after=1.0))
        ctrl.shutdown()

    def test_word_changed_speaks_when_enabled(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        assert ctrl.enabled
        mock_driver.reset_mock()

        # Use an event to wait for the worker thread to complete
        speak_done = threading.Event()
        original_run_and_wait = mock_driver.run_and_wait

        def tracking_run_and_wait():
            original_run_and_wait()
            speak_done.set()

        mock_driver.run_and_wait = tracking_run_and_wait

        engine.word_changed.emit(Word(text="hello", orp_index=0, pause_after=1.0))
        assert speak_done.wait(timeout=2.0), "TTS worker did not speak in time"
        mock_driver.say.assert_called_once_with("hello")
        ctrl.shutdown()

    def test_pause_calls_driver_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        assert ctrl.enabled
        engine.load_text("hello world")
        mock_driver.reset_mock()
        engine.play()
        engine.pause()
        # Process events so the queued _stop_requested signal reaches the worker thread
        qapp.processEvents()
        mock_driver.stop.assert_called()
        ctrl.shutdown()

    def test_pause_does_not_call_stop_when_disabled(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)  # NOT enabled
        assert not ctrl.enabled
        engine.load_text("hello world")
        engine.play()
        engine.pause()
        mock_driver.stop.assert_not_called()
        ctrl.shutdown()

    def test_shutdown_calls_driver_stop(self, qapp):
        engine = RSVPEngine()
        mock_driver = MagicMock()
        ctrl = TTSController(engine, driver=mock_driver)
        ctrl.set_enabled(True)
        assert ctrl.enabled
        mock_driver.reset_mock()
        ctrl.shutdown()
        # shutdown() calls _stop_requested.emit() (queued) then thread.quit()+wait()
        # The wait() should ensure the worker processes the stop signal
        mock_driver.stop.assert_called()


class TestTTSEnabledInSettings:
    def test_default_is_false(self):
        s = RSVPSettings()
        assert s.tts_enabled is False

    def test_can_be_set_to_true(self):
        s = RSVPSettings(tts_enabled=True)
        assert s.tts_enabled is True
