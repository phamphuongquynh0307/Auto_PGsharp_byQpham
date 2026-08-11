import threading
import unittest
from unittest.mock import patch

from avc.coord_shundo import CoordShundoConfig, CoordShundoRoutine
from avc.coord_source import CoordItem, CoordQueue


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
