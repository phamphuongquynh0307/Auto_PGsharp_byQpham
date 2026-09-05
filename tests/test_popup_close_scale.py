import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchConfig, CatchRoutine
from avc.layout import CALIBRATION_SWEEP
from avc.shundo import ShundoRoutine
from avc.vision import Match, find_popup_close, load_template


def _popup_config():
    return SimpleNamespace(
        popup_threshold=0.7,
        dialog_region=(150, 1150, 950, 500),
        cancel_btn_region=(620, 1480, 310, 220),
    )


class PopupCloseScaleTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
