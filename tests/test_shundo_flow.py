import threading
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, patch

from avc.shundo import ShundoRoutine, ShundoStats


class FakeDevice:
    def __init__(self):
        self.double_taps = []
        self.regular_taps = []
        self.adb_taps = []
        self.back_presses = 0
        self.screenshot_calls = []
        self.control_closed = False

    def screenshot(self, **kwargs):
        self.screenshot_calls.append(kwargs)
        return object()

    def double_tap(self, x, y):
        self.double_taps.append((x, y))

    def tap(self, x, y):
        self.regular_taps.append((x, y))

    def close_control(self):
        self.control_closed = True

    def adb_tap(self, x, y):
        self.adb_taps.append((x, y))

    def back(self):
        self.back_presses += 1


def bare_routine():
    routine = object.__new__(ShundoRoutine)
    routine.device = FakeDevice()
    routine.config = SimpleNamespace(
        encounter_open_wait=3.0,
        encounter_no_answer_attempts=2,
        teleport_wait=0.0,
        bar_clear_timeout=0.0,
        spawn_wait_log=20.0,
        spawn_timeout=0.0,
        flee_taps=3,
        flee_gap_ms=0,
        flee_map_wait=0.5,
        flee_xy=(120, 170),
        poll_interval=0.0,
        enc_berry_radius=95,
        enc_berry_min_fill=0.06,
        layout=SimpleNamespace(s=1.0),
    )
    routine.stats = ShundoStats()
    routine._pending_no_answers = 0
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._encounter_visible = lambda _frame: False
    routine._raw_target_in_bar = lambda _frame: (900, 500)
    routine._interruptible_sleep = lambda _seconds: None
    return routine


class ShundoAnswerTests(unittest.TestCase):
    def test_berry_button_is_the_only_encounter_signal(self):
        routine = bare_routine()
        routine._anchor_in = lambda _frame: (1100, 1166)
        detector = ShundoRoutine._encounter_visible.__get__(routine, ShundoRoutine)

        with patch("avc.shundo.find_berry_button", return_value=(163, 2460)) as berry:
            self.assertTrue(detector(object()))
        berry.assert_called_once_with(
            ANY,
            scale=1.0,
            radius=95,
            min_berry_fill=0.06,
        )

    def test_timeout_is_a_miss_and_does_not_advance_checked_count(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("miss", outcome)
        self.assertEqual(0, routine.stats.checked)
        self.assertEqual([(900, 500)], routine.device.double_taps)

    def test_second_confirmed_timeout_is_treated_as_silent_non_shiny_block(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: None

        first = routine._attempt_nearby((900, 500))
        second = routine._attempt_nearby((900, 500))

        self.assertEqual("miss", first)
        self.assertEqual("blocked", second)
        self.assertEqual(1, routine.stats.checked)

    def test_visible_blocked_answer_advances_checked_count(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: "blocked"

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, routine.stats.checked)

    def test_pending_miss_returns_before_the_next_feed_can_be_tapped(self):
        routine = bare_routine()
        routine._teleport_blocked = False
        routine._pending_nearby = (900, 500)
        routine._ensure_calibrated = lambda: None
        routine._drain_popups = lambda _frame: False
        routine._attempt_nearby = lambda _target: "miss"
        routine._feed_slot_in = lambda _frame: self.fail(
            "QuickSniper feed must not be read while the current entry is pending"
        )

        outcome = routine.run_once()

        self.assertEqual("miss", outcome)
        self.assertEqual((900, 500), routine._pending_nearby)

    def test_definitive_pending_answer_releases_the_feed_for_next_cycle(self):
        routine = bare_routine()
        routine._teleport_blocked = False
        routine._pending_nearby = (900, 500)
        routine._ensure_calibrated = lambda: None
        routine._drain_popups = lambda _frame: False
        routine._attempt_nearby = lambda _target: "blocked"

        outcome = routine.run_once()

        self.assertEqual("blocked", outcome)
        self.assertIsNone(routine._pending_nearby)

    def test_continuously_occupied_bar_does_not_stall_after_flee(self):
        routine = bare_routine()
        routine._teleport_blocked = False
        routine._pending_nearby = None
        routine._on_waiting = None
        routine.stats.checked = 1
        routine._nearby_presence_streak = 7
        routine._ensure_calibrated = lambda: None
        routine._drain_popups = lambda _frame=None: False
        routine._anchor_in = lambda _frame: (1100, 1166)
        routine._feed_slot_in = lambda _frame: (580, 364)
        # A short/fast teleport can replace one occupied list with another without
        # exposing an empty frame.
        routine._raw_target_in_bar = lambda _frame: (1100, 523)
        streaks_at_load = []
        routine._target_in_bar = lambda _frame: (
            streaks_at_load.append(routine._nearby_presence_streak) or (1100, 523)
        )
        routine._attempt_nearby = lambda _target: "blocked"

        with patch("avc.shundo.time.monotonic", side_effect=(0.0, 1.0, 1.1)):
            outcome = routine.run_once()

        self.assertEqual("blocked", outcome)
        self.assertEqual([(580, 364)], routine.device.regular_taps)
        self.assertEqual([0], streaks_at_load)


class ShundoFleeTests(unittest.TestCase):
    def test_flee_taps_then_waits_for_two_fresh_frames_without_berry(self):
        routine = bare_routine()
        states = iter((True, False, False))
        routine._encounter_visible = lambda _frame: next(states)

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertTrue(routine.device.control_closed)
        self.assertEqual([(120, 170)], routine.device.adb_taps)
        self.assertEqual(0, routine.device.back_presses)

    def test_flee_accepts_already_stable_exit_without_sending_any_action(self):
        routine = bare_routine()

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertEqual([], routine.device.adb_taps)
        self.assertEqual(0, routine.device.back_presses)
        self.assertTrue(routine.device.screenshot_calls)
        self.assertTrue(all(call.get("fresh") is True for call in routine.device.screenshot_calls))

    def test_flee_falls_back_to_android_back_when_tap_is_ignored(self):
        routine = bare_routine()
        states = iter((True, True, False, False))
        routine._encounter_visible = lambda _frame: next(states)

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertEqual([(120, 170)], routine.device.adb_taps)
        self.assertEqual(1, routine.device.back_presses)


if __name__ == "__main__":
    unittest.main()
