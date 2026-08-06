"""What may and may not be mistaken for a spinnable PokéStop.

Every rule here was written after something on a real map screen was tapped by mistake, so
each test names the thing it keeps out rather than just asserting a count.
"""
import os
import sys
import threading
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from avc.catch import CatchConfig, CatchRoutine, CatchStats  # noqa: E402
from avc.spin import SpinRoutine  # noqa: E402
from avc.vision import find_pokestops  # noqa: E402

SCREEN = (1220, 2712)
FEET = (610, 1750)
CIRCLE = (FEET[0] - 900, FEET[1] - 900, 1800, 1800)

# Measured off the live map: stop body vs. the water that shares its hue (see avc/vision.py).
STOP_BGR = (250, 60, 20)     # HSV ~ (112, 200, 250)
WATER_BGR = (188, 45, 15)    # same hue, value 188 — the whole difference is brightness


def _map(fill=(40, 25, 20)):
    """A night-map background: dark, blue-ish, nothing tappable on it."""
    return np.full((SCREEN[1], SCREEN[0], 3), fill, np.uint8)


def _blob(img, cx, cy, w, h, colour=STOP_BGR):
    cv2.rectangle(img, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), colour, -1)
    return img


class DetectorTests(unittest.TestCase):
    def test_a_stop_body_inside_the_circle_is_found(self):
        frame = _blob(_map(), 800, 1600, 150, 170)

        found = find_pokestops(frame, region=CIRCLE)

        self.assertEqual(1, len(found))
        self.assertAlmostEqual(800, found[0].center[0], delta=12)
        self.assertAlmostEqual(1600, found[0].center[1], delta=12)

    def test_water_is_not_a_stop(self):
        """Lakes carry the same hue and dwarf any stop, so without the brightness floor the
        nearest 'stop' on a coastal map is the sea."""
        frame = _blob(_map(), 800, 1600, 300, 220, colour=WATER_BGR)

        self.assertEqual([], find_pokestops(frame, region=CIRCLE))

    def test_a_ring_glint_never_outranks_the_body_it_came_off(self):
        """The spin rings throw off bright-blue fragments beside the body, and once the shape
        rules are loose enough to accept a spinning cube they cannot be excluded on looks. What
        keeps the tap on the stop is that the body is always the bigger of the two — ranking by
        distance instead put the tap 140 px to the side, on bare map."""
        frame = _map()
        _blob(frame, 800, 1600, 150, 170)          # the body
        _blob(frame, 940, 1620, 60, 60)            # a glint beside it, nearer the avatar

        found = find_pokestops(frame, region=CIRCLE)

        self.assertAlmostEqual(800, found[0].center[0], delta=12)

    def test_a_wide_hud_pill_is_not_a_stop(self):
        """The right-hand icon rail and PGSharp's menu rows are blue and long. One tap that
        strayed onto the rail opened a full-screen map view."""
        frame = _blob(_map(), 800, 1600, 360, 80)

        self.assertEqual([], find_pokestops(frame, region=CIRCLE))

    def test_a_cube_caught_mid_spin_is_still_a_stop(self):
        """The cube turns continuously, so its outline swings between taller-than-wide and
        wider-than-tall. Measured 0.5 to 1.6 across real frames; anything tighter drops the
        stop for half of its own rotation."""
        for w, h in ((90, 190), (190, 90)):
            with self.subTest(shape=(w, h)):
                self.assertEqual(1, len(find_pokestops(_blob(_map(), 800, 1600, w, h),
                                                       region=CIRCLE)))

    def test_a_stop_outside_the_circle_is_ignored(self):
        frame = _blob(_map(), 800, 300, 150, 170)   # far up the screen, out of reach

        self.assertEqual([], find_pokestops(frame, region=CIRCLE))

    def test_the_search_area_is_the_ellipse_not_the_box(self):
        """A corner of the box is where the HUD lives; only the inscribed circle counts."""
        cx, cy, w, h = CIRCLE
        frame = _blob(_map(), cx + 120, cy + 120, 150, 170)   # inside the box, outside the circle

        self.assertEqual([], find_pokestops(frame, region=CIRCLE))

    def test_the_biggest_stop_comes_first(self):
        """Size, not distance: a glint sitting closer than the body it belongs to must never
        outrank it, and the shape rules alone cannot tell the two apart once they are loose
        enough to accept a spinning cube."""
        frame = _map()
        _blob(frame, FEET[0] + 250, FEET[1] - 500, 200, 220)   # a big one, further away
        _blob(frame, FEET[0] + 150, FEET[1] - 100, 100, 110)   # a small one, closer

        found = find_pokestops(frame, region=CIRCLE)

        self.assertEqual(2, len(found))
        self.assertAlmostEqual(FEET[0] + 250, found[0].center[0], delta=12)


