"""Session separation for simultaneous device windows."""
import hashlib
import io
import json
import os
import queue
import tempfile
import time
import unittest
from unittest import mock

import gui


class MultiDeviceSessionTests(unittest.TestCase):
    def test_secondary_settings_use_stable_device_file(self):
        serial = "192.0.2.12:5555"
        token = hashlib.sha256(serial.encode("utf-8")).hexdigest()[:12]
        with mock.patch.dict(os.environ, {"AVC_DEVICE_SERIAL": serial}):
            self.assertTrue(gui._settings_path().endswith(f"settings-{token}.json"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(gui._settings_path().endswith("settings.json"))

    def test_new_device_does_not_inherit_other_devices_manual_taps(self):
        app = gui.App.__new__(gui.App)
        app.instance_serial = "device-two"
        app._settings_file = "settings-child.json"
        app.manager = None
        saved = {"device": "device-one", "manual": {"nearby_slot": [10, 20]},
                 "throw_power": 700}
        with mock.patch.object(gui, "_settings_path", return_value="settings-child.json"):
            with mock.patch("builtins.open", side_effect=[FileNotFoundError(),
                     io.StringIO(json.dumps(saved))]):
                loaded = app._read_settings()
        self.assertEqual(loaded["device"], "device-two")
        self.assertEqual(loaded["manual"], {})
        self.assertEqual(loaded["throw_power"], 700)

    def test_new_device_copies_running_phones_settings(self):
        app = gui.App.__new__(gui.App)
        app.instance_serial = "device-new"
        app._settings_file = "settings-new.json"
        idle = mock.Mock(worker=None, _settings_file="settings-idle.json")
        running = mock.Mock(_settings_file="settings-running.json")
        running.worker.is_alive.return_value = True
        app.manager = mock.Mock(sessions={"": mock.Mock(), "idle": idle,
                                          "running": running, "device-new": app})
        saved = {"device": "running", "manual": {"nearby_slot": [1, 2]}, "prefer_usb": True,
                 "throw_power": 777, "webhook": "https://example.invalid/hook"}
        opened = []

        def fake_open(path, *args, **kwargs):
            opened.append(path)
            if path == "settings-new.json":
                raise FileNotFoundError(path)
            return io.StringIO(json.dumps(saved))

        with mock.patch("builtins.open", side_effect=fake_open):
            loaded = app._read_settings()
        running.save_settings.assert_called_once_with()
        self.assertEqual(opened[-1], "settings-running.json")
        self.assertEqual(loaded["throw_power"], 777)
        self.assertEqual(loaded["webhook"], "https://example.invalid/hook")
        self.assertEqual(loaded["manual"], {})
        self.assertEqual(loaded["device"], "device-new")
        self.assertNotIn("prefer_usb", loaded)

    def test_wifi_settings_migrate_to_physical_phone_file(self):
        with tempfile.TemporaryDirectory() as folder:
            wifi = "192.0.2.12:5555"
            legacy = os.path.join(folder, "settings-legacy.json")
            with open(legacy, "w", encoding="utf-8") as file:
                json.dump({"device": "usb-phone", "known_devices": ["usb-phone", wifi],
                           "throw_power": 900}, file)
            app = gui.App.__new__(gui.App)
            app.instance_serial = wifi
            app._settings_file = os.path.join(folder, "settings-physical.json")
            app.manager = None
            self.assertEqual(app._read_settings()["throw_power"], 900)

    def test_transport_rebind_keeps_settings_file(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        app = mock.Mock(worker=None)
        app._settings_file = "settings-physical.json"
        frame = object()
        manager.sessions = {"usb-phone": app}
        manager.frames = {"usb-phone": frame}
        manager.identities = {"usb-phone": "physical-phone"}
        manager._refresh_labels = mock.Mock()
        manager._rebind_app("usb-phone", "192.0.2.12:5555", app)
        self.assertEqual(app._settings_file, "settings-physical.json")

    def test_blank_tab_loads_new_phones_settings(self):
        app = gui.App.__new__(gui.App)
        app.lang = "vi"
        app.known = []
        app.manual = {}
        app._settings_file = "settings.json"
        app._read_settings = mock.Mock(return_value={
            "throw_power": 900, "known_devices": ["usb-phone"],
            "manual": {"nearby_slot": [10, 20]}, "prefer_usb": True,
        })
        app._apply_settings = mock.Mock()
        app._sync_settings_visibility = mock.Mock()
        app._retranslate = mock.Mock()
        app.device_var = mock.Mock()
        with mock.patch.object(gui, "_settings_path", return_value="settings-physical.json"):
            app._adopt_device_settings("usb-phone", "physical-phone")
        self.assertEqual(app._settings_file, "settings-physical.json")
        self.assertEqual(app.manual, {"nearby_slot": [10, 20]})
        self.assertTrue(app.prefer_usb)
        app._apply_settings.assert_called_once_with(app._read_settings.return_value)

    def test_setting_edit_is_saved_after_short_idle(self):
        app = gui.App.__new__(gui.App)
        app.root = mock.Mock()
        app._save_after_id = None
        app.save_settings = mock.Mock()
        app._queue_settings_save()
        app.root.after.assert_called_once_with(400, app._autosave_settings)
        app._autosave_settings()
        app.save_settings.assert_called_once_with()

    def test_existing_device_reuses_tab(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        session = object()
        frame = object()
        manager.sessions = {"device-two": session}
        manager.frames = {"device-two": frame}
        manager.tabs = mock.Mock()
        self.assertIs(manager.add_device("device-two"), session)
        manager.tabs.select.assert_called_once_with(frame)

    def test_wifi_reuses_offline_usb_tab_for_same_phone(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        app = mock.Mock()
        app.worker = None
        frame = object()
        manager.sessions = {"usb-serial": app}
        manager.frames = {"usb-serial": frame}
        manager.identities = {"usb-serial": "phone-id"}
        manager._usb_wifi_links = {}
        manager._seen = {}
        manager.tabs = mock.Mock()
        manager._device_identity = lambda _serial: "phone-id"
        manager._refresh_labels = mock.Mock()
        with mock.patch.object(gui.Device, "list_devices", return_value=["192.0.2.1:5555"]):
            self.assertIs(manager.add_device("192.0.2.1:5555"), app)
        self.assertEqual(list(manager.sessions), ["192.0.2.1:5555"])
        self.assertEqual(app.instance_serial, "192.0.2.1:5555")
        manager.tabs.select.assert_called_once_with(frame)

    def test_run_all_skips_offline_device(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager.root = mock.Mock()
        online = mock.Mock()
        online.OFFLINE_TAG = " (offline)"
        online.device_var.get.return_value = "usb-serial"
        offline = mock.Mock()
        offline.OFFLINE_TAG = " (offline)"
        offline.device_var.get.return_value = "wifi-serial (offline)"
        manager.sessions = {"usb-serial": online, "wifi-serial": offline}
        manager.run_all()
        manager.root.after.assert_called_once_with(0, online.on_play)

    def test_usb_worker_recovers_on_matching_wifi_transport(self):
        app = gui.App.__new__(gui.App)
        app.device = mock.Mock()
        app.device.serial = "usb-serial"
        app.manager = mock.Mock()
        app.manager.wifi_for_usb.return_value = "192.0.2.1:5555"
        app.routine = mock.Mock()
        app.routine.stop_event.is_set.return_value = False
        app.log_queue = mock.Mock()
        app.root = mock.Mock()
        app.tr = lambda _key: "{} {}"
        self.assertEqual(app._recover_runtime_device(), "192.0.2.1:5555")
        self.assertEqual(app.device.serial, "192.0.2.1:5555")
        app.root.after.assert_called_once()

    def test_usb_recovers_through_paired_wifi_on_same_host(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager.identities = {"usb-serial": "phone-id"}
        manager._usb_wifi_links = {}
        manager._usb_wifi_hosts = {"usb-serial": "192.0.2.1"}
        manager.sessions = {"usb-serial": mock.Mock(known=[])}
        manager._device_identity = lambda serial: "phone-id" if serial == "192.0.2.1:37123" else serial
        with mock.patch.object(gui.Device, "list_devices", return_value=[]), \
             mock.patch.object(gui.Device, "discover_wireless", return_value=["192.0.2.1:37123"]), \
             mock.patch.object(gui.Device, "adb_connect") as connect:
            self.assertEqual(manager.wifi_for_usb("usb-serial"), "192.0.2.1:37123")
        connect.assert_called_with("192.0.2.1:37123", timeout=3.0)

    def test_background_discovery_updates_tabs(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager._closing = False
        manager._discovery_results = queue.Queue()
        manager._discovery_results.put(("attached", ["usb-serial"]))
        manager._polling = True
        manager._last_discovery = time.monotonic()
        manager._apply_attached = mock.Mock()
        manager.root = mock.Mock()
        manager._poll_devices()
        manager._apply_attached.assert_called_once_with(["usb-serial"])
        manager.root.after.assert_called_once_with(500, manager._poll_devices)

    def test_failed_wifi_endpoint_gets_retry_delay(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager._closing = False
        manager._discovery_results = queue.Queue()
        manager._discovery_results.put(("attached", [], {}, ["192.0.2.1:5555"]))
        manager._wifi_retry_after = {}
        manager._polling = True
        manager._last_discovery = time.monotonic()
        manager._usb_wifi_hosts = {}
        manager._apply_attached = mock.Mock()
        manager.root = mock.Mock()
        manager._poll_devices()
        self.assertGreater(manager._wifi_retry_after["192.0.2.1:5555"], time.monotonic() + 55)

    def test_idle_usb_phone_switches_to_wifi_once_per_plug(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        idle = mock.Mock(instance_serial="usb-idle", worker=None, _wifi_busy=False,
                         prefer_usb=False)
        busy = mock.Mock(instance_serial="usb-busy", _wifi_busy=False, prefer_usb=False)
        cable = mock.Mock(instance_serial="usb-cable", worker=None, _wifi_busy=False,
                          prefer_usb=True)
        busy.worker.is_alive.return_value = True
        manager.sessions = {"usb-idle": idle, "usb-busy": busy, "usb-cable": cable}
        manager._auto_wifi_tried = set()
        hosts = {"usb-idle": "192.0.2.1", "usb-busy": "192.0.2.2", "usb-cable": "192.0.2.3"}
        manager._auto_wifi(list(hosts), hosts)
        manager._auto_wifi(list(hosts), hosts)
        idle._to_wifi.assert_called_once_with()
        busy._to_wifi.assert_not_called()
        cable._to_wifi.assert_not_called()
        # Unplug and replug: allowed to try again.
        manager._auto_wifi([], {})
        manager._auto_wifi(["usb-idle"], {"usb-idle": "192.0.2.1"})
        self.assertEqual(idle._to_wifi.call_count, 2)

    def _cable_manager(self, app):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager.sessions = {"192.0.2.1:5555": app}
        manager.frames = {"192.0.2.1:5555": object()}
        manager.identities = {"192.0.2.1:5555": "phone-id"}
        manager._usb_wifi_links = {}
        manager._seen = {}
        manager.tabs = mock.Mock()
        manager._device_identity = lambda _serial: "phone-id"
        manager._refresh_labels = mock.Mock()
        return manager

    def test_prefer_usb_moves_wifi_tab_back_to_cable(self):
        app = mock.Mock(worker=None, prefer_usb=True)
        manager = self._cable_manager(app)
        with mock.patch.object(gui.Device, "list_devices",
                               return_value=["192.0.2.1:5555", "usb-serial"]):
            manager.add_device("usb-serial")
        self.assertEqual(list(manager.sessions), ["usb-serial"])

    def test_default_keeps_wifi_tab_when_cable_appears(self):
        app = mock.Mock(worker=None, prefer_usb=False)
        manager = self._cable_manager(app)
        with mock.patch.object(gui.Device, "list_devices",
                               return_value=["192.0.2.1:5555", "usb-serial"]):
            manager.add_device("usb-serial")
        self.assertEqual(list(manager.sessions), ["192.0.2.1:5555"])

    def test_usb_for_finds_same_phone_cable(self):
        manager = self._cable_manager(mock.Mock())
        manager._device_identity = lambda s: "other" if s == "usb-other" else "phone-id"
        with mock.patch.object(gui.Device, "list_devices",
                               return_value=["192.0.2.1:5555", "usb-other", "usb-serial"]):
            self.assertEqual(manager.usb_for("192.0.2.1:5555"), "usb-serial")


if __name__ == "__main__":
    unittest.main()
