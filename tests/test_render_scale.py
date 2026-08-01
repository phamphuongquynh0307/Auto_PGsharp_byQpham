"""A measured render scale must reach the *coordinates*, not just the template sizes.

The density guess can be well out — a 1080x2400 panel reporting 480dpi guesses s=1.000 against
a true 0.885 — and until now that error stayed in every fixed coordinate for the whole run.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from avc.catch import BASE_RESOLUTION, CatchConfig, CatchRoutine
from avc.layout import Layout


class LayoutScaleTests(unittest.TestCase):
    def test_measured_scale_outranks_density(self):
        self.assertEqual(0.885, Layout(1080, 2400, density=480, scale=0.885).s)

    def test_density_is_still_used_when_nothing_was_measured(self):
        self.assertEqual(1.0, Layout(1080, 2400, density=480).s)


class RescaleTests(unittest.TestCase):
    def test_rescale_derives_from_base_not_from_the_scaled_copy(self):
        base = CatchConfig()
        guessed = base.scale_to(1080, 2400, 480)          # density guess: s = 1.000
        measured = guessed.rescale(0.885)                 # the truth
        direct = base.scale_to(1080, 2400, 480, scale=0.885)

        self.assertEqual(direct.nearby_slot, measured.nearby_slot)
        self.assertEqual(direct.anchor_region, measured.anchor_region)
        self.assertEqual(direct.slot_offset_y, measured.slot_offset_y)

    def test_rescaling_twice_does_not_compound(self):
        base = CatchConfig().scale_to(1080, 2400, 480)

        once = base.rescale(0.885)
        twice = once.rescale(0.885)

        self.assertEqual(once.nearby_slot, twice.nearby_slot)
        self.assertEqual(once.slot_offset_y, twice.slot_offset_y)

    def test_the_drift_it_corrects_is_most_of_a_slot(self):
        guessed = CatchConfig().scale_to(1080, 2400, 480)
        measured = guessed.rescale(0.885)

        drift = guessed.slot_offset_y - measured.slot_offset_y

        self.assertGreater(drift, 0.7 * measured.slot_pitch)

    def test_non_geometric_settings_survive_a_rescale(self):
        base = CatchConfig(max_catches=42, quick_catch=True, catch_timeout=9.5)
        measured = base.scale_to(1080, 2400, 480).rescale(0.885)

        self.assertEqual(42, measured.max_catches)
        self.assertTrue(measured.quick_catch)
        self.assertEqual(9.5, measured.catch_timeout)

    def test_a_tuned_throw_is_derived_from_the_users_value_not_a_scaled_copy(self):
        # throw_dy is a distance in the *game's* UI, so it follows the screen-width default and
        # not the overlay measurement — but it must still be derived from the -700 the user
        # chose, never from an already-scaled copy, or a rescale would compound the scaling.
        base = CatchConfig(throw_dy=-700)
        guessed = base.scale_to(1080, 2400, 480)

        self.assertEqual(guessed.throw_dy, guessed.rescale(0.885).throw_dy)
        self.assertEqual(-round(700 * (1080 / 1220)), guessed.throw_dy)

    def test_a_scaled_game_distance_follows_the_screen_not_the_density(self):
        # Verified on two devices via the berry-ball span: the game layer tracks width, so a
        # density override changes nothing about it.
        base = CatchConfig(throw_dy=-700)

        self.assertEqual(base.scale_to(1080, 2400, 480).throw_dy,
                         base.scale_to(1080, 2400, 420).throw_dy)


class UiVersusGameLayerTests(unittest.TestCase):
    """The scale is only ever measured from PGSharp's overlay, so only the overlay may move."""

    def test_a_measurement_moves_the_overlay_coordinates(self):
        guessed = CatchConfig().scale_to(1080, 2400, 480)
        measured = guessed.rescale(0.885)

        self.assertNotEqual(guessed.nearby_slot, measured.nearby_slot)
        self.assertNotEqual(guessed.slot_offset_y, measured.slot_offset_y)
        self.assertNotEqual(guessed.anchor_region, measured.anchor_region)

    def test_a_measurement_leaves_the_games_own_ui_alone(self):
        guessed = CatchConfig().scale_to(1080, 2400, 480)
        measured = guessed.rescale(0.885)

        self.assertEqual(guessed.flee_xy, measured.flee_xy)
        self.assertEqual(guessed.berry_start, measured.berry_start)
        self.assertEqual(guessed.ball_fallback, measured.ball_fallback)
        self.assertEqual(guessed.throw_dy, measured.throw_dy)
        self.assertEqual(guessed.enc_berry_radius, measured.enc_berry_radius)

    def test_the_system_dialog_counts_as_a_native_view(self):
        guessed = CatchConfig().scale_to(1080, 2400, 480)

        self.assertNotEqual(guessed.cancel_btn_region,
                            guessed.rescale(0.885).cancel_btn_region)

    def test_shundo_splits_the_layers_the_same_way(self):
        from avc.shundo import ShundoConfig

        guessed = ShundoConfig().scale_to(1080, 2400, 480)
        measured = guessed.rescale(0.885)

        self.assertNotEqual(guessed.pill_region, measured.pill_region)
        self.assertEqual(guessed.flee_xy, measured.flee_xy)


