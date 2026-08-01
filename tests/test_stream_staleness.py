"""A frame left over from before a `screenrecord` relaunch must not be served as "now".

The worker restarts the recording every 175s (screenrecord's own cap), and the frame decoded
just before that gap stays in memory across it. Acting on it means tapping where the UI *was*.
"""
import time
import unittest
from unittest.mock import patch

import numpy as np

from avc.device import Device
from avc.stream import ScreenStream


def _stream_holding(frame_age: float) -> ScreenStream:
    """A stream whose newest frame was decoded `frame_age` seconds ago."""
    stream = ScreenStream.__new__(ScreenStream)
    ScreenStream.__init__(stream, serial=None, adb_path="adb", native_size=None, half=False)
    stream._frame = np.zeros((8, 8, 3), dtype=np.uint8)
    stream._frame_at = time.monotonic() - frame_age
    stream._sequence = 7
    return stream


class LatestStalenessTests(unittest.TestCase):
    def test_fresh_frame_is_returned(self):
        stream = _stream_holding(0.02)

        self.assertIsNotNone(stream.latest(timeout=0.05, max_age=0.5))

    def test_frame_older_than_max_age_counts_as_absent(self):
        stream = _stream_holding(3.0)

        self.assertIsNone(stream.latest(timeout=0.05, max_age=0.5))

    def test_without_max_age_the_old_behaviour_is_unchanged(self):
        stream = _stream_holding(3.0)

        self.assertIsNotNone(stream.latest(timeout=0.05))


class ScreenshotFallbackTests(unittest.TestCase):
    def _device(self, stream: ScreenStream) -> Device:
        device = Device.__new__(Device)
        device._stream = stream
        device._last_frame_sequence = 0
        return device

    def test_stale_stream_falls_back_to_a_one_shot_capture(self):
        device = self._device(_stream_holding(3.0))
        captured = np.full((8, 8, 3), 9, dtype=np.uint8)

        with patch.object(Device, "_run", return_value=b"png") as run, \
             patch("avc.device.cv2.imdecode", return_value=captured):
            frame = device.screenshot()

        self.assertIs(frame, captured)
        self.assertEqual(["exec-out", "screencap", "-p"], run.call_args.args[0])

    def test_fresh_stream_is_used_without_touching_adb(self):
        device = self._device(_stream_holding(0.02))

        with patch.object(Device, "_run", side_effect=AssertionError("must not shell out")):
            frame = device.screenshot()

        self.assertIsNotNone(frame)
        self.assertEqual(7, device._last_frame_sequence)


if __name__ == "__main__":
    unittest.main()
