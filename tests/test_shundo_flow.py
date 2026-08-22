import threading
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, patch

from avc.shundo import KEEP_PENDING, ShundoRoutine, ShundoStats


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
        encounter_no_answer_attempts=1,
        require_confirmed_check=False,
        nearby_recheck_attempts=6,
        nearby_presence_frames=2,
        nearby_recheck_gap=0.0,
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
        iv_read_tries=1,
        target_ivs=(15, 15, 15),
        layout=SimpleNamespace(s=1.0),
    )
    routine.stats = ShundoStats()
    routine._pending_no_answers = 0
    routine._pending_no_target = 0
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._encounter_visible = lambda _frame: False
    routine._anchor_in = lambda _frame: (1100, 1166)
    routine._raw_target_in_bar = lambda _frame: (900, 500)
    routine._interruptible_sleep = lambda _seconds: None
    return routine


class PendingEntryRecheckTests(unittest.TestCase):
    """An entry the crisp capture cannot see is looked at again — but not forever.

    The stream and the one-shot capture disagree for seconds at a time (measured live: 12
    looks over 15s before the bar read occupied again), so re-looking is right. An entry that
    despawned never comes back, though, and the old code had no way out of that.
    """

    def unseen_routine(self):
        routine = bare_routine()
        routine._raw_target_in_bar = lambda _frame: None
        routine._poll = lambda _predicate, _timeout: None
        return routine

    def test_an_unseen_entry_is_looked_at_again_without_tapping(self):
        routine = self.unseen_routine()

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("recheck", outcome)
        self.assertEqual([], routine.device.double_taps)   # no QuickSniper item spent
        self.assertEqual(0, routine.stats.checked)

    def test_the_recheck_gives_up_instead_of_looping_forever(self):
        routine = self.unseen_routine()

        outcomes = [routine._attempt_nearby((900, 500)) for _ in range(6)]

        self.assertEqual(["recheck"] * 5 + ["lost"], outcomes)
        self.assertEqual([], routine.device.double_taps)

    def test_giving_up_releases_the_entry_so_the_feed_advances(self):
        self.assertIn("recheck", KEEP_PENDING)
        self.assertIn("miss", KEEP_PENDING)
        self.assertNotIn("lost", KEEP_PENDING)

    def test_the_budget_refills_when_the_entry_comes_back(self):
        routine = bare_routine()
        seen = iter([None, None, (900, 500)])
        routine._raw_target_in_bar = lambda _frame: next(seen)
        routine._poll = lambda _predicate, _timeout: None

        outcomes = [routine._attempt_nearby((900, 500)) for _ in range(3)]

        self.assertEqual(["recheck", "recheck", "blocked"], outcomes)
        self.assertEqual(0, routine._pending_no_target)
        self.assertEqual([(900, 500)], routine.device.double_taps)


