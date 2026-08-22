import unittest

from avc.device import Device


class DeviceTextInputTests(unittest.TestCase):
    def setUp(self):
        self.device = object.__new__(Device)
        self.calls = []
        self.device._run = lambda args, **_kwargs: self.calls.append(args)

    def test_coordinate_is_typed_without_shell_interpolation(self):
        self.device.input_coordinate("-23.587435,-46.654448")
        self.assertEqual(
            self.calls,
            [["shell", "input", "keyevent",
              "KEYCODE_MINUS", "KEYCODE_2", "KEYCODE_3", "KEYCODE_PERIOD",
              "KEYCODE_5", "KEYCODE_8", "KEYCODE_7", "KEYCODE_4", "KEYCODE_3", "KEYCODE_5",
              "KEYCODE_COMMA", "KEYCODE_MINUS", "KEYCODE_4", "KEYCODE_6", "KEYCODE_PERIOD",
              "KEYCODE_6", "KEYCODE_5", "KEYCODE_4", "KEYCODE_4", "KEYCODE_4", "KEYCODE_8"]],
        )

    def test_positive_coordinate_uses_digit_and_punctuation_keycodes(self):
        self.device.input_coordinate("1.2,3.4")
        self.assertEqual(
            self.calls,
            [["shell", "input", "keyevent", "KEYCODE_1", "KEYCODE_PERIOD", "KEYCODE_2",
              "KEYCODE_COMMA", "KEYCODE_3", "KEYCODE_PERIOD", "KEYCODE_4"]],
        )

    def test_rejects_non_coordinate_shell_characters(self):
        with self.assertRaises(ValueError):
            self.device.input_coordinate("1,2;touch /tmp/nope")
        self.assertEqual(self.calls, [])

    def test_clear_is_one_bounded_keyevent_command(self):
        self.device.clear_text(3)
        self.assertEqual(
            self.calls,
            [["shell", "input", "keyevent", "KEYCODE_MOVE_END",
              "KEYCODE_DEL", "KEYCODE_DEL", "KEYCODE_DEL"]],
        )


class ControlReuseTests(unittest.TestCase):
    def test_release_sends_duplicate_ups_without_closing_a_live_socket(self):
        device = object.__new__(Device)
        device._control_socket = object()
        touches = []
        closed = []
        device._touch = lambda *args: touches.append(args)
        device.close_control = lambda: closed.append(True)

        device.release_control_pointers()

        self.assertEqual(
            [(1, 1, 0, 0), (1, 0, 0, 0), (1, 1, 0, 0), (1, 0, 0, 0)],
            touches,
        )
        self.assertEqual([], closed)

    def test_release_closes_only_when_the_live_socket_is_broken(self):
        device = object.__new__(Device)
        device._control_socket = object()
        closed = []
        device._touch = lambda *_args: (_ for _ in ()).throw(OSError("broken"))
        device.close_control = lambda: closed.append(True)

        device.release_control_pointers()

        self.assertEqual([True], closed)


if __name__ == "__main__":
    unittest.main()
