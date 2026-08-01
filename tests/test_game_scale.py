"""Pokémon GO's own UI gets measured from two controls found without any template.

It is the one layer nothing could correct: the render scale the routine measures comes from
PGSharp's overlay, and the game engine need not follow it. On MuMu the density estimate (0.5625)
and the resolution ratio (0.6639) sit 18% apart with nothing on screen to say which is right.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from avc.catch import BASE_RESOLUTION, CatchConfig, CatchRoutine


def _routine(config: CatchConfig) -> CatchRoutine:
    routine = object.__new__(CatchRoutine)
    routine.config = config
    routine._enc_berry_at = None
    routine._game_samples = []
    routine._game_scale_done = False
    routine._on_trace = None
    routine._trace_last_key = ""
    routine._trace_last_at = 0.0
    return routine


def _feed(routine: CatchRoutine, berry, ball, times: int) -> None:
    """Drive `times` readings of the two game controls at the given positions."""
    with patch("avc.catch.find_enc_ball", return_value=ball):
        for _ in range(times):
            routine._enc_berry_at = berry
            routine._sample_game_scale(object())


class SpanMeasurementTests(unittest.TestCase):
    def test_the_base_devices_own_span_reads_as_scale_one(self):
        routine = _routine(CatchConfig())
        # The positions five real 1220x2712 encounter frames actually produced.
        _feed(routine, (148, 2467), (1067, 2440), 3)

        self.assertTrue(routine._game_scale_done)
        # Within the drift threshold, so nothing is disturbed on the authoring device.
        self.assertIsNone(routine.config.game_scale)

    def test_a_genuinely_smaller_game_ui_is_measured_and_adopted(self):
        config = CatchConfig().scale_to(1080, 2400, 480)   # density guesses 1.000
        routine = _routine(config)
        before = config.berry_start
        # Same two controls, but the game drew them 0.80 of base size apart.
        _feed(routine, (118, 1974), (853, 1952), 3)

        self.assertIsNotNone(routine.config.game_scale)
        self.assertAlmostEqual(0.80, routine.config.game_scale, places=1)
        self.assertNotEqual(before, routine.config.berry_start)

    def test_measuring_the_game_leaves_the_overlay_alone(self):
        config = CatchConfig().scale_to(1080, 2400, 480)
        routine = _routine(config)
        overlay_before = (config.nearby_slot, config.slot_offset_y, config.anchor_region)

        _feed(routine, (118, 1974), (853, 1952), 3)

        self.assertEqual(overlay_before[0], routine.config.nearby_slot)
        self.assertEqual(overlay_before[1], routine.config.slot_offset_y)
        self.assertEqual(overlay_before[2], routine.config.anchor_region)


class FalsePositiveGuardTests(unittest.TestCase):
    """A phantom Berry hit was seen on a live map frame; one reading can never be enough."""

    def test_one_reading_never_moves_anything(self):
        routine = _routine(CatchConfig().scale_to(1080, 2400, 480))
        before = routine.config

        _feed(routine, (118, 1974), (853, 1952), 1)

        self.assertIs(before, routine.config)
        self.assertFalse(routine._game_scale_done)

    def test_readings_that_disagree_are_discarded_rather_than_averaged(self):
        routine = _routine(CatchConfig().scale_to(1080, 2400, 480))
        before = routine.config

        with patch("avc.catch.find_enc_ball", side_effect=[(853, 1952), (500, 1952), (853, 1952)]):
            for berry in ((118, 1974), (118, 1974), (118, 1974)):
                routine._enc_berry_at = berry
                routine._sample_game_scale(object())

        self.assertIs(before, routine.config)
        self.assertFalse(routine._game_scale_done)

    def test_a_missing_ball_selector_contributes_no_reading(self):
        routine = _routine(CatchConfig())

        _feed(routine, (148, 2467), None, 5)

        self.assertEqual([], routine._game_samples)

    def test_a_missing_berry_contributes_no_reading(self):
        routine = _routine(CatchConfig())

        _feed(routine, None, (1067, 2440), 5)

        self.assertEqual([], routine._game_samples)

    def test_the_question_is_asked_once_and_then_dropped(self):
        routine = _routine(CatchConfig().scale_to(1080, 2400, 480))
        _feed(routine, (118, 1974), (853, 1952), 3)
        settled = routine.config

        _feed(routine, (60, 1974), (400, 1952), 3)   # wildly different, must be ignored

        self.assertIs(settled, routine.config)


class DerivedThresholdTests(unittest.TestCase):
    """How far apart the accepted readings landed *is* this device's measurement precision."""

    def _spans_for(self, scales):
        """Berry/ball positions whose separation encodes each requested scale."""
        from avc.layout import BASE_GAME_SPAN

        return [((0, 0), (round(BASE_GAME_SPAN * s), 0)) for s in scales]

    def _run(self, config, scales):
        routine = _routine(config)
        pairs = self._spans_for(scales)
        with patch("avc.catch.find_enc_ball", side_effect=[ball for _b, ball in pairs]):
            for berry, _ball in pairs:
                routine._enc_berry_at = berry
                routine._sample_game_scale(object())
        return routine

    @staticmethod
    def _game_current(config):
        """The baseline the routine compares against: the game layer's width-ratio default."""
        from avc.layout import Layout

        return Layout(*config.screen).s

    def test_steady_readings_earn_a_tight_threshold_and_catch_a_small_error(self):
        # 1.5% off, with readings agreeing to ~0.1%. The old fixed 4% would have ignored this.
        config = CatchConfig().scale_to(1080, 2400, 480)
        current = self._game_current(config)

        routine = self._run(config, [current * 1.015, current * 1.016, current * 1.015])

        self.assertIsNotNone(routine.config.game_scale)

    def test_jittery_readings_demand_a_wider_gap_before_acting(self):
        # Same 1.5% difference, but the readings themselves disagree by ~2% — so the difference
        # is inside the measurement's own noise and must not be acted on.
        config = CatchConfig().scale_to(1080, 2400, 480)
        current = self._game_current(config)
        before = config

        routine = self._run(config, [current * 1.005, current * 1.025, current * 1.015])

        self.assertIs(before, routine.config)

    def test_perfect_agreement_cannot_derive_a_zero_threshold(self):
        config = CatchConfig().scale_to(1080, 2400, 480)
        current = self._game_current(config)
        before = config

        # Identical readings a hair off: spread is 0, so only the floor stands between this
        # and rescaling on nothing at all.
        routine = self._run(config, [current * 1.002] * 3)

        self.assertIs(before, routine.config)

    def test_a_large_error_is_adopted_however_the_threshold_lands(self):
        config = CatchConfig().scale_to(1080, 2400, 480)

        routine = self._run(config, [0.80, 0.802, 0.799])

        self.assertAlmostEqual(0.80, routine.config.game_scale, places=2)


class ConfigPlumbingTests(unittest.TestCase):
    def test_rescale_game_touches_only_the_game_layer(self):
        config = CatchConfig().scale_to(1080, 2400, 480)

        rescaled = config.rescale_game(0.80)

        self.assertNotEqual(config.flee_xy, rescaled.flee_xy)
        self.assertNotEqual(config.throw_dy, rescaled.throw_dy)
        self.assertEqual(config.nearby_slot, rescaled.nearby_slot)
        self.assertEqual(config.slot_offset_y, rescaled.slot_offset_y)

    def test_the_two_measurements_compose_instead_of_overwriting(self):
        config = CatchConfig().scale_to(1080, 2400, 480)

        both = config.rescale(0.885).rescale_game(0.80)

        self.assertEqual(0.885, both.render_scale)
        self.assertEqual(0.80, both.game_scale)
        self.assertEqual(config.rescale(0.885).nearby_slot, both.nearby_slot)
        self.assertEqual(config.rescale_game(0.80).flee_xy, both.flee_xy)

    def test_the_base_device_with_no_measurements_is_still_untouched(self):
        config = CatchConfig()

        self.assertIs(config, config.scale_to(*BASE_RESOLUTION, 480))


if __name__ == "__main__":
    unittest.main()
