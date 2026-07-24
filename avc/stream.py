"""Realtime screen streaming over ADB.

Instead of paying ~900 ms per one-shot `screencap -p`, this runs `adb screenrecord` to emit an
H.264 stream over a single adb connection, decodes it with PyAV on a background thread, and keeps
the most recent frame in memory. Callers read that latest frame instantly (~0 ms), so the catch
loop can poll the screen almost for free.

`screenrecord` caps a single recording at 180 s, so the worker relaunches the stream whenever it
ends and keeps going.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time

import av
import cv2
import numpy as np

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Just under screenrecord's 180 s hard cap; we relaunch on exit anyway.
_TIME_LIMIT = 175


class _ReadOnly:
    """PyAV probes with seek(); a pipe isn't seekable, so expose read() only."""

    def __init__(self, f):
        self.f = f

    def read(self, n=-1):
        return self.f.read(n)


class ScreenStream:
    def __init__(
        self,
        serial: str | None,
        adb_path: str,
        bitrate: str = "2M",
        native_size: tuple[int, int] | None = None,
        half: bool = True,
    ) -> None:
        self.serial = serial
        self.adb_path = adb_path
        self.bitrate = bitrate
        # Encode at half resolution by default: the phone's H.264 encoder then works on
        # 1/4 of the pixels (much less heat) and the PC decodes 4x faster, so frames never
        # back up in the pipe and latest() stays truly "now". Frames are upscaled lazily
        # only when consumed, so skipped decoder frames cost no resize work.
        # half=False keeps the native resolution — needed when tiny UI text must stay
        # sharp enough for template matching (the shundo IV read).
        self.native_size = native_size
        self._half_size: tuple[int, int] | None = None
        if half and native_size is not None:
            w, h = native_size
            self._half_size = (w // 2 - (w // 2) % 2, h // 2 - (h // 2) % 2)
        self._use_size = self._half_size is not None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._ready = threading.Condition(self._lock)
        self._sequence = 0
        self._native_cache: tuple[int, np.ndarray] | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None

    def _cmd(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += [
            "exec-out", "screenrecord",
            "--output-format=h264",
            f"--bit-rate={self.bitrate}",
            f"--time-limit={_TIME_LIMIT}",
        ]
        if self._use_size:
            hw, hh = self._half_size
            cmd.append(f"--size={hw}x{hh}")
        cmd.append("-")
        return cmd

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            got_frame = False
            try:
                self._proc = subprocess.Popen(self._cmd(), stdout=subprocess.PIPE, creationflags=_NO_WINDOW)
                container = av.open(_ReadOnly(self._proc.stdout), format="h264", mode="r")
                for frame in container.decode(video=0):
                    if self._stop.is_set():
                        break
                    img = frame.to_ndarray(format="bgr24")
                    got_frame = True
                    with self._ready:
                        self._frame = img
                        self._sequence += 1
                        self._native_cache = None
                        self._ready.notify_all()
            except Exception:
                # Transient decode/adb hiccup: pause briefly and relaunch.
                time.sleep(0.3)
            finally:
                self._kill_proc()
            if self._use_size and not got_frame:
                # This device's screenrecord rejected the reduced --size: retry at native size
                # for the rest of the run rather than looping on a dead stream.
                self._use_size = False
            if not self._stop.is_set():
                time.sleep(0.05)  # tiny gap between recordings

    def _kill_proc(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def latest(self, timeout: float = 5.0, *, after_sequence: int | None = None,
               with_sequence: bool = False):
        """Return the latest frame, optionally waiting until its sequence is newer."""
        deadline = time.monotonic() + timeout
        with self._ready:
            while self._frame is None or (after_sequence is not None and self._sequence <= after_sequence):
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._stop.is_set():
                    return (None, self._sequence) if with_sequence else None
                self._ready.wait(timeout=remaining)
            sequence = self._sequence
            img = self._frame
            # Resize lazily when a consumer asks for the frame, not for every decoded frame.
            if self.native_size is not None and (img.shape[1], img.shape[0]) != self.native_size:
                if self._native_cache is None or self._native_cache[0] != sequence:
                    self._native_cache = (
                        sequence, cv2.resize(img, self.native_size, interpolation=cv2.INTER_LINEAR)
                    )
                img = self._native_cache[1]
            return (img, sequence) if with_sequence else img

    def stop(self) -> None:
        self._stop.set()
        self._kill_proc()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._ready:
            self._frame = None
            self._native_cache = None
            self._ready.notify_all()
