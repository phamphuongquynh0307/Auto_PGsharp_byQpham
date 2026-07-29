import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from avc.catch import CatchRoutine
from avc.vision import find_berry_button


class BerryVisionTests(unittest.TestCase):
    def test_finds_actual_raspberry_button_centre_without_fixed_coordinate(self):
        frame = np.zeros((2712, 1220, 3), dtype=np.uint8)
        center = (183, 2460)
        cv2.circle(frame, center, 95, (210, 210, 210), -1)
        cv2.circle(frame, center, 34, (110, 0, 220), -1)

        found = find_berry_button(frame)

        self.assertIsNotNone(found)
        self.assertLessEqual(abs(found[0] - center[0]), 2)
        self.assertLessEqual(abs(found[1] - center[1]), 2)

    def test_red_ball_elsewhere_on_map_is_not_an_encounter(self):
        frame = np.zeros((2712, 1220, 3), dtype=np.uint8)
        cv2.circle(frame, (610, 2520), 100, (0, 0, 240), -1)

        self.assertIsNone(find_berry_button(frame))


class CatchBerryStateTests(unittest.TestCase):
    def test_catch_uses_berry_for_eager_and_strict_checks(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            berry_start=(145, 2410),
            enc_berry_radius=95,
            enc_berry_min_fill=0.06,
            layout=SimpleNamespace(s=1.0),
        )
        routine._enc_berry_at = None
        frame = object()

        with patch("avc.catch.find_berry_button", return_value=(163, 2460)) as berry:
            self.assertTrue(routine._in_encounter(frame))
            self.assertTrue(routine._in_encounter(frame, strict=True))

        self.assertEqual(2, berry.call_count)


if __name__ == "__main__":
    unittest.main()
