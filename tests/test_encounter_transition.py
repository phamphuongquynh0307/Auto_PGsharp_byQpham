import threading
import time
import unittest
from types import SimpleNamespace

from avc.catch import CatchRoutine


class EncounterTransitionWaitTests(unittest.TestCase):
    SLOT = (900, 500)
    BALL = (610, 2380)

    def _routine(self, *, configured_delay=0.0):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            encounter_timeout=2.0,
            encounter_transition_grace=2.0,
            engage_miss_grace=0.0,
            engage_miss_frames=2,
            pre_tap_delay=configured_delay,
            pre_tap_min_delay=0.12,
            settle_after_catch=1.0,
        )
        routine.stop_event = threading.Event()
        routine.device = SimpleNamespace(taps=[])
        routine.device.tap = lambda x, y: routine.device.taps.append((x, y))
        routine._jitter = lambda x, y: (x, y)
        routine.double_taps = []
        routine._double_tap = lambda x, y: routine.double_taps.append((x, y))
        routine.sleeps = []
        routine._interruptible_sleep = lambda seconds: routine.sleeps.append(seconds)
        routine._ball_in = lambda _frame: self.BALL
        routine._trace = lambda *_args, **_kwargs: None
        return routine

    def test_zero_setting_keeps_a_short_priming_tap(self):
        routine = self._routine(configured_delay=0.0)

        routine._engage_nearby(self.SLOT)

        self.assertEqual([self.SLOT], routine.device.taps)
        self.assertEqual([0.12], routine.sleeps)
        self.assertEqual([self.SLOT], routine.double_taps)

    def test_longer_user_priming_delay_is_still_honoured(self):
        routine = self._routine(configured_delay=0.4)

        routine._engage_nearby(self.SLOT)

        self.assertEqual([0.4], routine.sleeps)

    def test_wait_uses_fresh_stream_frames_and_returns_as_soon_as_ball_appears(self):
        routine = self._routine()
        frames = iter(("map", "encounter"))
        calls = []
        routine.device.screenshot = lambda **kwargs: calls.append(kwargs) or next(frames)
        routine._ball_in = lambda frame: self.BALL if frame == "encounter" else None
        routine._bar_visible = lambda _frame: False
        routine._scan_slots = lambda _frame: None
        routine._wait_if_paused = lambda: None

        found = routine._wait_for_engaged_encounter()

        self.assertEqual(self.BALL, found)
        self.assertEqual([{"next_frame": True}, {"next_frame": True}], calls)
        self.assertFalse(routine._engage_still_nearby)

    def test_occupied_nearby_after_rejected_tap_retries_without_full_timeout(self):
        routine = self._routine()
        calls = []
        routine.device.screenshot = lambda **kwargs: calls.append(kwargs) or "map"
        routine._ball_in = lambda _frame: None
        routine._bar_visible = lambda _frame: True
        routine._scan_slots = lambda _frame: self.SLOT
        routine._wait_if_paused = lambda: None

        found = routine._wait_for_engaged_encounter()

        self.assertIsNone(found)
        self.assertTrue(routine._engage_still_nearby)
        self.assertEqual(2, len(calls))

    def test_pgsharp_slot_overrides_stale_manual_coordinate_for_the_run(self):
        routine = self._routine()
        routine.config.force_slot = True
        routine.config.nearby_slot = (922, 462)
        routine._ui_nearby_slot = None
        routine._nearby_last_seen_at = None
        routine._force_bottom_cache = (1, 2)
        routine._force_bottom_value = 999
        traces = []
        routine._trace = lambda *args, **_kwargs: traces.append(args)

        routine._remember_ui_nearby_slot((927, 312))

        self.assertEqual((927, 312), routine._effective_nearby_slot())
        self.assertIsNone(routine._force_bottom_cache)
        self.assertIsNone(routine._force_bottom_value)
        self.assertTrue(any(item[0] == "nearby_ui_realign" for item in traces))

    def test_post_catch_settle_drops_old_evidence_before_waiting(self):
        routine = self._routine()
        routine._nearby_last_seen_at = 123.0
        events = []
        routine._interruptible_sleep = lambda seconds: events.append(("sleep", seconds))
        routine.device.screenshot = lambda **kwargs: events.append(("shot", kwargs)) or "new-frame"
        routine._scan_slots = lambda frame: events.append(("scan", frame)) or self.SLOT

        routine._settle_after_encounter()

        self.assertEqual("sleep", events[0][0])
        self.assertEqual(("shot", {"next_frame": True}), events[1])
        self.assertEqual(("scan", "new-frame"), events[2])
        self.assertGreater(routine._nearby_last_seen_at, 123.0)

    def test_zero_settle_still_invalidates_the_old_slot_sighting(self):
        routine = self._routine()
        routine.config.settle_after_catch = 0.0
        routine._nearby_last_seen_at = time.monotonic()

        routine._settle_after_encounter()

        self.assertIsNone(routine._nearby_last_seen_at)


if __name__ == "__main__":
    unittest.main()
