import unittest

from avc.device import Device


class DeviceUiDumpTests(unittest.TestCase):
    def test_reads_hierarchy_directly_without_a_stale_sdcard_file(self):
        device = object.__new__(Device)
        device._ui_dump_supported = True
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
        device._ui_dump_supported = True
        device._run = lambda _args, **_kwargs: b"UI hierarchy dump failed"

        self.assertIsNone(device.ui_dump())

    def test_skips_uiautomator_on_hyperos_3_android_15(self):
        device = object.__new__(Device)
        device._ui_dump_supported = None
        calls = []
        values = iter(("Xiaomi\n", "35\n", "OS3.0\n"))

        def run(args, **_kwargs):
            calls.append(args)
            return next(values)

        device._run = run

        self.assertIsNone(device.ui_dump())
        self.assertEqual(3, len(calls))
        self.assertNotIn("uiautomator", [part for call in calls for part in call])
        # The compatibility decision is cached; later checks must not issue more ADB calls.
        self.assertIsNone(device.ui_dump())
        self.assertEqual(3, len(calls))

    def test_keeps_uiautomator_on_other_android_builds(self):
        device = object.__new__(Device)
        device._ui_dump_supported = None
        replies = iter((
            "Google\n",
            "35\n",
            "\n",
            b"<?xml version='1.0'?><hierarchy><node bounds='[0,0][1,1]' /></hierarchy>",
        ))
        device._run = lambda _args, **_kwargs: next(replies)

        self.assertIn("<hierarchy>", device.ui_dump())


if __name__ == "__main__":
    unittest.main()
