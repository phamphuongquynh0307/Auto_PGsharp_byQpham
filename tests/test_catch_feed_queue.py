import threading
import unittest
from types import SimpleNamespace

from avc.catch import CatchRoutine


class FakeDevice:
    def __init__(self):
        self.taps = []
        self.screenshot_calls = 0

    def screenshot(self, **_kwargs):
        self.screenshot_calls += 1
        return object()

    def tap(self, x, y):
        self.taps.append((x, y))


def bare_feed_routine():
    routine = object.__new__(CatchRoutine)
    routine.device = FakeDevice()
    routine.config = SimpleNamespace(
        use_feed_bar=True,
        feed_teleport_wait=0.0,
        respect_cooldown=False,
        idle_poll=0.0,
    )
    routine._teleport_blocked = False
    routine._feed_pending = False
    routine._feed_pending_at = 0.0
    routine._feed_seen = True
    routine._rss = object()
    routine._handle = object()
    routine._cancelled_dialog = False
    routine.stop_event = threading.Event()
    routine._slot_in = lambda _frame: (900, 500)
    routine._feed_slot_in = lambda _frame: (580, 364)
    routine._interruptible_sleep = lambda _seconds: None
    routine._drain_popups = lambda _frame=None: False
    routine._poll = lambda _predicate, _timeout: None
    routine._wait_if_paused = lambda: None
    routine._occupied_slot_in = lambda _frame: (900, 500)
    routine._occupied_slot_ui = lambda: None
    routine._occupied_slot_fresh = lambda: None
    routine._trace = lambda *_args, **_kwargs: None
    return routine


class CatchFeedQueueTests(unittest.TestCase):
    def test_feed_is_tapped_only_once_while_its_spawn_is_pending(self):
        routine = bare_feed_routine()

        first = routine._tap_feed_spawn()
        second = routine._tap_feed_spawn()

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(routine._feed_pending)
        self.assertEqual([(580, 364)], routine.device.taps)

    def test_pending_feed_unlocks_only_after_encounter_was_handled(self):
        routine = bare_feed_routine()
        routine._feed_pending = True
        routine._feed_pending_at = 1.0
        routine._run_encounter = lambda _ball: True

        threw = routine._finish_encounter((610, 2380))

        self.assertTrue(threw)
        self.assertFalse(routine._feed_pending)

    def test_feed_call_itself_waits_until_nearby_really_has_a_pokemon(self):
        routine = bare_feed_routine()
        states = iter((None, None, (900, 500)))
        routine._occupied_slot_in = lambda _frame: next(states)

        tapped = routine._tap_feed_spawn()

        self.assertTrue(tapped)
        self.assertTrue(routine._feed_pending)
        self.assertEqual([(580, 364)], routine.device.taps)
        # One frame checks the map before tapping Feed, then three fresh stream states are
        # consumed while this same call waits for Nearby. It never returns to tap Feed again.
        self.assertGreaterEqual(routine.device.screenshot_calls, 4)

    def test_failed_encounter_does_not_unlock_next_feed_item(self):
        routine = bare_feed_routine()
        routine._feed_pending = True
        routine._feed_pending_at = 1.0
        routine._run_encounter = lambda _ball: False

        threw = routine._finish_encounter((610, 2380))

        self.assertFalse(threw)
        self.assertTrue(routine._feed_pending)


def empty_nearby_routine(*, use_feed_bar=True, idle_streak=1):
    """A routine parked in run_once's "Nearby is empty" branch, with both escapes recording."""
    routine = object.__new__(CatchRoutine)
    routine.device = FakeDevice()
    routine.config = SimpleNamespace(
        use_feed_bar=use_feed_bar, force_slot=False, use_ui_dump=False,
        min_catch_interval=0, anchor_timeout=0.0, feed_after_idle=1,
        menu_open_wait=0.0, autowalk_wait=0.0, idle_poll=0.0, trace_timing=False,
    )
    routine.stats = SimpleNamespace(cycles=0, autowalks=0)
    routine.stop_event = threading.Event()
    routine._idle_streak = idle_streak
    routine._feed_pending = False
    routine._teleport_blocked = False
    routine._ui_empty_confirmed = False
    routine._last_engage_at = 0.0
    routine._ensure_calibrated = lambda: None
    routine._drain_popups = lambda _frame=None: False
    routine._cooldown_left = lambda: 0.0
    routine._is_out_of_balls = lambda _frame: False
    routine._ball_in = lambda _frame, **_kw: None
    routine._occupied_slot_in = lambda _frame: None
    routine._occupied_slot_ui = lambda: None
    routine._occupied_slot_fresh = lambda: None
    routine._poll = lambda _predicate, _timeout: None
    routine._ensure_menu_open = lambda _frame: False
    routine._interruptible_sleep = lambda _seconds: None
    routine._trace = lambda *_args, **_kwargs: None
    routine._mark = lambda _name: None
    routine._flush_phases = lambda _outcome: None

    calls = []
    routine._tap_feed_spawn = lambda: (calls.append("feed"), True)[1]
    routine._tap_autowalk_paused = lambda: (calls.append("autowalk"), True)[1]
    return routine, calls


class EmptyNearbyPriorityTests(unittest.TestCase):
    """With the feed on, a dry cycle must reach the feed. AutoWalk used to take the branch
    first and return, so a paused row — which is the normal state on a dry cycle — meant the
    feed was never read at all, however many Pokémon it was listing."""

    def test_feed_is_tried_before_autowalk_when_enabled(self):
        routine, calls = empty_nearby_routine()

        routine.run_once()

        self.assertEqual(["feed"], calls)

    def test_autowalk_still_catches_the_cycle_the_feed_declines(self):
        routine, calls = empty_nearby_routine()
        routine._tap_feed_spawn = lambda: (calls.append("feed"), False)[1]

        routine.run_once()

        self.assertEqual(["feed", "autowalk"], calls)
        self.assertEqual(1, routine.stats.autowalks)

    def test_feed_off_leaves_autowalk_exactly_as_it_was(self):
        routine, calls = empty_nearby_routine(use_feed_bar=False)
        # _tap_feed_spawn returns at its own use_feed_bar guard in the real routine.
        routine._tap_feed_spawn = lambda: False

        routine.run_once()

        self.assertEqual(["autowalk"], calls)

    def test_first_empty_read_is_not_worth_a_teleport(self):
        routine, calls = empty_nearby_routine(idle_streak=0)

        routine.run_once()

        self.assertEqual(["autowalk"], calls)


if __name__ == "__main__":
    unittest.main()