class TapTests(unittest.TestCase):
    """spin_once picks a target and always gives the popup sweep a turn afterwards, because
    PGSharp answers every touch that reaches the map with a modal 'Stop AutoWalk?' dialog."""

    def _routine(self, frame, cls=CatchRoutine):
        routine = object.__new__(cls)
        routine.config = CatchConfig().scale_to(*SCREEN, 480)
        routine.stats = CatchStats()
        routine.stop_event = threading.Event()
        routine._spin_seen = []
        routine._trace = lambda *_a, **_k: None
        routine._interruptible_sleep = lambda _s: None
        routine.drained = []
        routine._drain_popups = lambda *_a: routine.drained.append(True) or False
        routine.device = SimpleNamespace(taps=[], screenshot=lambda **_k: frame)
        routine.device.tap = lambda x, y: routine.device.taps.append((x, y))
        return routine

    def test_a_tap_is_followed_by_a_popup_sweep(self):
        routine = self._routine(_blob(_map(), 800, 1600, 150, 170))

        self.assertTrue(routine.spin_once())

        self.assertEqual(1, len(routine.device.taps))
        self.assertEqual(1, routine.stats.spins)
        self.assertTrue(routine.drained)

    def test_the_same_stop_is_not_tapped_twice_in_a_row(self):
        """A stop that was out of range keeps its blue for good; without this the loop spends
        every cycle on it while the walk carries real ones past."""
        routine = self._routine(_blob(_map(), 800, 1600, 150, 170))

        self.assertTrue(routine.spin_once())
        self.assertFalse(routine.spin_once())
        self.assertEqual(1, len(routine.device.taps))

    def test_nothing_blue_means_no_tap_at_all(self):
        """Never tap a guessed spot: a miss lands on the map and stops the walk."""
        routine = self._routine(_map())

        self.assertFalse(routine.spin_once())
        self.assertEqual([], routine.device.taps)


class SpinModeTests(unittest.TestCase):
    def _routine(self, frame):
        routine = object.__new__(SpinRoutine)
        routine.config = CatchConfig().scale_to(*SCREEN, 480)
        routine.stats = CatchStats()
        routine.stop_event = threading.Event()
        routine._spin_seen = []
        routine._autowalk_active = False
        routine._walk_checks_left = SpinRoutine.WALK_CHECK_CYCLES
        routine._star_in = lambda _f: None
        routine._autowalk_row_in = lambda _f, _s: None
        routine._trace = lambda *_a, **_k: None
        routine._interruptible_sleep = lambda _s: None
        routine._ensure_calibrated = lambda: None
        routine._drain_popups = lambda *_a: False
        routine._in_encounter = lambda _f, strict=False: False
        # Nothing in this mode may reach the catch routine's AutoWalk path: it taps by a
        # remembered offset when the row icon is unreadable, and an unverified tap here can stop
        # the walk the whole mode depends on.
        routine.walks = []
        routine._try_autowalk = lambda: routine.walks.append("catch-path") or False
        routine.device = SimpleNamespace(taps=[], screenshot=lambda **_k: frame)
        routine.device.tap = lambda x, y: routine.device.taps.append((x, y))
        return routine

    def test_an_open_encounter_is_left_before_anything_else(self):
        """Go Plus can drop an encounter over the map; nothing below it can see a stop."""
        routine = self._routine(_blob(_map(), 800, 1600, 150, 170))
        routine._in_encounter = lambda _f, strict=False: True
        fled = []
        routine._leave_encounter = lambda: fled.append(True)

        self.assertFalse(routine.run_once())
        self.assertTrue(fled)
        self.assertEqual([], routine.device.taps)

    def test_a_stopped_walk_is_started_once_and_then_left_alone(self):
        routine = self._routine(_map())
        routine._star_in = lambda _f: (100, 100)
        routine._autowalk_row_in = lambda _f, _s: ((200, 400), True)   # showing '⊘'

        for _ in range(5):
            routine.run_once()

        self.assertEqual([(200, 400)], routine.device.taps)
        self.assertEqual([], routine.walks)

    def test_a_running_walk_is_never_tapped(self):
        """Tapping a row that is already walking raises "Stop AutoWalk?", and answering it
        CANCEL — which is the only safe answer — leaves the walk stopped."""
        routine = self._routine(_map())
        routine._star_in = lambda _f: (100, 100)
        routine._autowalk_row_in = lambda _f, _s: ((200, 400), False)

        for _ in range(5):
            routine.run_once()

        self.assertEqual([], routine.device.taps)

    def test_an_unreadable_row_is_retried_rather_than_guessed_at(self):
        """`_try_autowalk` aims by a remembered offset when the icon cannot be read. That is
        right for catching and wrong here: an unverified tap can stop a running walk. Unknown
        means try again — but not forever, since a collapsed menu never shows the row at all."""
        routine = self._routine(_map())
        routine._star_in = lambda _f: (100, 100)
        routine._autowalk_row_in = lambda _f, _s: None

        for _ in range(routine.WALK_CHECK_CYCLES + 3):
            routine.run_once()

        self.assertEqual([], routine.device.taps)
        self.assertEqual(0, routine._walk_checks_left)

    def test_a_stop_in_reach_is_spun_and_the_walk_left_alone(self):
        routine = self._routine(_blob(_map(), 800, 1600, 150, 170))

        self.assertTrue(routine.run_once())
        self.assertEqual([], routine.walks)

    def test_each_cycle_reports_only_what_it_did_itself(self):
        """run() reads last_event back to decide what to log, so a cycle must not inherit the
        verdict of the one before it."""
        routine = self._routine(_blob(_map(), 800, 1600, 150, 170))
        routine.stats.last_event = "spin"

        routine._spin_seen = [(1e18, 800, 1600)]     # already tapped: nothing to do this cycle
        self.assertFalse(routine.run_once())
        self.assertNotEqual("spin", routine.stats.last_event)


if __name__ == "__main__":
    unittest.main()