class ShundoAnswerTests(unittest.TestCase):
    def test_nearby_presence_confirmation_reads_config_without_name_error(self):
        routine = bare_routine()
        routine._nearby_presence_streak = 0
        routine._nearby_last_y = None
        routine.config.nearby_presence_frames = 3
        routine.config.s = lambda value: value
        routine._raw_target_in_bar = lambda _frame: (900, 500)

        outcomes = [routine._target_in_bar(object()) for _ in range(3)]

        self.assertEqual([None, None, (900, 500)], outcomes)

    def test_nearby_presence_allows_adjacent_scanner_rows(self):
        routine = bare_routine()
        routine._nearby_presence_streak = 0
        routine._nearby_last_y = None
        routine.config.nearby_presence_frames = 3
        routine.config.s = lambda value: value
        ys = iter((500, 540, 500))
        routine._raw_target_in_bar = lambda _frame: (900, next(ys))

        outcomes = [routine._target_in_bar(object()) for _ in range(3)]

        self.assertEqual([None, None, (900, 500)], outcomes)

    def test_confirmed_mode_keeps_same_entry_when_post_tap_image_is_ambiguous(self):
        routine = bare_routine()
        routine.config.require_confirmed_check = True
        routine.config.encounter_no_answer_attempts = 2
        routine._anchor_in = lambda _frame: (1100, 1166)
        routine._blocked_toast_in = lambda _frame: False
        routine._poll = lambda _predicate, _timeout: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("miss", outcome)
        self.assertEqual(0, routine.stats.checked)
        self.assertEqual([{"fresh": True}, {"fresh": True}], routine.device.screenshot_calls)

    def test_confirmed_mode_accepts_two_real_no_answer_checks_as_non_shiny(self):
        routine = bare_routine()
        routine.config.require_confirmed_check = True
        routine.config.encounter_no_answer_attempts = 2
        routine._anchor_in = lambda _frame: (1100, 1166)
        routine._blocked_toast_in = lambda _frame: False
        routine._poll = lambda _predicate, _timeout: None

        first = routine._attempt_nearby((900, 500))
        second = routine._attempt_nearby((900, 500))

        self.assertEqual(("miss", "blocked"), (first, second))
        self.assertEqual(1, routine.stats.checked)
        self.assertEqual([(900, 500), (900, 500)], routine.device.double_taps)

    def test_confirmed_mode_accepts_toast_visible_on_post_tap_image(self):
        routine = bare_routine()
        routine.config.require_confirmed_check = True
        routine._anchor_in = lambda _frame: (1100, 1166)
        routine._blocked_toast_in = lambda _frame: True
        routine._poll = lambda _predicate, _timeout: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, routine.stats.checked)

    def test_confirmed_mode_rejects_a_stream_only_blocked_answer(self):
        routine = bare_routine()
        routine.config.require_confirmed_check = True
        routine.config.encounter_no_answer_attempts = 2
        routine._anchor_in = lambda _frame: (1100, 1166)
        routine._blocked_toast_in = lambda _frame: False
        routine._poll = lambda _predicate, _timeout: "blocked"

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("miss", outcome)
        self.assertEqual(0, routine.stats.checked)
        self.assertEqual([{"fresh": True}, {"fresh": True}], routine.device.screenshot_calls)

    def test_confirmed_mode_never_gives_up_an_unseen_pending_entry(self):
        routine = bare_routine()
        routine.config.require_confirmed_check = True
        routine._raw_target_in_bar = lambda _frame: None

        outcomes = [routine._attempt_nearby((900, 500)) for _ in range(20)]

        self.assertEqual(["recheck"] * 20, outcomes)
        self.assertEqual(0, routine.stats.checked)

    def test_encounter_requires_berry_and_ball_selector(self):
        routine = bare_routine()
        routine._anchor_in = lambda _frame: (1100, 1166)
        detector = ShundoRoutine._encounter_visible.__get__(routine, ShundoRoutine)

        with (patch("avc.shundo.find_berry_button", return_value=(163, 2460)) as berry,
              patch("avc.shundo.find_enc_ball", return_value=(1060, 2440)) as ball):
            self.assertTrue(detector(object()))
        berry.assert_called_once_with(
            ANY,
            scale=1.0,
            radius=95,
            min_berry_fill=0.06,
        )
        ball.assert_called_once_with(ANY, scale=1.0)

    def test_map_berry_lookalike_is_not_an_encounter_without_ball_selector(self):
        routine = bare_routine()
        detector = ShundoRoutine._encounter_visible.__get__(routine, ShundoRoutine)

        with (patch("avc.shundo.find_berry_button", return_value=(163, 2460)),
              patch("avc.shundo.find_enc_ball", return_value=None)):
            self.assertFalse(detector(object()))

    def test_one_confirmed_no_answer_is_the_final_blocked_result(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, routine.stats.checked)
        self.assertEqual([(900, 500)], routine.device.double_taps)

    def test_blocked_result_does_not_double_tap_the_same_pokemon_again(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, routine.stats.checked)
        self.assertEqual([(900, 500)], routine.device.double_taps)

    def test_visible_blocked_answer_advances_checked_count(self):
        routine = bare_routine()
        routine._poll = lambda _predicate, _timeout: "blocked"

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, routine.stats.checked)

    def test_stream_shiny_candidate_needs_a_fresh_encounter_confirmation(self):
        routine = bare_routine()
        states = iter((False, False))
        routine._encounter_visible = lambda _frame: next(states)
        routine._poll = lambda _predicate, _timeout: "shiny"

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("miss", outcome)
        self.assertEqual(0, routine.stats.checked)
        self.assertEqual(0, routine.stats.shinies)
        self.assertEqual([{"fresh": True}, {"fresh": True}], routine.device.screenshot_calls)

    def test_freshly_confirmed_stream_candidate_is_counted_as_shiny(self):
        routine = bare_routine()
        states = iter((False, True))
        routine._encounter_visible = lambda _frame: next(states)
        routine._poll = lambda _predicate, _timeout: "shiny"
        routine._read_iv_stats = lambda _frame: (15, 15, 14)

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("shiny", outcome)
        self.assertEqual(1, routine.stats.checked)
        self.assertEqual(1, routine.stats.shinies)

    def test_exact_configured_iv_is_the_target_result(self):
        routine = bare_routine()
        routine.config.target_ivs = (15, 14, 15)
        routine._encounter_visible = lambda _frame: True
        routine._read_iv_stats = lambda _frame: (15, 14, 15)

        outcome = routine._grade_encounter(confirmed_frame=object())

        self.assertEqual("shundo", outcome)
        self.assertEqual((15, 14, 15), routine.stats.last_ivs)
        self.assertEqual(1, routine.stats.shundos)

    def test_exact_iv_reader_uses_pgsharp_view_text(self):
        routine = bare_routine()
        routine.config.target_ivs = (15, 15, 14)
        routine.device.ui_dump = lambda: (
            '<hierarchy><node resource-id="x:id/hl_ec_sum_stats" text="15/15/14" '
            'bounds="[0,0][100,50]" /></hierarchy>'
        )

        self.assertEqual((15, 15, 14), routine._read_iv_stats(object()))

    def test_different_iv_is_a_plain_shiny(self):
        routine = bare_routine()
        routine.config.target_ivs = (15, 15, 14)
        routine._encounter_visible = lambda _frame: True
        routine._read_iv_stats = lambda _frame: (14, 15, 15)

        outcome = routine._grade_encounter(confirmed_frame=object())

        self.assertEqual("shiny", outcome)
        self.assertEqual((14, 15, 15), routine.stats.last_ivs)

    def test_unreadable_iv_is_not_fled_as_a_mismatch(self):
        routine = bare_routine()
        routine.config.target_ivs = (15, 15, 14)
        routine._encounter_visible = lambda _frame: True
        routine._read_iv_stats = lambda _frame: None

        outcome = routine._grade_encounter(confirmed_frame=object())

        self.assertEqual("iv_unknown", outcome)
        self.assertIsNone(routine.stats.last_ivs)

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
        routine.config.require_confirmed_check = True
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
    def test_flee_uses_low_latency_tap_then_one_fresh_map_confirmation(self):
        routine = bare_routine()
        states = iter((False,))
        routine._encounter_visible = lambda _frame: next(states)

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertFalse(routine.device.control_closed)
        self.assertEqual([(120, 170)], routine.device.regular_taps)
        self.assertEqual(1, len(routine.device.screenshot_calls))
        self.assertEqual(0, routine.device.back_presses)

    def test_flee_falls_back_to_two_outside_frames_when_anchor_is_not_visible(self):
        routine = bare_routine()
        routine._anchor_in = lambda _frame: None

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertEqual([(120, 170)], routine.device.regular_taps)
        self.assertEqual(0, routine.device.back_presses)
        self.assertEqual(2, len(routine.device.screenshot_calls))
        self.assertTrue(all(call.get("fresh") is True for call in routine.device.screenshot_calls))

    def test_flee_falls_back_to_android_back_when_tap_is_ignored(self):
        routine = bare_routine()
        states = iter((True, False))
        routine._encounter_visible = lambda _frame: next(states)

        fled = routine._flee_to_map()

        self.assertTrue(fled)
        self.assertEqual([(120, 170)], routine.device.regular_taps)
        self.assertEqual(1, routine.device.back_presses)


if __name__ == "__main__":
    unittest.main()
