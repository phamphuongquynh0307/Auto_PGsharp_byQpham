import json
import unittest
import urllib.request

from avc.coord_source import COORD_BRIDGE_PORT, CoordBridge, CoordItem, CoordQueue


class CoordQueueTests(unittest.TestCase):
    def test_validates_and_deduplicates_source_links(self):
        queue = CoordQueue()
        item = CoordItem.from_payload({
            "coordinate": "32.978615,-96.551351",
            "pokemon": "Vulpix",
            "url": "https://coord.pokedex100.com/6/example",
        })
        self.assertTrue(queue.put(item))
        self.assertFalse(queue.put(item))
        self.assertEqual(queue.get(), item)
        self.assertIsNone(queue.get())

    def test_rejects_out_of_range_coordinate(self):
        with self.assertRaises(ValueError):
            CoordItem.from_payload({"coordinate": "92.0,10.0"})

    def test_keeps_clipboard_source_annotation(self):
        item = CoordItem.from_payload({
            "coordinate": "10.762622,106.660172",
            "source": "Discord Pokedex100",
            "note": "Từ Discord Pokedex100",
        })
        self.assertEqual(item.source, "Discord Pokedex100")
        self.assertEqual(item.note, "Từ Discord Pokedex100")

    def test_completed_counter_and_clear_define_a_session(self):
        queue = CoordQueue()
        self.assertEqual(queue.completed_count(), 0)
        self.assertEqual(queue.mark_completed(), 1)
        self.assertEqual(queue.mark_completed(), 2)
        queue.clear()
        self.assertEqual(queue.completed_count(), 0)


class CoordBridgeTests(unittest.TestCase):
    def test_default_port_is_separate_from_wireless_adb(self):
        self.assertEqual(8766, COORD_BRIDGE_PORT)

    def setUp(self):
        self.queue = CoordQueue()
        self.bridge = CoordBridge(self.queue, port=0)
        self.port = self.bridge.start()

    def tearDown(self):
        self.bridge.stop()

    def test_extension_payload_enters_queue(self):
        payload = json.dumps({
            "coordinate": "-23.587435,-46.654448",
            "pokemon": "Vulpix",
            "url": "https://coord.pokedex100.com/6/abc",
            "discordChannelUrl": "https://discord.com/channels/1/2",
        }).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/coords",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            body = json.load(response)
        self.assertTrue(body["ok"])
        self.assertEqual(body["queued"], 1)
        self.assertEqual(self.queue.get().coordinate, "-23.587435,-46.654448")

    def test_health_reports_completed_checks_and_session_reset(self):
        self.queue.mark_completed()
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as response:
            health = json.load(response)
        self.assertEqual(health["completed"], 1)

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/session",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            reset = json.load(response)
        self.assertEqual(reset, {"ok": True, "queued": 0, "completed": 0})
        self.assertEqual(self.queue.completed_count(), 0)


if __name__ == "__main__":
    unittest.main()
