import unittest

from gui import GUIDE_PAGES, GUIDE_SECTIONS, _parse_guide_image_marker


class GuideContentTests(unittest.TestCase):
    def test_every_section_has_both_languages(self):
        for code, labels in GUIDE_SECTIONS:
            self.assertIn(code, GUIDE_PAGES)
            self.assertTrue(labels["vi"])
            self.assertTrue(labels["en"])
            self.assertTrue(GUIDE_PAGES[code]["vi"].strip())
            self.assertTrue(GUIDE_PAGES[code]["en"].strip())

    def test_all_image_slots_have_stable_safe_filenames(self):
        stems = set()
        for page in GUIDE_PAGES.values():
            for language in ("vi", "en"):
                for line in page[language].splitlines():
                    if "[[IMAGE:" not in line:
                        continue
                    marker = _parse_guide_image_marker(line)
                    self.assertIsNotNone(marker, line)
                    stem, caption = marker
                    stems.add(stem)
                    self.assertTrue(caption)

        self.assertEqual(
            {
                "01-app-windows", "02-usb-debug", "03-connect-wifi", "04-test-control",
                "05-pgsharp-install", "06-pgsharp-shortcuts", "07-pgsharp-common",
                "08-catch-layout", "09-catch-preview", "10-shundo-feed",
                "11-shundo-calibration", "12-edge-extension", "13-pgsharp-teleport",
                "14-coord-flow", "15-spin-preview",
            },
            stems,
        )

    def test_image_marker_rejects_path_traversal(self):
        self.assertIsNone(_parse_guide_image_marker("[[IMAGE:../secret|bad]]"))
        self.assertIsNone(_parse_guide_image_marker("[[IMAGE:C:\\secret|bad]]"))

    def test_pgsharp_mode_switch_is_explicit(self):
        page = GUIDE_PAGES["pgsharp"]["vi"]
        self.assertIn("Auto bắt Pokémon: TẮT", page)
        self.assertIn("Chấm shiny từ Feed/Discord Coord: BẬT", page)


if __name__ == "__main__":
    unittest.main()
