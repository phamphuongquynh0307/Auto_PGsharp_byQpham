"""The support zip has to carry the log and *not* carry the user's Discord webhook."""
import json
import os
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from avc import diag


class RedactionTests(unittest.TestCase):
    def test_webhook_is_stripped_from_the_exported_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = os.path.join(tmp, "settings.json")
            with open(settings, "w", encoding="utf-8") as fh:
                json.dump({"webhook": "https://discord.com/api/webhooks/1/secret",
                           "lang": "vi"}, fh)
            dest = os.path.join(tmp, "report.zip")

            with patch.object(diag, "base_dir", return_value=tmp):
                diag.export(dest, settings_path=settings)

            with zipfile.ZipFile(dest) as bundle:
                exported = json.loads(bundle.read("settings.json").decode("utf-8"))
        self.assertNotIn("secret", json.dumps(exported))
        self.assertEqual("vi", exported["lang"])

    def test_an_empty_webhook_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = os.path.join(tmp, "settings.json")
            with open(settings, "w", encoding="utf-8") as fh:
                json.dump({"webhook": "", "lang": "en"}, fh)

            self.assertEqual("", json.loads(diag._redacted_settings(settings))["webhook"])


class ExportContentTests(unittest.TestCase):
    def test_log_and_screenshot_are_bundled(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, diag.LOG_NAME), "w", encoding="utf-8") as fh:
                fh.write("dong log thu nghiem\n")
            dest = os.path.join(tmp, "report.zip")

            with patch.object(diag, "base_dir", return_value=tmp):
                diag.export(dest, screenshot=np.zeros((8, 8, 3), dtype=np.uint8),
                            notes={"do_phan_giai": "1220x2712"})

            with zipfile.ZipFile(dest) as bundle:
                names = set(bundle.namelist())
                system = bundle.read("he_thong.txt").decode("utf-8")
        self.assertIn(diag.LOG_NAME, names)
        self.assertIn("man_hinh.png", names)
        self.assertIn("1220x2712", system)

    def test_export_survives_a_missing_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "report.zip")

            with patch.object(diag, "base_dir", return_value=tmp):
                diag.export(dest)

            self.assertTrue(os.path.exists(dest))


class DeviceInfoTests(unittest.TestCase):
    def test_a_tcp_serial_is_reported_as_wifi(self):
        device = SimpleNamespace(serial="192.168.1.2:5555", _stream=None,
                                 screen_size=lambda: (1220, 2712), density=lambda: 480)

        info = diag.device_info(device)

        self.assertEqual("Wi-Fi", info["ket_noi"])
        self.assertEqual("1220x2712", info["do_phan_giai"])
        self.assertEqual(480, info["mat_do_dpi"])

    def test_unreadable_size_does_not_raise(self):
        def boom():
            raise RuntimeError("adb offline")

        device = SimpleNamespace(serial="ABC123", _stream=object(),
                                 screen_size=boom, density=boom)

        info = diag.device_info(device)

        self.assertEqual("USB", info["ket_noi"])
        self.assertEqual("(khong doc duoc)", info["do_phan_giai"])
        self.assertEqual("bat", info["stream"])


if __name__ == "__main__":
    unittest.main()
