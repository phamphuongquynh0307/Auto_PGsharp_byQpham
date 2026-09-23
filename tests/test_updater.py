import unittest
import hashlib
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from avc import updater
from avc.updater import newer


class UpdaterTests(unittest.TestCase):
    def test_only_newer_stable_triplets_update(self):
        self.assertTrue(newer("v1.4.27", "1.4.26"))
        self.assertFalse(newer("v1.4.26", "1.4.26"))
        self.assertFalse(newer("v1.4.25", "1.4.26"))
        self.assertFalse(newer("v1.5.0-rc1", "1.4.26"))

    def test_download_accepts_only_matching_checksum(self):
        payload = b"MZexample"
        root = ("https://github.com/phamphuongquynh0307/Auto_PGsharp_byQpham/"
                "releases/download/v1.4.27/")
        release = {"tag_name": "v1.4.27", "assets": [
            {"name": name, "browser_download_url": root + name}
            for name in (updater.EXE_NAME, updater.HASH_NAME)]}
        with tempfile.TemporaryDirectory() as directory:
            exe = str(Path(directory) / updater.EXE_NAME)
            digest = hashlib.sha256(payload).hexdigest()
            with (patch.object(updater, "_get", return_value=digest.encode()),
                  patch.object(updater.urllib.request, "urlopen",
                               return_value=io.BytesIO(payload))):
                version, staged = updater.download_update(release, exe)
            self.assertEqual("v1.4.27", version)
            self.assertEqual(payload, staged.read_bytes())

            with (patch.object(updater, "_get", return_value=b"0" * 64),
                  patch.object(updater.urllib.request, "urlopen",
                               return_value=io.BytesIO(payload))):
                with self.assertRaisesRegex(ValueError, "digest mismatch"):
                    updater.download_update(release, exe)
            self.assertFalse(staged.exists())

    def test_check_only_reads_release_metadata(self):
        release = {"tag_name": "v1.4.27"}
        with patch.object(updater, "_get", return_value=json.dumps(release).encode()) as get:
            self.assertEqual(release, updater.available_update("1.4.26"))
            self.assertIsNone(updater.available_update("1.4.27"))
        self.assertEqual(2, get.call_count)
