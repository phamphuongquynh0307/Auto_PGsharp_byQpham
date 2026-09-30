import threading
import unittest

from avc.coord_shundo import CoordShundoConfig, CoordShundoRoutine
from avc.coord_source import CoordItem, CoordQueue
from avc.shundo import ShundoStats


class FakeDevice:
    def __init__(self):
        self.actions = []

    def screenshot(self, **kwargs):
        self.actions.append(("screenshot", kwargs))
        return object()

    def tap(self, *point):
        self.actions.append(("tap", point))

    def clear_text(self, count):
        self.actions.append(("clear", count))

    def input_coordinate(self, value):
        self.actions.append(("input", value))

    def back(self):
        self.actions.append(("back",))


class BareCoordRoutine(CoordShundoRoutine):
    def __init__(self, device, coord_queue, config):
        self.device = device
        self.config = config
        self.coord_queue = coord_queue
        self.current_coord = None
        self.stop_event = threading.Event()
        self.stats = type("Stats", (), {"last_event": ""})()

    def _interruptible_sleep(self, _seconds):
        return


class CoordTeleportTests(unittest.TestCase):
    def test_each_coord_supplies_its_own_target_instead_of_saved_settings(self):
        config = CoordShundoConfig(target_ivs=(15, 15, 15), iv_read_tries=1)
        routine = BareCoordRoutine(FakeDevice(), CoordQueue(), config)
        routine.stats = ShundoStats()
        routine.current_coord = CoordItem.from_payload({
            "coordinate": "1.2,3.4", "discordText": "IV57 9/2/15"
        })
        routine._read_iv_stats = lambda _frame: (9, 2, 15)
        self.assertEqual("shundo", routine._grade_encounter(confirmed_frame=object()))

        routine.current_coord = CoordItem.from_payload({
            "coordinate": "5.6,7.8", "discordText": "IV58 10/2/14"
        })
        routine._read_iv_stats = lambda _frame: (10, 2, 14)
        self.assertEqual("shundo", routine._grade_encounter(confirmed_frame=object()))
        self.assertEqual(2, routine.stats.shundos)

    def test_game_iv_mismatch_is_not_a_match_to_discord_coord(self):
        routine = BareCoordRoutine(FakeDevice(), CoordQueue(), CoordShundoConfig(iv_read_tries=1))
        routine.stats = ShundoStats()
        routine.current_coord = CoordItem.from_payload({
            "coordinate": "1.2,3.4", "discordText": "IV57 9/2/15"
        })
        routine._read_iv_stats = lambda _frame: (10, 2, 14)

        self.assertEqual("shiny", routine._grade_encounter(confirmed_frame=object()))
        self.assertEqual((10, 2, 14), routine.stats.last_ivs)

    def test_missing_discord_triplet_falls_back_to_saved_target(self):
        routine = BareCoordRoutine(FakeDevice(), CoordQueue(), CoordShundoConfig(
            target_ivs=(15, 15, 15), iv_read_tries=1))
        routine.stats = ShundoStats()
        routine.current_coord = CoordItem.from_payload({
            "coordinate": "1.2,3.4", "discordText": "IV57% Click for Coords"
        })
        routine._read_iv_stats = lambda _frame: (9, 2, 15)
        self.assertEqual("shiny", routine._grade_encounter(confirmed_frame=object()))

        routine._read_iv_stats = lambda _frame: (15, 15, 15)
        self.assertEqual("shundo", routine._grade_encounter(confirmed_frame=object()))

    def test_unreadable_game_iv_does_not_auto_match_discord_target(self):
        routine = BareCoordRoutine(FakeDevice(), CoordQueue(), CoordShundoConfig(iv_read_tries=1))
        routine.stats = ShundoStats()
        routine.current_coord = CoordItem.from_payload({
            "coordinate": "1.2,3.4", "discordText": "IV57 9/2/15"
        })
        routine._read_iv_stats = lambda _frame: None
        outcome = routine._grade_encounter(confirmed_frame=object())

        self.assertEqual("iv_unknown", outcome)
        self.assertIsNone(routine.stats.last_ivs)

    def test_empty_queue_is_a_separate_idle_outcome(self):
        routine = BareCoordRoutine(FakeDevice(), CoordQueue(), CoordShundoConfig(coord_queue_poll=0))
        self.assertEqual(routine._teleport_next(object()), "coord_idle")
        self.assertEqual(routine.stats.last_event, "coord_idle")

    def test_types_one_coord_and_confirms_teleport(self):
        queue = CoordQueue()
        queue.put(CoordItem.from_payload({
            "coordinate": "-23.587435,-46.654448",
            "url": "https://coord.pokedex100.com/6/abc",
        }))
        device = FakeDevice()
        cfg = CoordShundoConfig(coord_queue_poll=0)
        routine = BareCoordRoutine(device, queue, cfg)

        self.assertIsNone(routine._teleport_next(object()))

        self.assertEqual(device.actions, [
            ("tap", cfg.teleport_xy),
            ("tap", cfg.teleport_input_xy),
            ("clear", 64),
            ("input", "-23.587435,-46.654448"),
            ("back",),
            ("tap", cfg.teleport_ok_xy),
        ])

    def test_starts_directly_at_teleport_row(self):
        queue = CoordQueue()
        queue.put(CoordItem.from_payload({"coordinate": "1.2,3.4", "url": "https://x/1"}))
        device = FakeDevice()
        cfg = CoordShundoConfig(coord_queue_poll=0)
        routine = BareCoordRoutine(device, queue, cfg)

        routine._teleport_next(object())

        taps = [action for action in device.actions if action[0] == "tap"]
        self.assertEqual(taps[0], ("tap", cfg.teleport_xy))


if __name__ == "__main__":
    unittest.main()
