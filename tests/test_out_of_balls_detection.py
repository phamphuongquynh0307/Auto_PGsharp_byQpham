"""Out-of-balls detection supports both the old x0 badge and the missing selector UI."""
import threading
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from avc.catch import CatchConfig, CatchRoutine


class FrameDevice:
    def __init__(self, frames):
        self.frames = iter(frames)

    def screenshot(self, **_kwargs):
        return next(self.frames)


def bare_routine(frames):
    routine = object.__new__(CatchRoutine)
    routine.config = SimpleNamespace(no_balls_missing_frames=3)
    routine.device = FrameDevice(frames)
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._wait_if_paused = lambda: None
    routine._in_encounter = lambda frame, **_kwargs: frame != "map"
    routine._is_out_of_balls = lambda frame: frame == "x0"
    routine._ball_ready = lambda frame: frame == "ball"
    return routine


GRASS = (60, 120, 60)
BALL_CENTRE = (610, 2615)   # base-resolution centre of the throwable ball
BALL_RADIUS = 225


def encounter_frame(dome=None, background=GRASS):
    """A base-resolution encounter screen, with the throwable ball drawn when `dome` is given.

    `dome` is the ball type's colour (BGR): red = Poké, blue = Great, near-black = Ultra. Only
    the dome changes between types — the white belly, the black band and the light centre hub
    are the same ball to ball, which is what the readiness test is supposed to key on.
    """
    frame = np.full((2712, 1220, 3), background, dtype=np.uint8)
    if dome is None:
        return frame                                     # empty bag: no selector at all
    cv2.circle(frame, BALL_CENTRE, BALL_RADIUS, (245, 245, 245), -1)     # white lower half
    cv2.ellipse(frame, BALL_CENTRE, (BALL_RADIUS, BALL_RADIUS), 0, 180, 360, dome, -1)
    cv2.line(frame, (BALL_CENTRE[0] - BALL_RADIUS, BALL_CENTRE[1]),
             (BALL_CENTRE[0] + BALL_RADIUS, BALL_CENTRE[1]), (18, 18, 18), 26)
    cv2.circle(frame, BALL_CENTRE, 80, (18, 18, 18), -1)                 # black band
    cv2.circle(frame, BALL_CENTRE, 55, (215, 215, 215), -1)              # light hub
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


class MissingBallDetectionTests(unittest.TestCase):
    def test_three_missing_frames_in_an_open_encounter_mean_empty(self):
        routine = bare_routine(["missing", "missing", "missing", "missing"])

        self.assertEqual("empty", routine._wait_for_ball_state(0.0))

    def test_ball_appearing_during_confirmation_is_ready(self):
        routine = bare_routine(["missing", "missing", "ball"])

        self.assertEqual("ready", routine._wait_for_ball_state(0.0))

    def test_encounter_closing_during_confirmation_is_not_empty(self):
        routine = bare_routine(["missing", "map"])

        self.assertEqual("closed", routine._wait_for_ball_state(0.0))

    def test_legacy_x0_badge_still_wins_immediately(self):
        routine = bare_routine(["x0"])

        self.assertEqual("empty", routine._wait_for_ball_state(99.0))

    def test_fresh_confirmation_can_reject_smeared_stream_frames(self):
        routine = bare_routine(["missing", "missing", "missing", "ball"])

        self.assertEqual("ready", routine._wait_for_ball_state(0.0))


if __name__ == "__main__":
    unittest.main()
