"""Smoke tests for control widgets."""

import pytest

from rsvp.core.constants import WPM_DEFAULT, WPM_MAX, WPM_MIN, WPM_SLIDER_MAX, WPM_STEP

pytest.importorskip("pytestqt", reason="pytest-qt required for UI tests")


@pytest.fixture
def speed_control(qtbot):
    from rsvp.ui.controls import SpeedControl

    w = SpeedControl()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def playback_controls(qtbot):
    from rsvp.ui.controls import PlaybackControls

    w = PlaybackControls()
    qtbot.addWidget(w)
    return w


@pytest.fixture
def progress_widget(qtbot):
    from rsvp.ui.controls import ProgressWidget

    w = ProgressWidget()
    qtbot.addWidget(w)
    return w


class TestSpeedControl:
    def test_default_wpm(self, speed_control):
        assert speed_control.get_wpm() == WPM_DEFAULT

    def test_slider_bounds(self, speed_control):
        assert speed_control.slider.minimum() == WPM_MIN
        assert speed_control.slider.maximum() == WPM_SLIDER_MAX

    def test_spinbox_bounds(self, speed_control):
        assert speed_control.spinbox.minimum() == WPM_MIN
        assert speed_control.spinbox.maximum() == WPM_MAX

    def test_set_wpm_emits_signal(self, speed_control, qtbot):
        with qtbot.waitSignal(speed_control.wpm_changed, timeout=500) as sig:
            speed_control.set_wpm(500)
        assert sig.args == [500]

    def test_set_wpm_above_slider_max_clamps_slider(self, speed_control):
        speed_control.set_wpm(WPM_MAX)
        assert speed_control.spinbox.value() == WPM_MAX
        assert speed_control.slider.value() == WPM_SLIDER_MAX

    def test_increase_button_steps_by_wpm_step(self, speed_control, qtbot):
        speed_control.set_wpm(WPM_DEFAULT)
        with qtbot.waitSignal(speed_control.wpm_changed, timeout=500):
            speed_control.increase_btn.click()
        assert speed_control.get_wpm() == WPM_DEFAULT + WPM_STEP

    def test_decrease_button_steps_by_wpm_step(self, speed_control, qtbot):
        speed_control.set_wpm(WPM_DEFAULT)
        with qtbot.waitSignal(speed_control.wpm_changed, timeout=500):
            speed_control.decrease_btn.click()
        assert speed_control.get_wpm() == WPM_DEFAULT - WPM_STEP

    def test_decrease_clamps_at_min(self, speed_control):
        speed_control.set_wpm(WPM_MIN)
        speed_control.decrease_btn.click()
        assert speed_control.get_wpm() == WPM_MIN

    def test_increase_clamps_at_max(self, speed_control):
        speed_control.set_wpm(WPM_MAX)
        speed_control.increase_btn.click()
        assert speed_control.get_wpm() == WPM_MAX


class TestPlaybackControls:
    def test_instantiates(self, playback_controls):
        assert playback_controls is not None

    def test_play_pause_button_emits_play_when_paused(self, playback_controls, qtbot):
        playback_controls.set_playing(False)
        with qtbot.waitSignal(playback_controls.play_clicked, timeout=500):
            playback_controls.play_pause_btn.click()

    def test_play_pause_button_emits_pause_when_playing(self, playback_controls, qtbot):
        playback_controls.set_playing(True)
        with qtbot.waitSignal(playback_controls.pause_clicked, timeout=500):
            playback_controls.play_pause_btn.click()

    def test_stop_button_emits_stop(self, playback_controls, qtbot):
        with qtbot.waitSignal(playback_controls.stop_clicked, timeout=500):
            playback_controls.stop_btn.click()

    def test_skip_forward_emits(self, playback_controls, qtbot):
        with qtbot.waitSignal(playback_controls.skip_forward_clicked, timeout=500):
            playback_controls.skip_fwd_btn.click()

    def test_skip_backward_emits(self, playback_controls, qtbot):
        with qtbot.waitSignal(playback_controls.skip_backward_clicked, timeout=500):
            playback_controls.skip_back_btn.click()

    def test_prev_sentence_emits(self, playback_controls, qtbot):
        with qtbot.waitSignal(playback_controls.prev_sentence_clicked, timeout=500):
            playback_controls.prev_sentence_btn.click()

    def test_next_sentence_emits(self, playback_controls, qtbot):
        with qtbot.waitSignal(playback_controls.next_sentence_clicked, timeout=500):
            playback_controls.next_sentence_btn.click()


class TestProgressWidget:
    def test_initial_state(self, progress_widget):
        assert progress_widget.slider.value() == 0
        assert progress_widget.label.text() == "0 / 0 words"

    def test_update_progress_sets_label(self, progress_widget):
        progress_widget.update_progress(50.0, 100, 200, 60.0)
        assert progress_widget.label.text() == "100 / 200 words"

    def test_update_progress_shows_time_minutes(self, progress_widget):
        progress_widget.update_progress(50.0, 100, 200, 125.0)
        assert "2m" in progress_widget.time_label.text()
        assert "5s" in progress_widget.time_label.text()

    def test_update_progress_shows_time_seconds_only(self, progress_widget):
        progress_widget.update_progress(50.0, 100, 200, 30.0)
        assert progress_widget.time_label.text() == "30s left"

    def test_update_progress_clears_time_when_zero(self, progress_widget):
        progress_widget.update_progress(100.0, 200, 200, 0.0)
        assert progress_widget.time_label.text() == ""

    def test_update_progress_moves_slider(self, progress_widget):
        progress_widget.update_progress(50.0, 100, 200, 60.0)
        assert progress_widget.slider.value() == 500
