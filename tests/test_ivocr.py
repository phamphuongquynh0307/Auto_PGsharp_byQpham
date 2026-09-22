import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from avc.ivocr import IvOcr, _Component, _digit_groups
from avc.shundo import ShundoRoutine


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "text_recognition_CRNN_EN_2022oct_int8.onnx"


def _glyph(label, x, w, h=31):
    return _Component(label, x, 0, w, h, w * h, 0.0, np.ones((h, w), bool))


class IvOcrTests(unittest.TestCase):
    def test_reads_an_arbitrary_pgsharp_style_iv_triplet(self):
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        cv2.putText(frame, "IV73 11/7/15", (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 1, cv2.LINE_AA)

        self.assertEqual((11, 7, 15), IvOcr(str(MODEL)).read(frame, (0, 0, 260, 80)))

    def test_reads_a_native_pgsharp_pill_with_a_trailing_status_icon(self):
        # Real 1220x2712 encounter crop of "L34 IV53 11/9/4 ✿". Glyphs sit 4-7 px apart, so an
        # unmasked digit crop swallowed its neighbours, and the ✿ was taken as a second HP digit.
        frame = cv2.imread(str(ROOT / "tests" / "fixtures" / "iv_pill_11_9_4.png"))

        self.assertEqual((11, 9, 4), IvOcr(str(MODEL)).read(frame, (0, 0, 720, 170)))

    def test_reads_a_native_pill_lying_over_a_bright_sky(self):
        # Real 1220x2712 crop of "L8 IV62 13/2/13". The pill is translucent: over the bright sky
        # its own background reads ~127, so a fixed brightness cut fused pill and map into one
        # blob and no slash pair survived.
        frame = cv2.imread(str(ROOT / "tests" / "fixtures" / "iv_pill_13_2_13_bright.png"))

        self.assertEqual((13, 2, 13), IvOcr(str(MODEL)).read(frame, (0, 0, 720, 170)))

    def test_only_a_narrow_one_can_lead_a_two_glyph_iv(self):
        # "IV24 8/1/2": a tight space must not turn the "4" of the percent into ATK 48.
        percent_4, eight, slash_a, one, slash_b, two = (
            _glyph(1, 0, 22), _glyph(2, 30, 22), _glyph(3, 56, 14),
            _glyph(4, 74, 10), _glyph(5, 88, 14), _glyph(6, 106, 22))
        groups = _digit_groups([percent_4, eight, slash_a, one, slash_b, two], slash_a, slash_b)

        self.assertEqual([[2], [4], [6]], [[c.label for c in group] for group in groups])

    def test_rejects_text_without_two_iv_separators(self):
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        cv2.putText(frame, "IV73 11 7 15", (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 1, cv2.LINE_AA)

        self.assertIsNone(IvOcr(str(MODEL)).read(frame, (0, 0, 260, 80)))

    def test_shundo_reader_uses_ocr_without_paying_for_ui_dump(self):
        dumps = []
        routine = object.__new__(ShundoRoutine)
        routine.device = SimpleNamespace(ui_dump=lambda: dumps.append(True) or "<hierarchy />")
        routine.config = SimpleNamespace(
            iv_ocr_model=str(MODEL),
            pill_region=(0, 0, 260, 80),
            target_ivs=(11, 7, 15),
            require_background=False,
        )
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        reader = SimpleNamespace(read=lambda _frame, _region: (11, 7, 15))

        with patch("avc.shundo.IvOcr", return_value=reader):
            self.assertEqual((11, 7, 15), routine._read_iv_stats(frame))
        self.assertEqual([], dumps)


if __name__ == "__main__":
    unittest.main()
