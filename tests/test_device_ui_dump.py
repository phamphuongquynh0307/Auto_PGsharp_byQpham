import unittest

from avc.device import Device


class DeviceUiDumpTests(unittest.TestCase):
    def test_reads_hierarchy_directly_without_a_stale_sdcard_file(self):
        device = object.__new__(Device)
        calls = []

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return (b"vendor banner\n<?xml version='1.0'?><hierarchy>"
                    b"<node bounds='[0,0][1,1]' /></hierarchy>\nstatus")

        device._run = run

        xml = device.ui_dump(timeout=3.0)

        self.assertEqual(
            "<?xml version='1.0'?><hierarchy><node bounds='[0,0][1,1]' /></hierarchy>",
            xml,
        )
        self.assertEqual(
            [(["exec-out", "uiautomator", "dump", "/dev/tty"],
              {"binary": True, "timeout": 3.0})],
            calls,
        )

    def test_incomplete_dump_is_not_returned(self):
        device = object.__new__(Device)
        device._run = lambda _args, **_kwargs: b"UI hierarchy dump failed"

        self.assertIsNone(device.ui_dump())


if __name__ == "__main__":
    unittest.main()
