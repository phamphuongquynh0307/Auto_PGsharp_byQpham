import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import CatchRoutine
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
        self.assertEqual(CALIBRATION_SWEEP, close.call_args.kwargs["fallback_scales"])


if __name__ == "__main__":
    unittest.main()
