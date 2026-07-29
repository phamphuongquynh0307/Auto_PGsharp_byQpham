import threading
import unittest
from types import SimpleNamespace

from avc.catch import CatchRoutine


class FakeDevice:
    def __init__(self):
        self.taps = []

    def screenshot(self, **_kwargs):
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

    def test_failed_encounter_does_not_unlock_next_feed_item(self):
        routine = bare_feed_routine()
        routine._feed_pending = True
        routine._feed_pending_at = 1.0
        routine._run_encounter = lambda _ball: False

        threw = routine._finish_encounter((610, 2380))

        self.assertFalse(threw)
        self.assertTrue(routine._feed_pending)


if __name__ == "__main__":
    unittest.main()
