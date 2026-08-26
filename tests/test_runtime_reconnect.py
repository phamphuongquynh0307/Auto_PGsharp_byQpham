import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import gui
from avc.device import AdbError


class ImmediateRoot:
    def after(self, _delay, callback):
        callback()


def bare_app(serial="192.168.1.4:43239"):
    app = object.__new__(gui.App)
    app.device = SimpleNamespace(serial=serial, adb_path="adb-test")
    app.known = ["192.168.1.4:43239", "192.168.1.4:5555", "192.168.1.9:5555"]
    app.routine = SimpleNamespace(stop_event=threading.Event())
    app.log_queue = queue.Queue()
    app.root = ImmediateRoot()
    app.remembered = []
    app._remember_device = lambda value: app.remembered.append(value)
    app.tr = lambda key: "lost {}/{}" if key == "conn_run_lost" else key
    return app


class RuntimeReconnectTests(unittest.TestCase):
    def test_falls_back_to_same_phones_legacy_endpoint(self):
        app = bare_app()
        with patch.object(
            gui.Device,
            "adb_connect",
            side_effect=[AdbError("tls endpoint gone"), None],
        ) as connect:
            serial = app._recover_runtime_device(max_attempts=1)

        self.assertEqual("192.168.1.4:5555", serial)
        self.assertEqual(serial, app.device.serial)
        self.assertEqual([serial], app.remembered)
        self.assertEqual(
            [
                (("192.168.1.4:43239", "adb-test"), {"timeout": 3.0}),
                (("192.168.1.4:5555", "adb-test"), {"timeout": 3.0}),
            ],
            [(call.args, call.kwargs) for call in connect.call_args_list],
        )

    def test_mdns_can_supply_a_rotated_tls_port_after_known_ports_fail(self):
        app = bare_app()
        with patch.object(gui.Device, "adb_connect", side_effect=AdbError("offline")), patch.object(
            gui.Device,
            "connect_discovered_wireless",
            return_value="192.168.1.4:49999",
        ) as discover:
            serial = app._recover_runtime_device(max_attempts=1)

        self.assertEqual("192.168.1.4:49999", serial)
        discover.assert_called_once_with(
            ["192.168.1.4"], "adb-test", discovery_attempts=4, retry_delay=0.75,
        )

    def test_usb_disconnect_is_not_misrepresented_as_wifi_reconnect(self):
        app = bare_app("f76cc588")
        with patch.object(gui.Device, "adb_connect") as connect:
            with self.assertRaises(AdbError):
                app._recover_runtime_device(max_attempts=1)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
