"""Out-of-balls detection supports both the old x0 badge and the missing selector UI."""
import threading
import unittest
from types import SimpleNamespace

from avc.catch import CatchRoutine


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
