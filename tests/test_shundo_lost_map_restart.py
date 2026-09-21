"""A missing map must escalate to a relaunch instead of logging "miss" forever."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from avc.shundo import ShundoConfig, ShundoRoutine, ShundoStats


def _routine_without_map(cycles: int) -> ShundoRoutine:
    """A routine whose every capture shows neither the '@' anchor nor the map hierarchy."""
    routine = ShundoRoutine.__new__(ShundoRoutine)
    routine.config = ShundoConfig(no_map_restart_cycles=cycles)
    routine.stats = ShundoStats()
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine.device = SimpleNamespace(screenshot=Mock(return_value="frame"))
    routine._teleport_blocked = False
    routine._no_map_streak = 0
    routine._pending_nearby = None
    routine._ensure_calibrated = Mock()
    routine._wait_if_paused = Mock()
    routine._interruptible_sleep = Mock()
    routine._drain_popups = Mock(return_value=False)
    routine._encounter_visible = Mock(return_value=False)
    routine._anchor_in = Mock(return_value=None)
    routine._ui_map_visible = Mock(return_value=False)
    return routine


class LostMapRestartTests(unittest.TestCase):
    def test_missing_map_escalates_from_miss_to_nomap(self):
        routine = _routine_without_map(cycles=3)

        self.assertEqual("miss", routine.run_once())
        self.assertEqual("miss", routine.run_once())
        # Third consecutive mapless cycle spends the budget and asks for a relaunch.
        self.assertEqual("nomap", routine.run_once())

    def test_streak_resets_once_the_map_comes_back(self):
        routine = _routine_without_map(cycles=3)
        self.assertEqual("miss", routine.run_once())
        self.assertEqual("miss", routine.run_once())

        # Map is back: the cycle proceeds to the teleport step and the streak is cleared,
        # so a later transient blip cannot inherit the old count and relaunch immediately.
        routine.stats.checked = 1   # past the first cycle, so no initial-Nearby detour
        routine._anchor_in = Mock(return_value=(100, 200))
        routine._teleport_next = Mock(return_value="coord_idle")
        self.assertEqual("coord_idle", routine.run_once())
        self.assertEqual(0, routine._no_map_streak)

        routine._anchor_in = Mock(return_value=None)
        self.assertEqual("miss", routine.run_once())

    def test_backs_off_the_poll_rate_while_the_map_is_gone(self):
        routine = _routine_without_map(cycles=20)
        for _ in range(8):
            routine.run_once()

        waits = [call.args[0] for call in routine._interruptible_sleep.call_args_list]
        # First looks stay responsive for a normal loading blip; the rest stop hammering adb.
        self.assertEqual([routine.config.poll_interval] * 5, waits[:5])
        self.assertEqual([routine.config.idle_poll] * 3, waits[5:])

    def test_relaunch_is_not_gated_on_spawn_timeout(self):
        """Discord Coord runs with spawn_timeout=0 and must still recover from a dead game."""
        routine = ShundoRoutine.__new__(ShundoRoutine)
        routine.config = ShundoConfig(spawn_timeout=0.0)
        routine.stats = ShundoStats()
        routine.stop_event = threading.Event()
        routine.pause_event = threading.Event()
        routine._wait_if_paused = Mock()
        routine._restart_game = Mock(return_value=True)
        outcomes = iter(("nomap", "blocked"))
        events = []

        def run_once():
            outcome = next(outcomes)
            if outcome == "blocked":
                routine.stop_event.set()
            routine.stats.last_event = outcome
            return outcome

        routine.run_once = run_once
        routine.run(lambda stats, outcome: events.append(outcome))

        routine._restart_game.assert_called_once()
        self.assertEqual(["nomap", "nomap_restarting", "restarted", "blocked"], events)


if __name__ == "__main__":
    unittest.main()
