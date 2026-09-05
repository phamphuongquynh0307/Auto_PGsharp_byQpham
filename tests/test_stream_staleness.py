"""A frame left over from before a `screenrecord` relaunch must not be served as "now".

The worker restarts the recording every 175s (screenrecord's own cap), and the frame decoded
just before that gap stays in memory across it. Acting on it means tapping where the UI *was*.
"""
import time
import unittest
from unittest.mock import MagicMock, patch

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


class RelaunchCleanupTests(unittest.TestCase):
    """screenrecord's 180s cap means _run relaunches for the whole session.

    Every relaunch that leaves its decoder open keeps that decoder's threads and its handle on
    the pipe alive for the rest of the run. Measured on a live session: +6 OS threads a minute,
    which is what turned a 0.6s popup pass into a 1.7s one over a few hours.
    """

    def _run_one_launch(self, stream: ScreenStream, container, proc):
        """Drive ScreenStream._run through exactly one launch, then stop it."""
        def decode(video=0):
            yield MagicMock(**{"to_ndarray.return_value": np.zeros((4, 4, 3), np.uint8)})
            stream._stop.set()

        container.decode.side_effect = decode
        with patch("avc.stream.subprocess.Popen", return_value=proc),                 patch("avc.stream.av.open", return_value=container):
            stream._run()

    def _stream(self) -> ScreenStream:
        stream = ScreenStream.__new__(ScreenStream)
        ScreenStream.__init__(stream, serial=None, adb_path="adb", native_size=None, half=False)
        return stream

    def test_the_decoder_is_closed_when_a_recording_ends(self):
        stream = self._stream()
        container = MagicMock()
        self._run_one_launch(stream, container, MagicMock())

        container.close.assert_called_once()

    def test_the_decoder_is_closed_even_when_decoding_raises(self):
        stream = self._stream()
        container = MagicMock()

        def boom(video=0):
            stream._stop.set()
            raise RuntimeError("adb hiccup")

        container.decode.side_effect = boom
        with patch("avc.stream.subprocess.Popen", return_value=MagicMock()),                 patch("avc.stream.av.open", return_value=container),                 patch("avc.stream.time.sleep"):
            stream._run()

        container.close.assert_called_once()

    def test_the_recorder_pipe_is_closed_and_the_process_reaped(self):
        stream = self._stream()
        proc = MagicMock()
        self._run_one_launch(stream, MagicMock(), proc)

        proc.terminate.assert_called_once()
        proc.stdout.close.assert_called_once()
        proc.wait.assert_called_once()

    def test_the_decoder_is_capped_so_it_cannot_claim_every_core(self):
        stream = self._stream()
        container = MagicMock()
        video = container.streams.video.__getitem__.return_value
        self._run_one_launch(stream, container, MagicMock())

        self.assertEqual(2, video.thread_count)


if __name__ == "__main__":
    unittest.main()
