import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from avc.ivocr import IvOcr
from avc.shundo import ShundoRoutine


MODEL = (Path(__file__).resolve().parents[1]
         / "models" / "text_recognition_CRNN_EN_2022oct_int8.onnx")


class IvOcrTests(unittest.TestCase):
    def test_reads_an_arbitrary_pgsharp_style_iv_triplet(self):
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        cv2.putText(frame, "IV73 11/7/15", (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 1, cv2.LINE_AA)

        self.assertEqual((11, 7, 15), IvOcr(str(MODEL)).read(frame, (0, 0, 260, 80)))

    def test_rejects_text_without_two_iv_separators(self):
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        cv2.putText(frame, "IV73 11 7 15", (10, 48), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 1, cv2.LINE_AA)

        self.assertIsNone(IvOcr(str(MODEL)).read(frame, (0, 0, 260, 80)))

    def test_shundo_reader_falls_back_when_ui_dump_has_no_iv(self):
        routine = object.__new__(ShundoRoutine)
        routine.device = SimpleNamespace(ui_dump=lambda: "<hierarchy />")
        routine.config = SimpleNamespace(
            iv_ocr_model=str(MODEL),
            pill_region=(0, 0, 260, 80),
            target_ivs=(11, 7, 15),
        )
        frame = np.full((80, 260, 3), 30, dtype=np.uint8)
        reader = SimpleNamespace(read=lambda _frame, _region: (11, 7, 15))

        with patch("avc.shundo.IvOcr", return_value=reader):
            self.assertEqual((11, 7, 15), routine._read_iv_stats(frame))


if __name__ == "__main__":
    unittest.main()
