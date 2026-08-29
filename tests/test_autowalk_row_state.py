"""Which of the two AutoWalk row templates wins when both clear their threshold.

Measured on a live 1220x2712 phone: the '⊘' paused crop scored 0.72 off a neighbouring PGSharp
menu row while the running-row glyph scored 0.97 on the actual AutoWalk row 100px below it.
Returning whichever template happened to be tested first made the routine read a running walk
as paused and tap the wrong row on every empty Nearby cycle — then wait for a '⊘' to disappear
that was never there.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchConfig, CatchRoutine
from avc.vision import Match


class AutoWalkRowStateTests(unittest.TestCase):
    def _read(self, paused_hit, row_hit):
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig()
        routine._scales = (1.0,)
        routine._aw_paused = object()
        routine._aw_row = object()
        calls = iter((paused_hit, row_hit))

        def fake_find(*_args, **_kwargs):
            hit = next(calls)
            return [Match(hit[0][0] - 10, hit[0][1] - 10, 20, 20, hit[1])] if hit else []

        with patch("avc.catch.find", side_effect=fake_find):
            return routine._autowalk_row_visual_in(
                np.zeros((2712, 1220, 3), dtype=np.uint8), (273, 1330))

    def test_the_stronger_template_decides_when_both_match(self):
        self.assertEqual(((280, 1632), False),
                         self._read(((278, 1532), 0.72), ((280, 1632), 0.97)))

    def test_a_genuinely_paused_row_still_reads_as_paused(self):
        self.assertEqual(((280, 1632), True),
                         self._read(((280, 1632), 0.95), ((280, 1632), 0.74)))

    def test_either_template_alone_is_still_enough(self):
        self.assertEqual(((280, 1632), True), self._read(((280, 1632), 0.81), None))
        self.assertEqual(((280, 1632), False), self._read(None, ((280, 1632), 0.81)))

    def test_no_match_at_all_reports_nothing(self):
        self.assertIsNone(self._read(None, None))


if __name__ == "__main__":
    unittest.main()