class AdoptScaleTests(unittest.TestCase):
    def _routine(self, config: CatchConfig) -> CatchRoutine:
        routine = object.__new__(CatchRoutine)
        routine.config = config
        routine._on_trace = None
        routine._trace_last_key = ""
        routine._trace_last_at = 0.0
        return routine

    def test_a_real_disagreement_moves_the_coordinates(self):
        routine = self._routine(CatchConfig().scale_to(1080, 2400, 480))
        before = routine.config.slot_offset_y

        routine._adopt_measured_scale(0.885)

        self.assertNotEqual(before, routine.config.slot_offset_y)
        self.assertEqual(0.885, routine.config.render_scale)

    def test_agreement_within_the_threshold_is_left_alone(self):
        routine = self._routine(CatchConfig().scale_to(1080, 2340, 440))
        before = routine.config

        routine._adopt_measured_scale(before.layout.s * 1.01)

        self.assertIs(before, routine.config)

    def test_real_devices_measured_inside_one_step_are_left_alone(self):
        # Every device to hand landed within one 0.05 sweep step of its density estimate, so
        # the "difference" is the grid, not the device. (w, h, dpi, what the sweep answered)
        for width, height, dpi, measured in (
            (1280, 2772, 520, 1.10),    # phone, anchor 0.91
            (1220, 2712, 480, 1.00),    # base resolution, anchor 0.98
            (810, 1440, 270, 0.55),     # MuMu, anchor 0.85 and star 0.88 agreed
        ):
            routine = self._routine(CatchConfig().scale_to(width, height, dpi))
            before = routine.config

            routine._adopt_measured_scale(measured)

            self.assertIs(before, routine.config, f"{width}x{height}@{dpi}")

    def test_the_threshold_is_derived_from_the_measurement_grid(self):
        # Not "is it 0.02" — that just retypes the constant. The rule is that the threshold
        # cannot be finer than what the measurement can resolve, and it has to stay true when
        # the grid changes. It did not, once: a hand-typed 0.05 stopped being right the moment
        # the refine pass narrowed the grid to 0.01.
        self.assertGreaterEqual(CatchRoutine.RESCALE_MIN_STEP,
                                2 * CatchRoutine.CAL_REFINE_STEP)

    def test_the_base_device_is_never_disturbed(self):
        routine = self._routine(CatchConfig().scale_to(*BASE_RESOLUTION, 480))
        before = routine.config

        routine._adopt_measured_scale(1.0)

        self.assertIs(before, routine.config)

    def test_manual_alignment_is_laid_back_over_the_result(self):
        routine = self._routine(CatchConfig().scale_to(1080, 2400, 480))
        hand_placed = (777, 333)

        def reapply(config):
            config.nearby_slot = hand_placed
            return config

        routine._on_rescale = reapply
        routine._adopt_measured_scale(0.885)

        self.assertEqual(hand_placed, routine.config.nearby_slot)

    def test_a_failing_rescale_leaves_the_run_untouched(self):
        routine = self._routine(CatchConfig().scale_to(1080, 2400, 480))
        before = routine.config

        with patch.object(CatchConfig, "rescale", side_effect=RuntimeError("boom")):
            routine._adopt_measured_scale(0.885)

        self.assertIs(before, routine.config)


class CalibrationWiringTests(unittest.TestCase):
    def test_locking_the_scale_also_adopts_it(self):
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig(cal_max_attempts=3).scale_to(1080, 2400, 480)
        routine._cal_scale = None
        routine._cal_attempts = 0
        routine._star = object()
        routine.device = SimpleNamespace(screenshot=lambda: None)
        adopted = []

        with patch("avc.catch.best_matching_scale", return_value=(0.885, 0.91)), \
             patch.object(CatchRoutine, "_adopt_measured_scale", adopted.append):
            routine._ensure_calibrated()

        self.assertEqual([0.885], adopted)


if __name__ == "__main__":
    unittest.main()
