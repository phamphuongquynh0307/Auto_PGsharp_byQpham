"""The shadow pass measures the pixel estimates without being allowed to affect the run.

Its whole value is that it can be shipped on by default, so the two things worth proving are
that it records a disagreement and that running it leaves the routine exactly as it found it.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchRoutine


def _routine(**overrides):
    routine = object.__new__(CatchRoutine)
    routine.config = SimpleNamespace(
        use_ui_dump=True,
        force_slot=True,
        nearby_slot=(1100, 840),
        dialog_region=(150, 1150, 950, 500),
        game_scale=1.0,
    )
    for key, value in overrides.items():
        setattr(routine.config, key, value)
    routine.device = SimpleNamespace(
        _stream=object(),
        screenshot=lambda *a, **k: np.zeros((2712, 1220, 3), dtype=np.uint8))
    routine._tpl_s = 1.0
    routine._shadow_started = False
    routine._anchor_cache = (1150, 1900)
    routine._nearby_handle_cache = (1150, 700)
    routine._force_bottom_cache = (1150, 1880)
    routine._force_bottom_value = 1880
    routine._force_bottom_at = 12.5
    routine._star_cache = (300, 1400)
    routine._ui_nearby_bar = lambda _state: [(1104, 845)]
    routine._slot_in = lambda _frame: (1102, 842)
    routine._autowalk_row_visual_in = lambda _frame, _star: ((300, 1520), True)
    return routine


def _state(**kwargs):
    return SimpleNamespace(autowalk_row=kwargs.get("autowalk_row", ("AW", (298, 1523))),
                           cancel_button=kwargs.get("cancel_button"))


class ShadowCompareTests(unittest.TestCase):
    def _run(self, routine, state=None):
        rows = []
        with patch("avc.catch.diag.shadow", rows.append), \
                patch("avc.catch.find_dialog_buttons", return_value=[]):
            routine._shadow_check(state if state is not None else _state())
        return rows

    def test_it_records_the_gap_between_the_two_coordinates(self):
        rows = self._run(_routine())
        body = [r for r in rows if r.startswith("0") or r[:2].isdigit()]
        joined = "\n".join(body)

        self.assertIn("nearby-moc@", joined)
        self.assertIn("(1102,842)", joined)
        self.assertIn("(1104,845)", joined)
        # hypot(2, 3) rounds to 4px.
        self.assertRegex(joined, r"nearby-moc@.*\b4px\b")
        self.assertRegex(joined, r"autowalk.*\b4px\b")

    def test_the_hand_calibration_is_measured_too_when_it_is_what_gets_tapped(self):
        rows = "\n".join(self._run(_routine()))

        self.assertIn("nearby-canhtay", rows)
        # (1100,840) against PGSharp's (1104,845) is 6px of drift the run never reports.
        self.assertRegex(rows, r"nearby-canhtay.*\b6px\b")

    def test_a_one_sided_answer_is_named_rather_than_measured(self):
        routine = _routine()
        routine._slot_in = lambda _frame: None
        rows = "\n".join(self._run(routine))

        self.assertRegex(rows, r"nearby-moc@.*CHI-UI")

    def test_rows_neither_side_saw_are_left_out(self):
        routine = _routine()
        routine._ui_nearby_bar = lambda _state: []
        routine._slot_in = lambda _frame: None
        rows = "\n".join(self._run(routine))

        self.assertNotIn("nearby-moc@", rows)
        self.assertNotIn("nearby-canhtay", rows)

    def test_running_it_leaves_every_detector_cache_as_it_found_it(self):
        routine = _routine()
        before = {name: getattr(routine, name) for name in CatchRoutine._SHADOW_VOLATILE}

        def clobber(_frame):
            routine._anchor_cache = None
            routine._nearby_handle_cache = (1, 1)
            routine._force_bottom_cache = None
            routine._force_bottom_value = None
            routine._force_bottom_at = 99.0
            routine._star_cache = None
            return (1102, 842)

        routine._slot_in = clobber
        self._run(routine)

        after = {name: getattr(routine, name) for name in CatchRoutine._SHADOW_VOLATILE}
        self.assertEqual(before, after)

    def test_it_keeps_its_own_warm_caches_instead_of_starting_cold_every_time(self):
        """In force_slot mode nothing else populates the anchor, so restoring the run's empty
        value would make every dump repay a full-region sweep."""
        routine = _routine()
        for name in CatchRoutine._SHADOW_VOLATILE:
            setattr(routine, name, None)

        def warms(_frame):
            routine._anchor_cache = (1058, 1900)
            routine._nearby_handle_cache = (1058, 700)
            return (1102, 842)

        routine._slot_in = warms
        self._run(routine)

        # The run still sees the empty caches it had...
        self.assertIsNone(routine._anchor_cache)
        # ...while the measurement starts warm next time.
        self.assertEqual((1058, 1900), routine._shadow_caches["_anchor_cache"])

        seen = []
        routine._slot_in = lambda _frame: seen.append(routine._anchor_cache) or (1102, 842)
        self._run(routine)
        self.assertEqual([(1058, 1900)], seen)
        self.assertIsNone(routine._anchor_cache)

    def test_a_detector_that_raises_cannot_stop_the_run(self):
        routine = _routine()

        def boom(_frame):
            raise RuntimeError("detector exploded")

        routine._slot_in = boom
        self._run(routine)  # must not raise
        self.assertIsNotNone(routine._anchor_cache)

    def test_a_settled_answer_stops_costing_anything(self):
        """The cap has to stop the detector running, not merely stop the row being written:
        the '@' search behind one reading costs ~200ms on a bar with no cacheable handle."""
        routine = _routine()
        calls = []
        routine._slot_in = lambda _frame: calls.append(1) or (1102, 842)

        for _ in range(CatchRoutine._SHADOW_ROWS_PER_KIND + 10):
            self._run(routine)

        self.assertEqual(CatchRoutine._SHADOW_ROWS_PER_KIND, len(calls))
        self.assertTrue(routine._shadow_done("nearby-moc@"))

    def test_a_question_both_sides_declined_still_counts_as_asked(self):
        routine = _routine()
        routine._ui_nearby_bar = lambda _state: []
        routine._slot_in = lambda _frame: None
        self._run(routine)

        self.assertEqual(1, routine._shadow_counts["nearby-moc@"])

    def test_no_measurement_is_worth_a_one_shot_capture(self):
        """Without the stream, screenshot() costs seconds over Wi-Fi. Skip rather than pay."""
        routine = _routine()
        routine.device._stream = None

        self.assertEqual([], self._run(routine))

    def test_nothing_is_written_when_the_view_tree_is_not_in_use(self):
        rows = self._run(_routine(use_ui_dump=False))

        self.assertEqual([], rows)

    def test_the_session_header_names_the_device_it_was_measured_on(self):
        rows = self._run(_routine())

        self.assertTrue(any("man_hinh=1220x2712" in r for r in rows))
        self.assertTrue(any("force_slot=True" in r for r in rows))


if __name__ == "__main__":
    unittest.main()
