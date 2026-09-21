import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from avc.shundo import ShundoConfig, ShundoRoutine, ShundoStats


def _restart_waits_for_map_and_clears_stale_targets():
    routine = ShundoRoutine.__new__(ShundoRoutine)
    routine.config = ShundoConfig(restart_delay=7.5)
    routine.device = SimpleNamespace(
        _run=Mock(side_effect=[
            "",  # force-stop
            "com.nianticlabs.pokemongo/com.nianticproject.holoholo.libholoholo.unity.UnityMainActivity\n",
            "Starting: Intent ...",  # explicit activity launch
        ]),
        screenshot=Mock(side_effect=["loading", "map"]),
    )
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._wait_if_paused = Mock()
    routine._interruptible_sleep = Mock()
    routine._anchor_in = Mock(side_effect=[None, (100, 200)])
    routine._release_pending = Mock()
    routine._anchor_cache = (1, 2)
    routine._feed_cache = ((1, 2), (3, 4), (5, 6))
    routine._nearby_column_x = 1
    routine._ui_state_cache = "old"

    assert routine._restart_game() is True
    assert routine.device._run.call_args_list[0].args[0][:3] == ["shell", "am", "force-stop"]
    assert routine.device._run.call_args_list[1].args[0][:4] == [
        "shell", "cmd", "package", "resolve-activity"]
    assert routine.device._run.call_args_list[2].args[0][:3] == ["shell", "am", "start"]
    assert routine.device.screenshot.call_count == 2
    routine._interruptible_sleep.assert_any_call(7.5)
    assert routine._feed_cache is None
    routine._release_pending.assert_called_once()


def _spawn_timeout_relaunches_before_next_check():
    routine = ShundoRoutine.__new__(ShundoRoutine)
    routine.config = ShundoConfig(spawn_timeout=200)
    routine.stats = ShundoStats()
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._wait_if_paused = Mock()
    routine._restart_game = Mock(return_value=True)
    outcomes = iter(("nospawn", "blocked"))
    events = []

    def run_once():
        outcome = next(outcomes)
        if outcome == "blocked":
            routine.stats.checked += 1
            routine.stop_event.set()
        routine.stats.last_event = outcome
        return outcome

    routine.run_once = run_once
    routine.run(lambda stats, outcome: events.append(outcome))

    routine._restart_game.assert_called_once()
    assert events == ["nospawn", "spawn_restarting", "restarted", "blocked"]


class SpawnRestartTests(unittest.TestCase):
    def test_relaunch_waits_for_map(self):
        _restart_waits_for_map_and_clears_stale_targets()

    def test_spawn_timeout_relaunches(self):
        _spawn_timeout_relaunches_before_next_check()

    def test_launcher_falls_back_to_monkey_when_activity_cannot_be_resolved(self):
        routine = ShundoRoutine.__new__(ShundoRoutine)
        routine.device = SimpleNamespace(_run=Mock(side_effect=["No activity found", "Events injected: 1"]))

        self.assertTrue(routine._launch_game())
        self.assertEqual(["shell", "monkey", "-p"],
                         routine.device._run.call_args_list[1].args[0][:3])
