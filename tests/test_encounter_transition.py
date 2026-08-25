import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc.catch import MIN_POST_CATCH_REFRESH, CatchRoutine, CatchStats


class EncounterTransitionWaitTests(unittest.TestCase):
    SLOT = (900, 500)
    BALL = (610, 2380)

    class Clock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            return self.value

        def advance(self, seconds):
            self.value += seconds

    def _routine(self, *, configured_delay=0.0, encounter_timeout=4.0):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            encounter_timeout=encounter_timeout,
            encounter_transition_grace=0.0,
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

    def test_occupied_nearby_retries_only_after_full_timeout_and_fresh_confirmation(self):
        routine = self._routine(encounter_timeout=0.0)
        calls = []
        routine.device.screenshot = lambda **kwargs: calls.append(kwargs) or "map"
        routine._ball_in = lambda _frame: None
        routine._bar_visible = lambda _frame: True
        routine._scan_slots = lambda _frame: self.SLOT
        routine._wait_if_paused = lambda: None

        found = routine._wait_for_engaged_encounter()

        self.assertIsNone(found)
        self.assertTrue(routine._engage_still_nearby)
        self.assertEqual(
            [{"next_frame": True}, {"fresh": True}],
            calls,
        )

    def test_stale_nearby_frames_do_not_end_wait_before_ball_appears(self):
        routine = self._routine()
        stream_frames = iter(("stale-map", "stale-map", "encounter"))
        calls = []

        def screenshot(**kwargs):
            calls.append(kwargs)
            if kwargs.get("fresh"):
                return "transition"
            return next(stream_frames)

        routine.device.screenshot = screenshot
        routine._ball_in = lambda frame: self.BALL if frame == "encounter" else None
        routine._bar_visible = lambda frame: frame == "stale-map"
        routine._scan_slots = lambda frame: self.SLOT if frame == "stale-map" else None
        routine._wait_if_paused = lambda: None

        found = routine._wait_for_engaged_encounter()

        self.assertEqual(self.BALL, found)
        self.assertFalse(routine._engage_still_nearby)
        self.assertEqual([{"next_frame": True}] * 3, calls)

    def test_ball_on_final_fresh_capture_is_caught_in_the_same_cycle(self):
        routine = self._routine(encounter_timeout=0.0)
        calls = []

        def screenshot(**kwargs):
            calls.append(kwargs)
            return "encounter" if kwargs.get("fresh") else "stale-map"

        routine.device.screenshot = screenshot
        routine._ball_in = lambda frame: self.BALL if frame == "encounter" else None
        routine._bar_visible = lambda frame: frame == "stale-map"
        routine._scan_slots = lambda frame: self.SLOT if frame == "stale-map" else None
        routine._wait_if_paused = lambda: None

        found = routine._wait_for_engaged_encounter()

        self.assertEqual(self.BALL, found)
        self.assertFalse(routine._engage_still_nearby)
        self.assertEqual([{"next_frame": True}, {"fresh": True}], calls)

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

    def test_post_catch_settle_ends_early_after_two_changed_frames(self):
        routine = self._routine()
        routine.config.settle_after_catch = 1.2
        routine._nearby_last_seen_at = 123.0
        routine._engaged_slot_signature = np.array([1.0, 0.0], dtype=np.float32)
        frames = iter(("old", "new", "new"))
        clock = self.Clock()
        events = []

        def sleep(seconds):
            events.append(("sleep", seconds))
            clock.advance(seconds)

        def screenshot(**kwargs):
            frame = next(frames)
            events.append(("shot", kwargs, frame))
            clock.advance(0.10)
            return frame

        routine._interruptible_sleep = sleep
        routine.device.screenshot = screenshot
        routine._wait_if_paused = lambda: None
        routine._bar_visible = lambda _frame: True
        routine._scan_slots = lambda _frame: self.SLOT
        routine._slot_visual_signature = lambda frame, _slot: (
            np.array([1.0, 0.0], dtype=np.float32) if frame == "old"
            else np.array([0.0, 1.0], dtype=np.float32)
        )

        with patch("avc.catch.time.monotonic", side_effect=clock):
            routine._settle_after_encounter()

        self.assertEqual(("sleep", MIN_POST_CATCH_REFRESH), events[0])
        self.assertEqual(3, sum(event[0] == "shot" for event in events))
        self.assertLess(clock.value, routine.config.settle_after_catch)
        self.assertIsNone(routine._nearby_last_seen_at)
        self.assertIsNone(routine._engaged_slot_signature)

    def test_zero_settle_cannot_disable_the_measured_refresh_floor(self):
        routine = self._routine()
        routine.config.settle_after_catch = 0.0
        routine._nearby_last_seen_at = time.monotonic()
        clock = self.Clock()
        routine._interruptible_sleep = lambda seconds: (
            routine.sleeps.append(seconds), clock.advance(seconds)
        )

        with patch("avc.catch.time.monotonic", side_effect=clock):
            routine._settle_after_encounter()

        self.assertEqual([MIN_POST_CATCH_REFRESH], routine.sleeps)
        self.assertIsNone(routine._nearby_last_seen_at)

    def test_unknown_old_sprite_uses_the_configured_safety_ceiling(self):
        routine = self._routine()
        routine.config.settle_after_catch = 1.8
        clock = self.Clock()
        routine._interruptible_sleep = lambda seconds: (
            routine.sleeps.append(seconds), clock.advance(seconds)
        )

        with patch("avc.catch.time.monotonic", side_effect=clock):
            routine._settle_after_encounter()

        self.assertAlmostEqual(1.8, sum(routine.sleeps))

    def test_unchanged_slot_waits_until_the_safety_ceiling(self):
        routine = self._routine()
        routine.config.settle_after_catch = 0.6
        routine._engaged_slot_signature = np.array([1.0, 0.0], dtype=np.float32)
        clock = self.Clock()

        def screenshot(**_kwargs):
            clock.advance(0.1)
            return "old"

        def sleep(seconds):
            routine.sleeps.append(seconds)
            clock.advance(seconds)

        routine.device.screenshot = screenshot
        routine._interruptible_sleep = sleep
        routine._wait_if_paused = lambda: None
        routine._bar_visible = lambda _frame: True
        routine._scan_slots = lambda _frame: self.SLOT
        routine._slot_visual_signature = lambda _frame, _slot: np.array(
            [1.0, 0.0], dtype=np.float32,
        )

        with patch("avc.catch.time.monotonic", side_effect=clock):
            routine._settle_after_encounter()

        self.assertGreaterEqual(clock.value, 0.6)
        self.assertLess(clock.value, 0.71)


