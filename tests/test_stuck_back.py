"""The stall watchdog: unrecognisable screen for long enough -> Android BACK.

Every popup handler recognises its dialog by a template cropped from one phone running one
PGSharp/Pokemon GO build, so a build that draws a modal differently stalls the run until a
human notices. BACK needs no template, no coordinate and no language — but it is a blind key
press, so what is guarded here is mostly when it must NOT fire.
"""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchConfig, CatchRoutine


def _routine(**overrides):
    config = dict(popup_threshold=0.7, dialog_region=(150, 1150, 950, 500),
                  cancel_btn_region=(620, 1480, 310, 220), stuck_back=True,
                  stuck_back_after=12.0, stuck_back_interval=8.0)
    config.update(overrides)
    routine = object.__new__(CatchRoutine)
    routine.config = SimpleNamespace(**config)
    routine.backs = []
    routine.taps = []
    routine.device = SimpleNamespace(back=lambda: routine.backs.append(1),
                                     tap=lambda *xy: routine.taps.append(xy))
    routine.stats = SimpleNamespace(last_event="")
    routine.stop_event = threading.Event()
    routine._popup_block_until = 0.0
    routine._popup_scales = (1.0,)
    routine._game_popup_scales = (1.0,)
    routine._stuck_since = 0.0
    routine._stuck_back_at = 0.0
    routine._stuck_checked_at = 0.0
    routine._on_stuck = None
    for name in ("_cancel_btn", "_popup_weather", "_popup_speed", "_maybe_later",
                 "_popup_autowalk", "_claim_rewards", "_caught_ok", "_check_btn",
                 "_close_btn", "_close_btn_blue", "_close_btn_white"):
        setattr(routine, name, None)
    routine._ball_in = lambda _frame, **_kw: None
    routine._is_pokestop_screen = lambda _frame: False
    routine._in_encounter = lambda _frame, **_kw: False
    routine._bar_visible = lambda _frame: False
    routine._trace = lambda *_args, **_kw: None
    return routine


class StuckBackTests(unittest.TestCase):
    def _handle(self, routine, at):
        frame = np.zeros((2712, 1220, 3), dtype=np.uint8)
        with patch("avc.catch.find_dialog_buttons", return_value=[]), \
             patch("avc.catch.time.monotonic", return_value=at):
            return routine._handle_popups(frame)

    def test_back_is_not_pressed_before_the_screen_has_been_strange_long_enough(self):
        routine = _routine()
        self.assertFalse(self._handle(routine, 1000.0))
        self.assertFalse(self._handle(routine, 1005.0))
        self.assertEqual([], routine.backs)

    def test_back_fires_once_the_screen_has_been_unreadable_for_the_full_window(self):
        routine = _routine()
        self._handle(routine, 1000.0)

        self.assertTrue(self._handle(routine, 1013.0))
        self.assertEqual(1, len(routine.backs))

    def test_an_encounter_never_gets_a_back_press(self):
        """BACK inside an encounter abandons the Pokemon — worse than staying stuck."""
        routine = _routine()
        routine._in_encounter = lambda _frame, **_kw: True

        for at in (1000.0, 1013.0, 1030.0, 1060.0):
            self._handle(routine, at)
        self.assertEqual([], routine.backs)

    def test_the_map_never_gets_a_back_press(self):
        """Nearby bar in view means the map is up, and BACK there raises the quit prompt."""
        routine = _routine()
        routine._bar_visible = lambda _frame: True

        for at in (1000.0, 1013.0, 1030.0, 1060.0):
            self._handle(routine, at)
        self.assertEqual([], routine.backs)

    def test_the_timer_restarts_the_moment_the_screen_is_readable_again(self):
        routine = _routine()
        self._handle(routine, 1000.0)
        routine._bar_visible = lambda _frame: True
        self._handle(routine, 1006.0)
        routine._bar_visible = lambda _frame: False
        self._handle(routine, 1007.0)

        self.assertFalse(self._handle(routine, 1015.0))
        self.assertEqual([], routine.backs)

    def test_presses_are_rate_limited_so_a_dead_screen_is_not_hammered(self):
        routine = _routine()
        self._handle(routine, 1000.0)
        self.assertTrue(self._handle(routine, 1013.0))
        self._handle(routine, 1014.0)
        self.assertFalse(self._handle(routine, 1018.0))
        self.assertEqual(1, len(routine.backs))

    def test_the_switch_turns_the_whole_thing_off(self):
        routine = _routine(stuck_back=False)
        routine._bar_visible = lambda _frame: self.fail("must not be consulted")

        for at in (1000.0, 1020.0, 1040.0):
            self._handle(routine, at)
        self.assertEqual([], routine.backs)

    def test_the_screen_is_sampled_about_once_a_second_not_every_poll(self):
        routine = _routine()
        reads = []
        routine._bar_visible = lambda _frame: reads.append(1) or False

        for tick in range(10):
            self._handle(routine, 1000.0 + tick * 0.08)
        self.assertEqual(1, len(reads))

    def test_the_gui_hook_receives_the_frame_that_could_not_be_read(self):
        routine = _routine()
        seen = []
        routine._on_stuck = seen.append
        self._handle(routine, 1000.0)
        self._handle(routine, 1013.0)

        self.assertEqual(1, len(seen))
        self.assertEqual((2712, 1220, 3), seen[0].shape)

    def test_a_failing_hook_cannot_end_the_run(self):
        routine = _routine()

        def boom(_frame):
            raise RuntimeError("disk full")

        routine._on_stuck = boom
        self._handle(routine, 1000.0)
        self.assertTrue(self._handle(routine, 1013.0))


class StuckBackDefaultTests(unittest.TestCase):
    def test_the_watchdog_is_on_out_of_the_box(self):
        config = CatchConfig()
        self.assertTrue(config.stuck_back)
        self.assertGreaterEqual(config.stuck_back_after, 10.0)


if __name__ == "__main__":
    unittest.main()
