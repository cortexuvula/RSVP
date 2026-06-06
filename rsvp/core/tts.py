"""Text-to-speech integration: speaks each engine word via pyttsx3."""

import logging
from typing import Protocol

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


class TTSController:
    """Speaks each engine word via the TTS driver, paced to the display WPM.

    Subscribes to RSVPEngine.word_changed and speaks each new word. The
    call is synchronous (say + run_and_wait) — the main thread blocks for
    the duration of each word, which naturally paces the display to the
    TTS rate. The engine's QTimer is the wakeup mechanism; TTS is the
    bottleneck.
    """

    def __init__(self, engine: RSVPEngine, driver: TTSDriver | None = None) -> None:
        self._engine = engine
        self._driver: TTSDriver = driver if driver is not None else NullDriver()
        self._enabled: bool = False
        engine.word_changed.connect(self._on_word_changed)
        engine.state_changed.connect(self._on_state_changed)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """User toggled TTS in Settings. Stops any current utterance if disabling."""
        self._enabled = enabled
        if not enabled:
            self._driver.stop()

    def shutdown(self) -> None:
        """Interrupt any in-progress utterance. Called by MainWindow.closeEvent."""
        self._driver.stop()

    def _on_word_changed(self, word: Word | None) -> None:
        if not self._enabled or word is None:
            return
        self._driver.say(word.text)
        self._driver.run_and_wait()

    def _on_state_changed(self) -> None:
        if not self._enabled:
            return
        if not self._engine.is_playing:
            self._driver.stop()