class CatchRunClassificationTests(unittest.TestCase):
    def _routine(self, cycle_result):
        routine = object.__new__(CatchRoutine)
        routine.config = SimpleNamespace(
            max_catches=0,
            idle_before_autowalk=2,
        )
        routine.stats = CatchStats()
        routine.stop_event = threading.Event()
        routine.pause_event = threading.Event()
        routine._no_balls = False
        routine._no_balls_alerted = False
        routine._feed_pending = False
        routine._idle_streak = 1
        routine._dry_streak = 1
        routine._wait_if_paused = lambda: None
        routine._try_autowalk = lambda: self.fail("AutoWalk must not run during an encounter transition")

        def run_once():
            routine.stats.cycles += 1
            routine._cycle_result = cycle_result
            return False

        routine.run_once = run_once
        return routine

    def test_rejected_encounter_tap_is_not_counted_as_empty(self):
        routine = self._routine("engage_retry")
        events = []

        def on_event(stats, threw):
            events.append((stats.last_event, threw))
            routine.stop_event.set()

        routine.run(on_event)

        self.assertEqual([("engage_retry", False)], events)
        self.assertEqual(0, routine._idle_streak)
        self.assertEqual(0, routine._dry_streak)

    def test_slow_encounter_transition_is_not_counted_as_empty(self):
        routine = self._routine("encounter_wait")
        events = []

        def on_event(stats, threw):
            events.append((stats.last_event, threw))
            routine.stop_event.set()

        routine.run(on_event)

        self.assertEqual([("encounter_wait", False)], events)
        self.assertEqual(0, routine._idle_streak)
        self.assertEqual(0, routine._dry_streak)


if __name__ == "__main__":
    unittest.main()
