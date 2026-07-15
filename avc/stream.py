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
    def __init__(self, serial: str | None, adb_path: str, bitrate: str = "8M") -> None:
        self.serial = serial
        self.adb_path = adb_path
        self.bitrate = bitrate
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
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
            "-",
        ]
        return cmd

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(self._cmd(), stdout=subprocess.PIPE, creationflags=_NO_WINDOW)
                container = av.open(_ReadOnly(self._proc.stdout), format="h264", mode="r")
                for frame in container.decode(video=0):
                    if self._stop.is_set():
                        break
                    img = frame.to_ndarray(format="bgr24")
                    with self._lock:
                        self._frame = img
            except Exception:
                # Transient decode/adb hiccup: pause briefly and relaunch.
                time.sleep(0.3)
            finally:
                self._kill_proc()
            if not self._stop.is_set():
                time.sleep(0.05)  # tiny gap between recordings

    def _kill_proc(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def latest(self, timeout: float = 5.0) -> np.ndarray | None:
        """Most recent frame, waiting up to `timeout` for the first one to arrive."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                if self._frame is not None:
                    return self._frame
            if time.monotonic() >= deadline or self._stop.is_set():
                return None
            time.sleep(0.02)

    def stop(self) -> None:
        self._stop.set()
        self._kill_proc()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        with self._lock:
            self._frame = None
