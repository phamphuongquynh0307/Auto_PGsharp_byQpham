"""The no-ball refill flow finds and starts only a disconnected Go Plus button."""
import threading
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from avc.catch import CatchRoutine
from avc.vision import find_disconnected_goplus


def disconnected_button(y=490):
    frame = np.full((2712, 1220, 3), (150, 105, 75), dtype=np.uint8)
    centre = (1115, y)
    # Same stable colour/geometry as the game's disconnected accessory control.
    cv2.ellipse(frame, centre, (52, 52), 180, 0, 180, (105, 115, 185), -1)
    cv2.ellipse(frame, centre, (52, 52), 0, 0, 180, (180, 155, 115), -1)
    cv2.circle(frame, centre, 20, (70, 85, 95), -1)
    return frame, centre


class GoPlusVisionTests(unittest.TestCase):
    def test_finds_disconnected_button_even_when_event_rows_move_it(self):
        for y in (350, 490, 720):
            with self.subTest(y=y):
                frame, expected = disconnected_button(y)
                found = find_disconnected_goplus(frame)
                self.assertIsNotNone(found)
                self.assertLessEqual(abs(found[0] - expected[0]), 3)
                # Any point inside the 40px dark centre is a safe button tap; the red cap's
                # antialiasing moves its contour edge a few pixels between renderers.
                self.assertLessEqual(abs(found[1] - expected[1]), 10)

    def test_connected_green_button_is_not_returned(self):
        frame = np.full((2712, 1220, 3), (150, 105, 75), dtype=np.uint8)
        cv2.circle(frame, (1115, 490), 52, (90, 190, 90), -1)
        cv2.circle(frame, (1115, 490), 20, (70, 85, 95), -1)

        self.assertIsNone(find_disconnected_goplus(frame))

    def test_smaller_red_event_icon_is_not_returned(self):
        frame = np.full((2712, 1220, 3), (150, 105, 75), dtype=np.uint8)
        cv2.circle(frame, (1115, 320), 22, (80, 80, 200), -1)

        self.assertIsNone(find_disconnected_goplus(frame))


class FakeDevice:
    def __init__(self):
        self.taps = []

    def screenshot(self, **_kwargs):
        return object()

    def tap(self, *point):
        self.taps.append(point)


class NoBallsRecoveryTests(unittest.TestCase):
    def test_a_visible_running_autowalk_row_is_not_tapped_off(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            autowalk_offset_x=100,
            autowalk_offset_y=300,
        )
        routine.device = FakeDevice()
        routine._in_encounter = lambda _frame: False
        routine._star_in = lambda _frame: (100, 100)
        routine._autowalk_row_in = lambda _frame, _star: ((200, 400), False)
        routine._autowalk_active = False
        routine._aw_offset = None
        routine._trace = lambda *_args: None

        tapped = routine._try_autowalk()

        self.assertFalse(tapped)
        self.assertTrue(routine._autowalk_active)
        self.assertEqual([], routine.device.taps)

    def test_no_ball_flow_starts_goplus_after_autowalk(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            no_balls_pause=10.0,
            no_balls_walk_interval=0.0,
            goplus_after_autowalk_wait=0.0,
            spin_on_no_balls=False,
            start_goplus_on_no_balls=True,
            quick_catch=False,
        )
        routine.stop_event = threading.Event()
        routine.stats = SimpleNamespace(last_event="no_balls")
        routine._wait_if_paused = lambda: None
        routine._drain_popups = lambda: False
        routine._interruptible_sleep = lambda _seconds: None
        events = []

        def autowalk():
            events.append("autowalk")
            return True

        def goplus():
            events.append("goplus")
            routine.stop_event.set()
            return True

        routine._try_autowalk = autowalk
        routine._try_start_goplus = goplus
        callbacks = []

        routine._wait_no_balls(lambda stats, threw: callbacks.append((stats.last_event, threw)))

        self.assertEqual(["autowalk", "goplus"], events)
        self.assertEqual([("goplus_started", False)], callbacks)

    def test_quick_or_disabled_catching_never_touches_goplus(self):
        for enabled, quick in ((True, True), (False, False)):
            with self.subTest(enabled=enabled, quick=quick):
                routine = object.__new__(CatchRoutine)
                routine.config = SimpleNamespace(
                    no_balls_pause=10.0,
                    no_balls_walk_interval=0.0,
                    goplus_after_autowalk_wait=0.0,
                    spin_on_no_balls=False,
                    start_goplus_on_no_balls=enabled,
                    quick_catch=quick,
                )
                routine.stop_event = threading.Event()
                routine.stats = SimpleNamespace(last_event="no_balls")
                routine._wait_if_paused = lambda: None
                routine._drain_popups = lambda: False
                routine._interruptible_sleep = lambda _seconds: None
                events = []

                def autowalk():
                    events.append("autowalk")
                    routine.stop_event.set()
                    return True

                routine._try_autowalk = autowalk
                routine._try_start_goplus = lambda: events.append("goplus") or True

                routine._wait_no_balls()

                self.assertEqual(["autowalk"], events)


if __name__ == "__main__":
    unittest.main()
