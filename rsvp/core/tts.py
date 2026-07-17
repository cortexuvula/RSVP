"""Text-to-speech integration: speaks each engine word via pyttsx3."""

import logging
from typing import Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from rsvp.core.rsvp_engine import RSVPEngine
from rsvp.core.text_processor import Word

logger = logging.getLogger(__name__)


class TTSDriver(Protocol):
    """Protocol for TTS drivers. Production = Pyttsx3Driver, tests = NullDriver."""

    def say(self, text: str) -> None: ...
    def run_and_wait(self) -> None: ...
    def stop(self) -> None: ...


class NullDriver:
    """No-op driver. Used in tests and as a fallback when pyttsx3 is unavailable."""

    def say(self, text: str) -> None:
        pass

    def run_and_wait(self) -> None:
        pass

    def stop(self) -> None:
        pass


class Pyttsx3Driver:
    """Wraps pyttsx3.init() / say() / runAndWait() / stop()."""

    def __init__(self) -> None:
        import pyttsx3  # imported here so the dep is optional

        self._engine = pyttsx3.init()

    def say(self, text: str) -> None:
        self._engine.say(text)

    def run_and_wait(self) -> None:
        self._engine.runAndWait()

    def stop(self) -> None:
        self._engine.stop()


def create_tts_driver() -> TTSDriver:
    """Create a Pyttsx3Driver if pyttsx3 is importable, else NullDriver.

    Also returns NullDriver if pyttsx3.init() fails (e.g., no TTS engine
    installed on the system).
    """
    try:
        return Pyttsx3Driver()
    except Exception as e:  # noqa: BLE001  (pyttsx3 raises many things, all fall through to NullDriver)
        logger.warning("Failed to initialize pyttsx3; TTS will be a no-op: %s", e)
        return NullDriver()


class _TTSWorker(QObject):
    """Worker that runs TTS playback in a background thread.

    Signals
    -------
    finished – emitted after a word has been spoken successfully.
    error    – emitted with a message if playback raises.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, driver: TTSDriver, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._driver = driver

    @pyqtSlot(str)
    def speak(self, text: str) -> None:
        """Speak *text* using the driver. Runs in the worker thread."""
        try:
            self._driver.say(text)
            self._driver.run_and_wait()
            self.finished.emit()
        except Exception as e:
            logger.warning("TTS playback error: %s", e)
            self.error.emit(str(e))

    @pyqtSlot()
    def stop(self) -> None:
        """Stop the driver."""
        self._driver.stop()


class TTSController(QObject):
    """Speaks each engine word via the TTS driver in a background QThread.

    Subscribes to RSVPEngine.word_changed and speaks each new word.
    Playback (``say`` + ``run_and_wait``) happens inside a ``_TTSWorker``
    that lives on a dedicated ``QThread`` so the Qt event loop is never
    blocked.
    """

    # Internal signal used to dispatch work to the worker thread.
    _speak_requested = pyqtSignal(str)

    def __init__(self, engine: RSVPEngine, driver: TTSDriver | None = None) -> None:
        super().__init__()
        self._engine = engine
        self._driver: TTSDriver = driver if driver is not None else NullDriver()
        self._enabled: bool = False

        # Background thread for TTS playback
        self._thread = QThread()
        self._worker = _TTSWorker(self._driver)
        self._worker.moveToThread(self._thread)

        # Internal signal: queued connection so speak() runs in the worker thread
        self._speak_requested.connect(self._worker.speak)

        self._worker.finished.connect(self._on_tts_finished)
        self._worker.error.connect(self._on_tts_error)

        self._thread.start()

        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """User toggled TTS in Settings. Stops any current utterance if disabling."""
        self._enabled = enabled
        if not enabled:
            # Call stop directly on the worker. A queued _stop_requested signal
            # would not be delivered until the worker's event loop runs again,
            # but the worker blocks inside pyttsx3.runAndWait() with its loop
            # stalled — so the signal can never interrupt an in-progress
            # utterance. pyttsx3.stop() is designed to be called from another
            # thread to unblock runAndWait(); the same approach is already used
            # in shutdown().
            self._worker.stop()

    def shutdown(self) -> None:
        """Interrupt any in-progress utterance and stop the background thread."""
        # Call stop directly on the worker since the queued signal may not
        # be processed before thread.quit() exits the event loop.
        self._worker.stop()
        self._thread.quit()
        self._thread.wait()

    @pyqtSlot(object)
    def _on_word_changed(self, word: Word | None) -> None:
        if not self._enabled or word is None:
            return
        self._speak_requested.emit(word.text)

    @pyqtSlot()
    def _on_state_changed(self) -> None:
        if not self._enabled:
            return
        if not self._engine.is_playing:
            # See set_enabled(): direct call is required because the worker
            # blocks inside runAndWait() and cannot process a queued signal.
            self._worker.stop()

    def _on_tts_finished(self) -> None:
        """Word finished speaking – no-op (engine timer paces the next word)."""

    def _on_tts_error(self, error_msg: str) -> None:
        logger.warning("TTS error: %s", error_msg)
