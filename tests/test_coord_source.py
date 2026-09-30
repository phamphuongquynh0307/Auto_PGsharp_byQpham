import json
import unittest
import urllib.request

from avc.coord_source import COORD_BRIDGE_PORT, CoordBridge, CoordItem, CoordQueue, parse_exact_ivs


class CoordQueueTests(unittest.TestCase):
    def test_discord_exact_iv_is_carried_with_the_coordinate(self):
        item = CoordItem.from_payload({
            "coordinate": "10.762622,106.660172",
            "discordText": "Pokedex100 · IV57 9/2/15 · CP 778 · Click for Coords",
        })
        self.assertEqual((9, 2, 15), item.iv_stats)

    def test_pokedex100_labelled_triplet_from_the_whole_message(self):
        # Real post text: the IV line is in the message body, the link is in the embed below.
        text = (":flag_jp: Geodude :74::shiny: IV66 (A1/D14/S15) CP298 L9 ♀ /WXL (DSP in 34m)"
                " - Kamigyo Ward, Kyoto\nGreat League Rank 1\nEvolution: Golem L19.0 CP1498\n"
                "Cost: Stardust 32000, Candy 36, Candy XL 0\nClick for Coords | Donor | Support Us")
        self.assertEqual((1, 14, 15), parse_exact_ivs(text))
        self.assertEqual((12, 15, 14), parse_exact_ivs(
            "🇺🇸 Sewaddle 🍃 IV91 (A12/D15/S14) CP213 L8 ♂ / (DSP in 26m) - Highland Park"))

    def test_percentage_alone_does_not_identify_three_stats(self):
        self.assertIsNone(parse_exact_ivs("IV 57% · CP 778 · 10/12/2026"))
        self.assertEqual((15, 15, 15), parse_exact_ivs("IV: 100% · CP 778"))
        self.assertEqual((15, 15, 15), parse_exact_ivs("100IV · CP 778"))

    def test_page_iv_text_is_used_when_discord_only_has_a_link(self):
        item = CoordItem.from_payload({
            "coordinate": "10.762622,106.660172",
            "discordText": "Click for Coords",
            "ivText": "IV 57% (9/2/15) CP 778",
        })
        self.assertEqual((9, 2, 15), item.iv_stats)

    def test_conflicting_triplets_are_not_trusted(self):
        self.assertIsNone(parse_exact_ivs("IV 9/2/15; corrected IV 8/3/15"))

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
        self.assertTrue(health["sessionId"])

        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/session",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            reset = json.load(response)
        self.assertEqual(reset, {"ok": True, "queued": 0, "completed": 0,
                                 "sessionId": health["sessionId"]})
        self.assertEqual(self.queue.completed_count(), 0)

    def test_new_bridge_has_a_new_session_even_when_completed_is_zero(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as response:
            first = json.load(response)
        self.bridge.stop()
        self.bridge = CoordBridge(CoordQueue(), port=0)
        self.port = self.bridge.start()
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as response:
            second = json.load(response)

        self.assertEqual(0, first["completed"])
        self.assertEqual(0, second["completed"])
        self.assertNotEqual(first["sessionId"], second["sessionId"])


if __name__ == "__main__":
    unittest.main()
