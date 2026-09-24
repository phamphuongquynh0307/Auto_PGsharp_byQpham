"""Out-of-balls detection supports both the old x0 badge and the missing selector UI."""
import threading
import unittest
import unittest.mock
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from avc.catch import (
    CURRENT_OUT_OF_BALLS_REGION, LEGACY_OUT_OF_BALLS_REGION, CatchConfig, CatchRoutine,
)
from avc.vision import find_ball_picker_choices, find_throw_ball_hub, master_ball_at


class FrameDevice:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.releases = 0

    def screenshot(self, **_kwargs):
        return next(self.frames)

    def release_control_pointers(self):
        self.releases += 1


def bare_routine(frames):
    routine = object.__new__(CatchRoutine)
    routine.config = SimpleNamespace(
        no_balls_missing_frames=3,
    )
    routine.device = FrameDevice(frames)
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._wait_if_paused = lambda: None
    routine._in_encounter = lambda frame, **_kwargs: frame != "map"
    routine._is_out_of_balls = lambda frame: frame == "x0"
    routine._ball_ready = lambda frame: frame == "ball"
    routine._master_ball_visible = lambda _frame: False
    # The live empty-bag screen still contains the bottom-right selector button. Only ``ball``
    # models the large throwable ball resting at the throw point.
    routine._ball_selector_present = lambda frame: frame in ("selector", "ball")
    return routine


GRASS = (60, 120, 60)
BALL_CENTRE = (610, 2615)   # base-resolution centre of the throwable ball
BALL_RADIUS = 225


def encounter_frame(dome=None, background=GRASS, center=BALL_CENTRE):
    """A base-resolution encounter screen, with the throwable ball drawn when `dome` is given.

    `dome` is the ball type's colour (BGR): red = Poké, blue = Great, near-black = Ultra. Only
    the dome changes between types — the white belly, the black band and the light centre hub
    are the same ball to ball, which is what the readiness test is supposed to key on.
    """
    frame = np.full((2712, 1220, 3), background, dtype=np.uint8)
    if dome is None:
        return frame                                     # empty bag: no selector at all
    cv2.circle(frame, center, BALL_RADIUS, (245, 245, 245), -1)     # white lower half
    cv2.ellipse(frame, center, (BALL_RADIUS, BALL_RADIUS), 0, 180, 360, dome, -1)
    cv2.line(frame, (center[0] - BALL_RADIUS, center[1]),
             (center[0] + BALL_RADIUS, center[1]), (18, 18, 18), 26)
    cv2.circle(frame, center, 80, (18, 18, 18), -1)                 # black band
    cv2.circle(frame, center, 55, (215, 215, 215), -1)              # light hub
    return frame


def ball_reader():
    routine = object.__new__(CatchRoutine)
    routine.config = CatchConfig()
    return routine


