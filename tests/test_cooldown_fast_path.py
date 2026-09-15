import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from avc.catch import CatchRoutine
from avc.vision import cooldown_zero_visible, load_template


class CooldownZeroFastPathTests(unittest.TestCase):
    REGION = (30, 40, 230, 90)
    THRESHOLD = 0.88

    @classmethod
    def setUpClass(cls):
        cls.template = load_template("templates/cooldown_zero.png")

    def _scene(self, *, erase_last_digit=False, make_last_digit_eight=False):
        mask = cv2.cvtColor(self.template, cv2.COLOR_BGR2GRAY)
        if erase_last_digit:
            mask = mask.copy()
            mask[:, -24:] = 0
        if make_last_digit_eight:
            # A single extra centre stroke turns the final zero into the most dangerous
            # near-match: the whole timer still correlates at roughly 0.98.
            mask = mask.copy()
            mask[18:22, -25:-3] = 255
        scene = np.zeros((180, 320, 3), dtype=np.uint8)
        y, x = 60, 55
        patch = scene[y:y + mask.shape[0], x:x + mask.shape[1]]
        patch[mask > 0] = (0, 255, 0)
        return scene

    def test_exact_zero_timer_is_recognised(self):
        self.assertTrue(cooldown_zero_visible(
            self._scene(), self.template, self.REGION,
            scales=(1.0,), threshold=self.THRESHOLD,
        ))

    def test_partial_or_uncertain_timer_is_not_declared_clear(self):
        self.assertFalse(cooldown_zero_visible(
            self._scene(erase_last_digit=True), self.template, self.REGION,
            scales=(1.0,), threshold=self.THRESHOLD,
        ))

    def test_nonzero_timer_with_a_high_whole_word_score_is_rejected(self):
        self.assertFalse(cooldown_zero_visible(
            self._scene(make_last_digit_eight=True), self.template, self.REGION,
            scales=(1.0,), threshold=self.THRESHOLD,
        ))

    def _routine(self, frame, *, use_feed_bar=True):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            use_feed_bar=use_feed_bar,
            respect_cooldown=True,
            use_ui_dump=True,
            cooldown_check_interval=0.0,
            cooldown_margin=5.0,
            cooldown_region=self.REGION,
            cooldown_zero_threshold=self.THRESHOLD,
        )
        routine._cooldown_until = 0.0
        routine._cooldown_checked_at = 0.0
        routine._cooldown_probe_frame = frame
        routine._cooldown_zero = self.template
        routine._popup_scales = (1.0,)
        return routine

    def test_exact_zero_skips_the_android_hierarchy_dump(self):
        routine = self._routine(self._scene())
        routine._ui_state = lambda: self.fail("zero timer should avoid a UI dump")

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertEqual(0.0, routine._cooldown_left())

        self.assertEqual(100.0, routine._cooldown_checked_at)

    def test_uncertain_timer_falls_back_to_the_authoritative_dump(self):
        routine = self._routine(self._scene(erase_last_digit=True))
        calls = []
        routine._ui_state = lambda: calls.append(True)

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertEqual(0.0, routine._cooldown_left())

        self.assertEqual([True], calls)

    def test_nearby_only_mode_never_probes_or_waits_for_cooldown(self):
        routine = self._routine(
            self._scene(erase_last_digit=True),
            use_feed_bar=False,
        )
        routine._cooldown_until = 999.0
        routine._ui_state = lambda: self.fail("Nearby-only mode must not read cooldown")

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertEqual(0.0, routine._cooldown_left())


if __name__ == "__main__":
    unittest.main()
