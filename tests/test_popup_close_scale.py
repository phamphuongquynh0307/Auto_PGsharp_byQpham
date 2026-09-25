import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from avc.catch import CatchConfig, CatchRoutine
from avc.layout import CALIBRATION_SWEEP
from avc.shundo import ShundoRoutine
from avc.vision import Match, find_exit_game_cancel, find_popup_close, load_template


def _popup_config():
    return SimpleNamespace(
        popup_threshold=0.7,
        dialog_region=(150, 1150, 950, 500),
        cancel_btn_region=(620, 1480, 310, 220),
    )


class PopupCloseScaleTests(unittest.TestCase):
    def test_real_exit_game_popup_targets_cancel_and_ignores_map(self):
        popup = cv2.imread("tests/fixtures/exit_game_popup.png")
        template = load_template("templates/exit_game_cancel.png")
        self.assertEqual((608, 1564), find_exit_game_cancel(
            cv2.resize(popup, (1220, 2712)), template))
        without_cancel = popup.copy()
        without_cancel[420:455, 125:215] = 255
        self.assertIsNone(find_exit_game_cancel(without_cancel, template))

    def test_dismiss_news_popup_is_closed_in_catch_and_shundo(self):
        frame = cv2.imread("tests/fixtures/dismiss_popup.png")
        dismiss = load_template("templates/dismiss.png")

        for routine_type, module_name in (
                (CatchRoutine, "avc.catch"), (ShundoRoutine, "avc.shundo")):
            with self.subTest(routine=routine_type.__name__):
                taps = []
                routine = object.__new__(routine_type)
                routine.config = _popup_config()
                routine.config.use_ui_dump = False
                routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
                routine.stats = SimpleNamespace(last_event="")
                routine._popup_block_until = 0.0
                routine._exit_game_cancel = None
                routine._cancel_btn = None
                routine._dismiss = dismiss
                if routine_type is CatchRoutine:
                    routine._trace = lambda *_args: None
                else:
                    routine._teleport_blocked = False

                with patch(f"{module_name}.find_dialog_buttons", return_value=[]):
                    self.assertTrue(routine._handle_popups(frame))

                self.assertEqual(1, len(taps))
                self.assertLessEqual(abs(taps[0][0] - 171), 5)
                self.assertLessEqual(abs(taps[0][1] - 728), 5)

    def test_shundo_taps_game_drawn_cancel_without_android_button(self):
        taps = []
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._exit_game_cancel = load_template("templates/exit_game_cancel.png")
        frame = cv2.resize(cv2.imread("tests/fixtures/exit_game_popup.png"), (1220, 2712))

        self.assertTrue(routine._handle_popups(frame))
        self.assertEqual([(608, 1564)], taps)

    def test_catch_taps_game_drawn_cancel_without_android_button(self):
        taps = []
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine._trace = lambda *_args: None
        routine._popup_block_until = 0.0
        routine._exit_game_cancel = load_template("templates/exit_game_cancel.png")
        frame = cv2.resize(cv2.imread("tests/fixtures/exit_game_popup.png"), (1220, 2712))

        self.assertTrue(routine._handle_popups(frame))
        self.assertEqual([(608, 1564)], taps)

    def test_known_encounter_rate_limits_the_heavy_popup_scan(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(popup_known_screen_interval=8.0)
        routine._popup_full_scan_at = 95.0
        routine._in_encounter = lambda _frame: True

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertFalse(routine._needs_full_popup_scan(object()))

    def test_visible_nearby_bar_does_not_skip_the_popup_scan(self):
        """PGSharp's bar overlays game popups, so seeing it must not suppress the scan."""
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(popup_known_screen_interval=8.0)
        routine._popup_full_scan_at = 95.0
        routine._in_encounter = lambda _frame: False
        routine._bar_visible = lambda _frame: True

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertTrue(routine._needs_full_popup_scan(object()))

    def test_unknown_screen_still_gets_an_immediate_popup_scan(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(popup_known_screen_interval=8.0)
        routine._popup_full_scan_at = 95.0
        routine._in_encounter = lambda _frame: False
        routine._bar_visible = lambda _frame: False

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertTrue(routine._needs_full_popup_scan(object()))

    def test_known_screen_gets_periodic_popup_safety_scan(self):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(popup_known_screen_interval=8.0)
        routine._popup_full_scan_at = 91.0
        routine._in_encounter = lambda _frame: self.fail("interval check should win first")
        routine._bar_visible = lambda _frame: self.fail("interval check should win first")

        with patch("avc.catch.time.monotonic", return_value=100.0):
            self.assertTrue(routine._needs_full_popup_scan(object()))

    def test_catch_geometry_is_confirmed_by_exact_android_cancel_node(self):
        taps = []
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.config.use_ui_dump = True
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._cancel_btn = None
        routine._trace = lambda *_args: None
        routine._ui_state = lambda force=False: SimpleNamespace(cancel_button=(515, 1510))

        with patch("avc.catch.find_dialog_buttons",
                   return_value=[(500, 1510), (760, 1510)]):
            handled = routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([(515, 1510)], taps)

    def test_catch_uses_visual_dialog_fallback_when_ui_dump_is_unsafe(self):
        taps = []
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.config.use_ui_dump = True
        routine.device = SimpleNamespace(
            tap=lambda *xy: taps.append(xy),
            supports_ui_dump=lambda: False,
        )
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._cancel_btn = None
        routine._trace = lambda *_args: None
        routine._ui_state = lambda **_kwargs: self.fail("unsafe hierarchy reader was called")

        with patch("avc.catch.find_dialog_buttons",
                   return_value=[(500, 1510), (760, 1510)]):
            handled = routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([(500, 1510)], taps)

    def test_inner_x_matches_when_the_button_background_changed(self):
        template = load_template("templates/close_btn_white.png")
        th, tw = template.shape[:2]
        glyph = template[th // 4:th - th // 4, tw // 4:tw - tw // 4]
        frame = np.full((1000, 600, 3), (150, 240, 150), dtype=np.uint8)
        x0, y0 = 300 - glyph.shape[1] // 2, 920 - glyph.shape[0] // 2
        frame[y0:y0 + glyph.shape[0], x0:x0 + glyph.shape[1]] = glyph

        close = find_popup_close(frame, (template,), threshold=0.7, scales=(1.0,))

        self.assertIsNotNone(close)
        self.assertLessEqual(abs(close.center[0] - 300), 2)
        self.assertLessEqual(abs(close.center[1] - 920), 2)

    def test_catch_tries_game_ui_scales_for_the_bottom_close_x(self):
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace()
        routine.stats = SimpleNamespace(last_event="")
        routine.stop_event = threading.Event()
        routine._popup_block_until = 0.0
        routine._popup_scales = (0.55,)
        routine._game_popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._maybe_later = None
        routine._popup_autowalk = None
        routine._claim_rewards = None
        routine._caught_ok = None
        routine._check_btn = None
        routine._close_btn = object()
        routine._close_btn_blue = object()
        routine._close_btn_white = object()
        routine._ball_in = lambda _frame: None
        routine._is_pokestop_screen = lambda _frame: False

        with patch("avc.catch.find_popup_close", return_value=None) as close:
            routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertEqual(1, close.call_count)
        self.assertEqual(0.82, close.call_args.kwargs["threshold"])
        self.assertEqual((0.66,), close.call_args.kwargs["scales"])
        self.assertEqual(CALIBRATION_SWEEP, close.call_args.kwargs["fallback_scales"])

    def test_wide_scale_sweep_is_not_repaid_on_every_ordinary_cycle(self):
        """The 17-scale fallback costs ~90ms and can only ever come back empty on a map frame.

        A popup that renders at an unexpected scale is blocking, so it is still there a second
        later; the calibrated scales keep being tried every cycle either way.
        """
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.config.use_ui_dump = False
        routine.device = SimpleNamespace(tap=lambda *xy: None)
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._scales = (0.55,)
        routine._popup_scales = (0.66,)
        routine._game_popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._popup_autowalk = None
        routine._maybe_later = None
        routine._claim_rewards = None
        routine._caught_ok = None
        routine._check_btn = None
        routine._close_btn = object()
        routine._close_btn_blue = object()
        routine._close_btn_white = object()
        routine._ball_in = lambda _frame: None
        routine._is_pokestop_screen = lambda _frame: False

        frame = np.zeros((2712, 1220, 3), dtype=np.uint8)
        with patch("avc.catch.find_dialog_buttons", return_value=[]),                 patch("avc.catch.find_popup_close", return_value=None) as close:
            for _ in range(4):
                routine._handle_popups(frame)

        swept = [call.kwargs["fallback_scales"] for call in close.call_args_list]
        self.assertEqual(4, len(swept))
        self.assertEqual(CALIBRATION_SWEEP, swept[0])
        self.assertEqual([(), (), ()], swept[1:])

        # Once the budget is up the safety net is spent again.
        routine._popup_sweep_at -= routine.POPUP_SWEEP_INTERVAL
        with patch("avc.catch.find_dialog_buttons", return_value=[]),                 patch("avc.catch.find_popup_close", return_value=None) as close:
            routine._handle_popups(frame)
        self.assertEqual(CALIBRATION_SWEEP, close.call_args.kwargs["fallback_scales"])

    def test_medal_x_wins_before_the_share_button_can_match_weather(self):
        taps = []
        routine = object.__new__(CatchRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine.stop_event = threading.Event()
        routine._popup_block_until = 0.0
        routine._popup_scales = (0.55,)
        routine._game_popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._popup_weather = object()
        routine._popup_speed = None
        routine._maybe_later = None
        routine._popup_autowalk = None
        routine._claim_rewards = None
        routine._caught_ok = None
        routine._check_btn = None
        routine._close_btn = object()
        routine._close_btn_blue = object()
        routine._close_btn_white = object()
        routine._ball_in = lambda _frame: None
        routine._is_pokestop_screen = lambda _frame: False

        medal_x = Match(580, 2480, 60, 60, 0.93)
        with patch("avc.catch.find_dialog_buttons", return_value=[]), \
                patch("avc.catch.find_popup_close", return_value=medal_x), \
                patch("avc.catch.find_fast",
                      side_effect=AssertionError("SHARE was checked before the medal X")):
            handled = routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([medal_x.center], taps)

    def test_shundo_tries_game_ui_scales_for_the_bottom_close_x(self):
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace()
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._scales = (0.55,)
        routine._popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._claim_rewards = None
        routine._close_btns = (object(),)
        routine._encounter_visible = lambda _frame: False

        with patch("avc.shundo.find_popup_close", return_value=None) as close:
            routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertEqual(1, close.call_count)
        self.assertEqual(0.82, close.call_args.kwargs["threshold"])
        self.assertEqual((0.66,), close.call_args.kwargs["scales"])
        self.assertEqual(CALIBRATION_SWEEP, close.call_args.kwargs["fallback_scales"])

    def test_shundo_uses_geometry_when_android_cancel_artwork_does_not_match(self):
        taps = []
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._scales = (0.55,)
        routine._popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._teleport_blocked = False

        with patch("avc.shundo.find_dialog_buttons",
                   return_value=[(720, 1520), (490, 1520)]), \
                patch("avc.shundo.find_popup_close",
                      side_effect=AssertionError("dialog fallback ran too late")):
            handled = routine._handle_popups(np.zeros((1440, 810, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([(490, 1520)], taps)
        # CANCEL is pressed, but the run is NOT declared dead. "Two buttons in a centre box,
        # the left one chosen" describes a great many Android dialogs, and treating that as
        # proof that Go Plus is connected turned any stray dialog into a permanent silent stop.
        # Only the Go Plus warning's own template, matched in its own tight region, may do that.
        self.assertFalse(routine._teleport_blocked)

    def test_shundo_uses_visual_dialog_fallback_when_ui_dump_is_unsafe(self):
        taps = []
        dump_calls = []
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.config.use_ui_dump = True
        routine.device = SimpleNamespace(
            tap=lambda *xy: taps.append(xy),
            ui_dump=lambda: dump_calls.append(True),
            supports_ui_dump=lambda: False,
        )
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._scales = (0.55,)
        routine._popup_scales = (0.66,)
        routine._cancel_btn = None
        routine._teleport_blocked = False

        with patch("avc.shundo.find_dialog_buttons",
                   return_value=[(720, 1520), (490, 1520)]):
            handled = routine._handle_popups(np.zeros((1440, 810, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([(490, 1520)], taps)
        self.assertEqual([], dump_calls)

    def test_shundo_cancels_exit_dialog_after_flee_back(self):
        taps = []
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy),
                                         ui_dump=lambda: '<hierarchy/>')
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._exit_dialog_until = 110.0
        routine._exit_dialog_checked_at = 0.0
        routine._cancel_btn = None

        with patch("avc.shundo.time.monotonic", return_value=100.0), \
             patch("avc.shundo.uidump.parse",
                   return_value=SimpleNamespace(cancel_button=(515, 1510))):
            self.assertTrue(routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8)))

        self.assertEqual([(515, 1510)], taps)
        self.assertEqual(0.0, routine._exit_dialog_until)

    def test_pokestop_uses_calibrated_close_point_when_x_template_misses(self):
        taps = []
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig()
        routine.device = SimpleNamespace(tap=lambda *xy: taps.append(xy))
        routine.stats = SimpleNamespace(last_event="")
        routine.stop_event = threading.Event()
        routine._popup_block_until = 0.0
        routine._popup_scales = (1.0,)
        routine._game_popup_scales = (1.0,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._maybe_later = None
        routine._popup_autowalk = None
        routine._claim_rewards = None
        routine._caught_ok = None
        routine._check_btn = None
        routine._close_btn = object()
        routine._close_btn_blue = object()
        routine._close_btn_white = object()
        routine._ball_in = lambda _frame: None
        routine._is_pokestop_screen = lambda _frame: True

        with patch("avc.catch.find_dialog_buttons", return_value=[]), \
                patch("avc.catch.find_popup_close", return_value=None), \
                patch("avc.catch.find_fast", return_value=[]):
            handled = routine._handle_popups(np.zeros((2712, 1220, 3), dtype=np.uint8))

        self.assertTrue(handled)
        self.assertEqual([routine.config.pokestop_close_xy], taps)

    def test_stale_popup_x_does_not_tap_the_returned_map(self):
        stale = np.zeros((2712, 1220, 3), dtype=np.uint8)
        fresh_map = np.ones_like(stale)
        match = Match(580, 2480, 60, 60, 0.93)
        for routine_type, module_name in (
            (CatchRoutine, "avc.catch"),
            (ShundoRoutine, "avc.shundo"),
        ):
            with self.subTest(mode=routine_type.__name__):
                taps = []
                routine = object.__new__(routine_type)
                routine.config = _popup_config()
                routine.device = SimpleNamespace(
                    tap=lambda *xy: taps.append(xy),
                    screenshot=lambda *, fresh=False: fresh_map,
                )
                routine.stats = SimpleNamespace(last_event="")
                routine._popup_block_until = 0.0
                routine._popup_scales = (0.66,)
                routine._cancel_btn = None
                routine._popup_weather = None
                routine._popup_speed = None
                routine._claim_rewards = None
                if routine_type is CatchRoutine:
                    routine._game_popup_scales = (0.66,)
                    routine._close_btn = routine._close_btn_blue = routine._close_btn_white = object()
                    routine._ball_in = lambda _frame: None
                    routine._bar_visible = lambda frame: frame is fresh_map
                    routine._trace = lambda *_args: None
                else:
                    routine._close_btns = (object(),)
                    routine._encounter_visible = lambda _frame: False
                    routine._anchor_in = lambda frame: (972, 1053) if frame is fresh_map else None
                with patch(f"{module_name}.find_dialog_buttons", return_value=[]), \
                        patch(f"{module_name}.find_popup_close",
                              side_effect=lambda frame, *_a, **_k: match if frame is stale else None):
                    self.assertFalse(routine._handle_popups(stale))
                self.assertEqual([], taps)

    def test_shundo_false_claim_match_does_not_tap_a_fresh_map(self):
        stale = np.zeros((2712, 1220, 3), dtype=np.uint8)
        fresh_map = np.ones_like(stale)
        claim = object()
        taps = []
        routine = object.__new__(ShundoRoutine)
        routine.config = _popup_config()
        routine.device = SimpleNamespace(
            tap=lambda *xy: taps.append(xy),
            screenshot=lambda **_kwargs: fresh_map,
        )
        routine.stats = SimpleNamespace(last_event="")
        routine._popup_block_until = 0.0
        routine._popup_scales = (1.0,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._claim_rewards = claim
        routine._close_btns = ()
        routine._encounter_visible = lambda _frame: False
        routine._anchor_in = lambda frame: (972, 1053) if frame is fresh_map else None

        def find_button(frame, template, **_kwargs):
            return [Match(500, 1500, 80, 50, 0.9)] if template is claim and frame is stale else []

        with patch("avc.shundo.find_dialog_buttons", return_value=[]), \
                patch("avc.shundo.find_popup_close", return_value=None), \
                patch("avc.shundo.find_fast", side_effect=find_button):
            self.assertFalse(routine._handle_popups(stale))

        self.assertEqual([], taps)

    def test_claim_reward_close_does_not_also_tap_the_screen_center(self):
        taps = []
        first = np.zeros((2712, 1220, 3), dtype=np.uint8)
        map_frame = np.ones_like(first)
        captures = iter((first, first, map_frame))
        claim, close = object(), object()
        routine = object.__new__(CatchRoutine)
        routine.config = CatchConfig()
        routine.device = SimpleNamespace(
            tap=lambda *xy: taps.append(xy),
            screenshot=lambda **_kwargs: next(captures, map_frame),
        )
        routine.stats = SimpleNamespace(last_event="")
        routine.stop_event = threading.Event()
        routine._popup_block_until = 0.0
        routine._popup_scales = (1.0,)
        routine._game_popup_scales = (1.0,)
        routine._claim_scales = (1.0,)
        routine._cancel_btn = None
        routine._popup_weather = None
        routine._popup_speed = None
        routine._maybe_later = None
        routine._popup_autowalk = None
        routine._claim_rewards = claim
        routine._close_btn = close
        routine._close_btn_blue = routine._close_btn_white = None
        routine._ball_in = lambda _frame: None
        routine._bar_visible = lambda frame: frame is map_frame
        routine._interruptible_sleep = lambda _seconds: None

        def find_button(frame, template, **_kwargs):
            if template is claim:
                return [Match(500, 1500, 80, 50, 0.9)]
            if template is close and frame is first:
                return [Match(580, 2450, 60, 60, 0.9)]
            return []

        with patch("avc.catch.find_dialog_buttons", return_value=[]), \
                patch("avc.catch.find_popup_close", return_value=None), \
                patch("avc.catch.find_fast", side_effect=find_button):
            self.assertTrue(routine._handle_popups(first))
        self.assertEqual([(540, 1525), (610, 2480)], taps)


if __name__ == "__main__":
    unittest.main()