class AnyBallTypeIsThrowableTests(unittest.TestCase):
    """Running out of one ball type is not running out of balls: the game switches type and
    keeps the selector up, so every type has to read as ready."""

    def test_every_ball_type_reads_as_ready(self):
        for name, dome in (("poke", (30, 30, 225)), ("great", (200, 90, 40)),
                           ("ultra", (25, 25, 25)), ("master", (170, 40, 130))):
            with self.subTest(ball=name):
                self.assertTrue(ball_reader()._ball_ready(encounter_frame(dome)))

    def test_master_ball_is_rejected_before_ready_state(self):
        frame = encounter_frame((170, 40, 130))
        routine = ball_reader()
        routine.stop_event = threading.Event()
        routine.pause_event = threading.Event()
        routine._wait_if_paused = lambda: None
        routine._in_encounter = lambda _frame, **_kwargs: True
        routine._is_out_of_balls = lambda _frame: False
        routine.device = FrameDevice([frame])

        self.assertTrue(routine._master_ball_visible(frame))
        self.assertEqual("empty", routine._wait_for_ball_state(0.0))

    def test_master_ball_appearing_immediately_before_throw_cancels_it(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(max_throws_per_encounter=1,
                                         encounter_touch_delay_ms=0,
                                         no_balls_missing_timeout=0)
        routine.stop_event = threading.Event()
        routine.stats = SimpleNamespace(throws=0)
        routine.device = SimpleNamespace(screenshot=lambda **_kwargs: "master")
        routine._wait_for_ball_state = lambda _timeout: "ready"
        routine._throw_point_from_hub = lambda _hub: (610, 2380)
        routine._in_encounter = lambda _frame: True
        routine._master_ball_visible = lambda _frame: True
        routine._is_out_of_balls = lambda _frame: False
        routine._flag_no_balls = lambda: setattr(routine, "stopped_for_balls", True)

        self.assertFalse(routine._run_encounter((610, 2380)))
        self.assertTrue(routine.stopped_for_balls)
        self.assertEqual(0, routine.stats.throws)

    def test_quick_throw_releases_contacts_before_closing_control(self):
        events = []
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(berry_start=(100, 2300), berry_end=(300, 2300),
                                         quick_flick_ms=100, post_throw_wait_ms=0,
                                         flee_taps=1, flee_xy=(120, 170))
        routine.stop_event = threading.Event()
        routine._throw_vector = lambda _xy: ((610, 2380), (610, 1680))
        routine._interruptible_sleep = lambda _seconds: None
        routine.device = SimpleNamespace(
            quick_catch_throw=lambda *_args: events.append("throw"),
            release_control_pointers=lambda: events.append("release"),
            close_control=lambda: events.append("close"),
            adb_tap=lambda *_args: events.append("flee"),
        )

        routine._quick_throw((610, 2380))
        self.assertEqual(["throw", "release", "close", "flee"], events)

    def test_first_throw_uses_fallback_when_berry_is_visible_but_hub_is_missing(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(max_throws_per_encounter=1,
                                         encounter_touch_delay_ms=0,
                                         no_balls_missing_timeout=0,
                                         quick_catch=False, catch_timeout=1.0)
        routine.stop_event = threading.Event()
        routine.stats = SimpleNamespace(throws=0, encounters=0)
        screenshot = unittest.mock.Mock(return_value="missing")
        routine.device = SimpleNamespace(screenshot=screenshot)
        routine._in_encounter = lambda _frame: True
        routine._master_ball_visible = lambda _frame: False
        routine._is_out_of_balls = lambda _frame: False
        routine._ball_ready = lambda _frame: False
        routine._throw_point_from_hub = lambda _hub: (610, 2380)
        routine._throw = unittest.mock.Mock()
        routine._throw_outcome = lambda _timeout: "closed"
        routine._settle_after_encounter = lambda: None
        routine._trace = lambda *_args: None

        self.assertTrue(routine._run_encounter((610, 2380)))
        screenshot.assert_called_once_with(next_frame=True)
        routine._throw.assert_called_once_with((610, 2380))
        self.assertEqual(1, routine.stats.throws)

    def test_open_encounter_checks_remaining_ball_after_first_throw(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(max_throws_per_encounter=2,
                                         encounter_touch_delay_ms=0,
                                         no_balls_missing_timeout=0,
                                         quick_catch=False, catch_timeout=1.0)
        routine.stop_event = threading.Event()
        routine.stats = SimpleNamespace(throws=0)
        routine.device = SimpleNamespace(screenshot=lambda **_kwargs: "encounter")
        routine._in_encounter = lambda _frame: True
        routine._master_ball_visible = lambda _frame: False
        routine._is_out_of_balls = lambda _frame: False
        routine._ball_ready = lambda _frame: False
        routine._throw_point_from_hub = lambda _hub: (610, 2380)
        routine._throw = unittest.mock.Mock()
        routine._throw_outcome = lambda _timeout: "timeout"
        routine._wait_for_ball_state = unittest.mock.Mock(return_value="empty")
        routine._flag_no_balls = lambda: setattr(routine, "stopped_for_balls", True)
        routine._trace = lambda *_args: None

        self.assertTrue(routine._run_encounter((610, 2380)))
        routine._throw.assert_called_once()
        routine._wait_for_ball_state.assert_called_once()
        self.assertTrue(routine.stopped_for_balls)

    def test_missing_selector_is_not_ready(self):
        for name, background in (("grass", GRASS), ("water", (170, 120, 40)),
                                 ("night", (25, 30, 25)), ("snow", (235, 235, 235))):
            with self.subTest(background=name):
                self.assertFalse(ball_reader()._ball_ready(encounter_frame(background=background)))

    def test_ball_in_flight_is_not_ready(self):
        frame = encounter_frame((30, 30, 225))
        cv2.circle(frame, BALL_CENTRE, BALL_RADIUS + 8, GRASS, -1)   # ball has left the spot
        cv2.circle(frame, (640, 1500), 70, (30, 30, 225), -1)        # ...and is mid-throw

        self.assertFalse(ball_reader()._ball_ready(frame))

    def test_ready_survives_a_scaled_down_device(self):
        frame = cv2.resize(encounter_frame((200, 90, 40)), None, fx=0.66, fy=0.66,
                           interpolation=cv2.INTER_AREA)
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig().scale_to(frame.shape[1], frame.shape[0], None,
                                                game_scale=0.66)

        self.assertTrue(routine._ball_ready(frame))

    def test_hub_detector_follows_a_shifted_ball_instead_of_a_fixed_coordinate(self):
        shifted = (700, 2570)
        frame = encounter_frame((30, 30, 225), center=shifted)

        found = find_throw_ball_hub(frame)

        self.assertIsNotNone(found)
        self.assertLessEqual(abs(found[0] - shifted[0]), 2)
        self.assertLessEqual(abs(found[1] - shifted[1]), 2)

    def test_lifted_ball_hub_is_not_a_resting_throw_ball(self):
        routine = ball_reader()
        routine._enc_berry_at = (147, 2467)
        lifted = encounter_frame((30, 30, 225), center=(655, 2470))
        self.assertIsNotNone(find_throw_ball_hub(lifted))
        self.assertFalse(routine._ball_ready(lifted))

    def test_missing_ball_clears_previous_throw_position(self):
        routine = ball_reader()
        shifted = (700, 2570)
        self.assertIsNotNone(routine._throw_hub_in(
            encounter_frame((30, 30, 225), center=shifted)))
        self.assertIsNone(routine._throw_hub_in(encounter_frame()))
        self.assertIsNone(routine._throw_hub_at)

    def test_detected_hub_moves_the_throw_start_but_manual_alignment_still_wins(self):
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig()
        self.assertEqual((700, 2335), routine._throw_point_from_hub((700, 2570)))

        routine.config.force_ball = True
        routine.config.ball_fallback = (640, 2300)
        self.assertEqual((640, 2300), routine._throw_point_from_hub((700, 2570)))


class MissingBallDetectionTests(unittest.TestCase):
    def test_one_dropped_hub_frame_does_not_mean_breakout(self):
        routine = object.__new__(CatchRoutine)
        routine.stop_event = threading.Event()
        routine.pause_event = threading.Event()
        routine._wait_if_paused = lambda: None
        screenshot = unittest.mock.Mock(side_effect=["ready", "missing", "ready",
                                                 "missing", "missing", "ready"])
        routine.device = SimpleNamespace(screenshot=screenshot)
        routine._in_encounter = lambda _frame, **_kwargs: True
        routine._ball_ready = lambda frame: frame == "ready"

        self.assertEqual("breakout", routine._throw_outcome(5.0))
        self.assertEqual(6, screenshot.call_count)

    def test_three_missing_frames_in_an_open_encounter_mean_empty(self):
        routine = bare_routine(["missing", "missing", "missing", "missing"])

        self.assertEqual("empty", routine._wait_for_ball_state(0.0))

    def test_ball_appearing_during_confirmation_is_ready(self):
        routine = bare_routine(["missing", "missing", "ball"])

        self.assertEqual("ready", routine._wait_for_ball_state(0.0))

    def test_visible_selector_without_a_throwable_ball_is_still_empty(self):
        routine = bare_routine(["selector", "selector", "selector", "selector"])

        self.assertEqual("empty", routine._wait_for_ball_state(0.0))
        self.assertEqual(1, routine.device.releases)

    def test_held_ball_can_snap_back_after_pointer_release(self):
        routine = bare_routine(["selector", "ball"])

        self.assertEqual("ready", routine._wait_for_ball_state(0.0))
        self.assertEqual(1, routine.device.releases)

    def test_encounter_closing_during_confirmation_is_not_empty(self):
        routine = bare_routine(["missing", "map"])

        self.assertEqual("closed", routine._wait_for_ball_state(0.0))

    def test_legacy_x0_badge_still_wins_immediately(self):
        routine = bare_routine(["x0"])

        self.assertEqual("empty", routine._wait_for_ball_state(99.0))

    def test_fresh_confirmation_can_reject_smeared_stream_frames(self):
        routine = bare_routine(["missing", "missing", "missing", "ball"])

        self.assertEqual("ready", routine._wait_for_ball_state(0.0))

    def test_confirmed_bare_throw_spot_stops_without_opening_picker(self):
        routine = bare_routine(["missing", "missing", "missing", "missing"])

        self.assertEqual("empty", routine._wait_for_ball_state(0.0))

    def test_x0_badge_stops_without_opening_picker(self):
        routine = bare_routine(["x0"])

        self.assertEqual("empty", routine._wait_for_ball_state(99.0))


def picker_frame(balls=3, domes=None):
    """Base-resolution encounter with the ball picker sheet open, as measured on a live phone."""
    frame = np.full((2712, 1220, 3), GRASS, dtype=np.uint8)
    frame[2040:] = (208, 208, 206)                                   # light sheet
    for i in range(balls):
        px, py = 156 + 381 * i, 2359
        dome = domes[i] if domes else (40, 40, 220)
        cv2.circle(frame, (px + 72, py - 95), 80, dome, -1)  # ball sprite
        cv2.rectangle(frame, (px - 69, py - 34), (px + 69, py + 34), (120, 99, 38), -1)  # pill
        cv2.putText(frame, "x199", (px - 55, py + 14), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                    (244, 242, 237), 3)
    return frame


class BallPickerTests(unittest.TestCase):
    def test_user_master_only_screenshot_is_recognised(self):
        screenshot = cv2.imread(str(Path(__file__).parent / "fixtures" /
                                    "master_picker_only.png"))
        self.assertTrue(master_ball_at(screenshot, (70, 695), 30))

    def test_picker_offers_each_owned_type_left_to_right(self):
        choices = find_ball_picker_choices(picker_frame())

        self.assertEqual(3, len(choices))
        self.assertLessEqual(abs(choices[0][0] - 228), 3)
        self.assertLessEqual(abs(choices[0][1] - 2264), 3)
        self.assertEqual(sorted(choices), choices)

    def test_picker_follows_a_scaled_down_device(self):
        frame = cv2.resize(picker_frame(), None, fx=0.59, fy=0.59, interpolation=cv2.INTER_AREA)

        choices = find_ball_picker_choices(frame, scale=0.59)

        self.assertEqual(3, len(choices))
        self.assertLessEqual(abs(choices[0][0] - 228 * 0.59), 4)

    def test_no_picker_on_encounter_or_snow(self):
        for name, frame in (("encounter", encounter_frame((200, 90, 40))),
                            ("snow", encounter_frame(background=(235, 235, 235))),
                            ("empty sheet", picker_frame(balls=0))):
            with self.subTest(frame=name):
                self.assertEqual([], find_ball_picker_choices(frame))


class CurrentCountBadgeLocationTests(unittest.TestCase):
    def test_default_region_contains_the_right_side_x0_badge(self):
        config = CatchConfig()
        template = cv2.imread(config.out_of_balls_template, cv2.IMREAD_COLOR)
        self.assertIsNotNone(template)
        frame = np.zeros((2712, 1220, 3), dtype=np.uint8)
        x, y = 760, 2500
        height, width = template.shape[:2]
        frame[y:y + height, x:x + width] = template

        routine = object.__new__(CatchRoutine)
        routine.config = config
        routine._noball_tpl = template
        routine._scales = (1.0,)

        self.assertFalse(
            LEGACY_OUT_OF_BALLS_REGION[0]
            <= x
            < LEGACY_OUT_OF_BALLS_REGION[0] + LEGACY_OUT_OF_BALLS_REGION[2]
        )
        self.assertEqual(CURRENT_OUT_OF_BALLS_REGION, config.out_of_balls_region)
        self.assertTrue(routine._is_out_of_balls(frame))


class NoBallsExitTests(unittest.TestCase):
    def _routine(self, poll_results):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(flee_xy=(120, 170))
        routine.stop_event = threading.Event()
        routine.stats = SimpleNamespace(last_event=None)
        routine._no_balls = False
        routine._in_encounter = lambda _frame, **_kwargs: False
        results = iter(poll_results)
        routine._poll = lambda _predicate, _timeout: next(results)
        routine._trace = lambda *_args: None
        routine.device = SimpleNamespace(
            adb_taps=[], backs=0, releases=0,
        )
        routine.device.adb_tap = lambda *point: routine.device.adb_taps.append(point)
        routine.device.release_control_pointers = lambda: setattr(
            routine.device, "releases", routine.device.releases + 1,
        )
        routine.device.back = lambda: setattr(routine.device, "backs", routine.device.backs + 1)
        return routine

    def test_empty_bag_exit_uses_independent_adb_tap_and_verifies_map(self):
        routine = self._routine([True])

        routine._flag_no_balls()

        self.assertTrue(routine._no_balls)
        self.assertEqual("no_balls", routine.stats.last_event)
        self.assertEqual([(120, 170)], routine.device.adb_taps)
        self.assertEqual(1, routine.device.releases)
        self.assertEqual(0, routine.device.backs)

    def test_android_back_is_used_when_flee_tap_does_not_leave(self):
        routine = self._routine([None, True])

        routine._flag_no_balls()

        self.assertEqual(1, routine.device.backs)


if __name__ == "__main__":
    unittest.main()
