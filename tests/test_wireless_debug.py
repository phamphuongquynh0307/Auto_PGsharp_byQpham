import unittest
from types import SimpleNamespace
from unittest.mock import patch

from avc.device import AdbError, Device


def completed(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


class WirelessDebugDiscoveryTests(unittest.TestCase):
    def test_mdns_keeps_only_valid_services_and_normalises_endpoints(self):
        output = """List of discovered mdns services
pixel-pair _adb-tls-pairing._tcp 192.168.1.4:37123
pixel-connect _adb-tls-connect._tcp 192.168.1.4:43239
old-phone _adb._tcp 192.168.1.8:5555
bad-line _adb-tls-connect._tcp not-an-endpoint
"""
        with patch("avc.device._quiet_run", return_value=completed(output)):
            services = Device.mdns_services("adb-test")

        self.assertEqual(3, len(services))
        self.assertEqual(
            ["192.168.1.4:43239"],
            [s.endpoint for s in services if s.service_type == "_adb-tls-connect._tcp"],
        )

    def test_empty_mdns_result_is_not_an_error(self):
        with patch("avc.device._quiet_run", return_value=completed("")):
            self.assertEqual([], Device.discover_wireless("adb-test"))

    def test_mdns_command_failure_is_reported(self):
        with patch(
            "avc.device._quiet_run",
            return_value=completed("", "daemon unavailable", returncode=1),
        ):
            with self.assertRaisesRegex(AdbError, "daemon unavailable"):
                Device.mdns_services("adb-test")

    def test_connect_prefers_a_remembered_phone_ip(self):
        with patch.object(
            Device,
            "discover_wireless",
            return_value=["192.168.1.9:40001", "192.168.1.4:43239"],
        ), patch.object(Device, "adb_connect") as connect:
            serial = Device.connect_discovered_wireless(["192.168.1.4"], "adb-test")

        self.assertEqual("192.168.1.4:43239", serial)
        connect.assert_called_once_with("192.168.1.4:43239", "adb-test")

    def test_connect_moves_to_next_advertised_device_after_failure(self):
        with patch.object(
            Device,
            "discover_wireless",
            return_value=["192.168.1.4:43239", "192.168.1.9:40001"],
        ), patch.object(
            Device,
            "adb_connect",
            side_effect=[AdbError("offline"), None],
        ) as connect:
            serial = Device.connect_discovered_wireless(adb_path="adb-test")

        self.assertEqual("192.168.1.9:40001", serial)
        self.assertEqual(2, connect.call_count)

    def test_discovery_retries_when_mdns_is_not_ready_yet(self):
        with patch.object(
            Device,
            "discover_wireless",
            side_effect=[[], ["192.168.1.4:43239"]],
        ), patch.object(Device, "adb_connect") as connect, patch(
            "avc.device.time.sleep"
        ) as sleep:
            serial = Device.connect_discovered_wireless(
                discovery_attempts=2, retry_delay=0.25, adb_path="adb-test",
            )

        self.assertEqual("192.168.1.4:43239", serial)
        connect.assert_called_once_with("192.168.1.4:43239", "adb-test")
        sleep.assert_called_once_with(0.25)

    def test_connect_accepts_success_reported_on_stderr(self):
        with patch(
            "avc.device._quiet_run",
            side_effect=[
                completed(b"", b"already connected to 192.168.1.4:43239\n"),
                completed(b"device\n", b""),
            ],
        ) as run:
            Device.adb_connect("192.168.1.4:43239", "adb-test")

        self.assertEqual(
            ["adb-test", "connect", "192.168.1.4:43239"],
            run.call_args_list[0].args[0],
        )

    def test_connect_waits_for_device_state_after_adb_says_connected(self):
        with patch(
            "avc.device._quiet_run",
            side_effect=[
                completed(b"connected to 192.168.1.4:43239\n", b""),
                completed(b"offline\n", b""),
                completed(b"already connected to 192.168.1.4:43239\n", b""),
                completed(b"device\n", b""),
            ],
        ) as run, patch("avc.device.time.sleep") as sleep:
            Device.adb_connect("192.168.1.4:43239", "adb-test")

        self.assertEqual(4, run.call_count)
        sleep.assert_called_once_with(0.25)


class WirelessDebugPairTests(unittest.TestCase):
    def test_pair_passes_code_as_one_argument_and_returns_endpoint(self):
        with patch(
            "avc.device._quiet_run",
            return_value=completed(b"Successfully paired to 192.168.1.4:37123\n", b""),
        ) as run:
            serial = Device.adb_pair(" 192.168.1.4:37123 ", "123456", "adb-test")

        self.assertEqual("192.168.1.4:37123", serial)
        self.assertEqual(
            ["adb-test", "pair", "192.168.1.4:37123", "123456"],
            run.call_args.args[0],
        )

    def test_pair_rejects_invalid_code_before_running_adb(self):
        with patch("avc.device._quiet_run") as run:
            with self.assertRaises(ValueError):
                Device.adb_pair("192.168.1.4:37123", "12;456", "adb-test")
        run.assert_not_called()

    def test_endpoint_parser_rejects_commands_and_bad_ports(self):
        for value in ("192.168.1.4", "host:43239", "192.168.1.4:70000", "1.2.3.4:4;whoami"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Device.normalize_tcp_endpoint(value)

    def test_pair_failure_does_not_echo_code_in_exception(self):
        with patch(
            "avc.device._quiet_run",
            return_value=completed(b"", b"Failed: wrong password", returncode=1),
        ):
            with self.assertRaises(AdbError) as caught:
                Device.adb_pair("192.168.1.4:37123", "123456", "adb-test")
        self.assertNotIn("123456", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
