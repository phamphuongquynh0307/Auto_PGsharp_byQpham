"""Measuring the render scale must not hinge on one icon being present and matchable.

Giving up left every coordinate on the density guess for the whole run — the failure that only
shows on somebody else's phone, where that guess is the thing that was wrong.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchConfig, CatchRoutine
from avc.vision import best_matching_scale, load_template
from avc.layout import CALIBRATION_SWEEP


class SourceFallbackTests(unittest.TestCase):
    def _routine(self, **templates) -> CatchRoutine:
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig()
        routine.device = SimpleNamespace(screenshot=lambda: np.zeros((40, 40, 3), np.uint8))
        routine._on_trace = None
        routine._trace_last_key = ""
        routine._trace_last_at = 0.0
        for name in ("_anchor", "_star", "_gear"):
            setattr(routine, name, templates.get(name))
        return routine

    def test_agreeing_sources_are_trusted(self):
        routine = self._routine(_anchor=object(), _star=object(), _gear=object())

        with patch("avc.catch.best_matching_scale", return_value=(0.885, 0.93)):
            scale, _score, _source, agreed = routine._measure_render_scale()

        self.assertEqual(0.885, scale)
        self.assertTrue(agreed)

    def test_scattered_sources_are_measured_but_not_trusted(self):
        # The real 1280x2772@520 case: peaks at 1.10, 1.04 and 1.07 on curves flat to 0.04.
        routine = self._routine(_anchor=object(), _star=object(), _gear=object())
        coarse_then_refine = [(1.10, 0.89), (1.10, 0.89),
                              (1.05, 0.89), (1.04, 0.89),
                              (1.05, 0.90), (1.07, 0.90)]

        with patch("avc.catch.best_matching_scale", side_effect=coarse_then_refine):
            scale, _score, _source, agreed = routine._measure_render_scale()

        self.assertFalse(agreed)
        self.assertEqual(1.07, scale)   # the median, not whichever was asked first

    def test_the_median_is_taken_rather_than_the_best_score(self):
        # A flat curve makes the top score noise; the middle reading is decided by all of them.
        routine = self._routine(_anchor=object(), _star=object(), _gear=object())
        readings = [(0.90, 0.99), (0.90, 0.99),   # best score, but the outlier
                    (0.91, 0.83), (0.91, 0.83),
                    (0.92, 0.84), (0.92, 0.84)]

        with patch("avc.catch.best_matching_scale", side_effect=readings):
            scale, _score, _source, _agreed = routine._measure_render_scale()

        self.assertEqual(0.91, scale)

    def test_a_weak_source_is_skipped_and_the_rest_still_answer(self):
        routine = self._routine(_anchor=object(), _star=object(), _gear=object())

        with patch("avc.catch.best_matching_scale",
                   side_effect=[(0.5, 0.40), (0.885, 0.90), (0.885, 0.90),
                                (0.885, 0.88), (0.885, 0.88)]):
            scale, _score, source, agreed = routine._measure_render_scale()

        self.assertEqual(0.885, scale)
        self.assertTrue(agreed)

    def test_a_missing_template_is_skipped_not_fatal(self):
        routine = self._routine(_anchor=None, _star=None, _gear=object())

        with patch("avc.catch.best_matching_scale", return_value=(0.9, 0.88)) as measure:
            _scale, _score, source, agreed = routine._measure_render_scale()

        self.assertEqual("gear", source)
        self.assertTrue(agreed)                   # a lone source has nothing to disagree with
        self.assertEqual(2, measure.call_count)   # coarse + refine on the only source present

    def test_no_templates_at_all_reports_no_measurement(self):
        routine = self._routine()

        scale, score, _source, agreed = routine._measure_render_scale()

        self.assertIsNone(scale)
        self.assertEqual(0.0, score)
        self.assertFalse(agreed)

    def test_when_all_sources_miss_the_best_attempt_is_reported(self):
        routine = self._routine(_anchor=object(), _star=object(), _gear=object())

        with patch("avc.catch.best_matching_scale",
                   side_effect=[(0.5, 0.40), (0.7, 0.61), (0.6, 0.55)]):
            scale, score, source, agreed = routine._measure_render_scale()

        self.assertEqual(0.7, scale)
        self.assertAlmostEqual(0.61, score)
        self.assertEqual("star", source)
        self.assertFalse(agreed)


class RefinementTests(unittest.TestCase):
    """The coarse grid rounds to ±0.025; the fine pass is what makes the answer trustworthy."""

    def test_a_worse_refinement_is_rejected_rather_than_accepted(self):
        routine = object.__new__(CatchRoutine)

        with patch("avc.catch.best_matching_scale", return_value=(0.61, 0.70)):
            scale, score = routine._refine_scale(None, None, 0.55, 0.90)

        self.assertEqual(0.55, scale)
        self.assertEqual(0.90, score)

    def test_the_fine_grid_brackets_the_coarse_answer(self):
        seen = {}

        def capture(_scene, _template, scales, **_kw):
            seen["scales"] = scales
            return (0.57, 0.96)

        routine = object.__new__(CatchRoutine)
        with patch("avc.catch.best_matching_scale", side_effect=capture):
            routine._refine_scale(None, None, 0.55, 0.85)

        scales = seen["scales"]
        self.assertLessEqual(min(scales), 0.50)
        self.assertGreaterEqual(max(scales), 0.60)
        step = round(scales[1] - scales[0], 4)
        self.assertEqual(CatchRoutine.CAL_REFINE_STEP, step)

    def test_no_scale_is_ever_negative(self):
        seen = {}

        def capture(_scene, _template, scales, **_kw):
            seen["scales"] = scales
            return (0.05, 0.9)

        routine = object.__new__(CatchRoutine)
        with patch("avc.catch.best_matching_scale", side_effect=capture):
            routine._refine_scale(None, None, 0.04, 0.85)

        self.assertTrue(all(s > 0 for s in seen["scales"]))


class ReductionTests(unittest.TestCase):
    """Halving the frame is what pays for trying several sources; it must not move the answer."""

    def test_reduction_returns_the_scale_in_full_frame_units(self):
        scene = np.zeros((600, 400, 3), np.uint8)
        template = np.full((60, 60, 3), 200, np.uint8)
        scene[200:260, 150:210] = 200

        full, _ = best_matching_scale(scene, template, (0.5, 1.0, 1.5), grayscale=False)
        halved, _ = best_matching_scale(scene, template, (0.5, 1.0, 1.5),
                                        grayscale=False, reduction=0.5)

        self.assertEqual(full, halved)

    def test_the_real_anchor_still_measures_the_authoring_device_at_one(self):
        import glob

        import cv2

        frames = sorted(glob.glob("_*.png"))
        if not frames:
            self.skipTest("no captured device frames in the working tree")
        anchor = load_template("templates/nearby_anchor.png")
        for path in frames[:3]:
            scene = cv2.imread(path)
            if scene is None:
                continue
            scale, score = best_matching_scale(scene, anchor, CALIBRATION_SWEEP,
                                               grayscale=False, reduction=0.5)
            self.assertEqual(1.0, scale, path)
            self.assertGreaterEqual(score, 0.82, path)


if __name__ == "__main__":
    unittest.main()
