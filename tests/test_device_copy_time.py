"""Device actions without an attached phone or Tk display."""
import unittest
from unittest import mock

import gui


class DeviceCopyTimeTests(unittest.TestCase):
    def test_name_click_copies_disambiguated_name_without_status_icon(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager.root = mock.Mock()
        manager.primary = None
        first = mock.Mock(instance_serial="phone-1234")
        second = mock.Mock(instance_serial="phone-5678")
        manager.models = {first: "Điện thoại", second: "Điện thoại"}
        manager._fleet_rows = {"first": first}
        manager.fleet = mock.Mock()
        manager.fleet.identify_column.return_value = "#1"
        manager.fleet.identify_row.return_value = "first"
        manager._on_fleet_click(mock.Mock(x=10, y=10))
        manager.root.clipboard_clear.assert_called_once_with()
        manager.root.clipboard_append.assert_called_once_with("Điện thoại ·1234")
        first._toggle_link.assert_not_called()

    def test_empty_card_does_not_overwrite_clipboard(self):
        manager = gui.MultiDeviceApp.__new__(gui.MultiDeviceApp)
        manager.root = mock.Mock()
        manager._fleet_rows = {"empty": None}
        manager._on_card_name()
        manager.root.clipboard_clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
