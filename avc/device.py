"""ADB device control: capture the screen and dispatch taps/swipes.

Everything here shells out to `adb`. Screen capture uses `exec-out screencap -p` piped
straight into memory (no temp file on the phone) and decoded with OpenCV.
"""
from __future__ import annotations

import subprocess
import sys
import time

import cv2
import numpy as np

from .resources import find_adb

# adb is a console program; in a windowed (no-console) build every call would otherwise flash
# a terminal window. CREATE_NO_WINDOW suppresses that. No-op on non-Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _quiet_run(cmd, **kwargs):
    return subprocess.run(cmd, creationflags=_NO_WINDOW, **kwargs)


class AdbError(RuntimeError):
    pass


class Device:
    def __init__(self, serial: str | None = None, adb_path: str | None = None) -> None:
        self.adb_path = adb_path or find_adb()
        self.serial = serial
        self._size: tuple[int, int] | None = None
        self._stream = None  # ScreenStream when realtime capture is enabled

    # -- realtime streaming ---------------------------------------------------
    def start_stream(self) -> None:
        """Switch screenshot() to pull frames from a live H.264 stream (near-zero latency)."""
        if self._stream is not None:
            return
        from .stream import ScreenStream

        self._stream = ScreenStream(self.serial, self.adb_path)
        self._stream.start()

    def stop_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None

    # -- low level ------------------------------------------------------------
    def _base_cmd(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run(self, args: list[str], *, binary: bool = False, timeout: float = 20.0):
        proc = _quiet_run(
            self._base_cmd() + args,
            capture_output=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "replace").strip()
            raise AdbError(f"adb {' '.join(args)} failed: {stderr}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    # -- discovery ------------------------------------------------------------
    @classmethod
    def list_devices(cls, adb_path: str | None = None) -> list[str]:
        adb = adb_path or find_adb()
        out = _quiet_run([adb, "devices"], capture_output=True, text=True, timeout=15).stdout
        serials = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if line and "\tdevice" in line:
                serials.append(line.split("\t")[0])
        return serials

    def screen_size(self) -> tuple[int, int]:
        """(width, height) in pixels. Cached after first read."""
        if self._size is not None:
            return self._size
        out = self._run(["shell", "wm", "size"])
        # e.g. "Physical size: 1220x2712"
        for token in out.replace("Override size", "Physical size").split():
            if "x" in token and token.replace("x", "").isdigit():
                w, h = token.split("x")
                self._size = (int(w), int(h))
                return self._size
        raise AdbError(f"could not parse screen size from: {out!r}")

    # -- capture --------------------------------------------------------------
    def screenshot(self) -> np.ndarray:
        """Current screen as a BGR image. Uses the live stream if started, else a one-shot capture."""
        if self._stream is not None:
            frame = self._stream.latest()
            if frame is not None:
                return frame
            # Stream not producing yet — fall through to a one-shot grab.
        png = self._run(["exec-out", "screencap", "-p"], binary=True)
        arr = np.frombuffer(png, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("failed to decode screencap PNG (empty or corrupt frame)")
        return img

    # -- input ----------------------------------------------------------------
    def tap(self, x: int, y: int) -> None:
        self._run(["shell", "input", "tap", str(int(x)), str(int(y))])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run(
            ["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))]
        )

    def key(self, keycode: str) -> None:
        self._run(["shell", "input", "keyevent", keycode])

    def back(self) -> None:
        self.key("KEYCODE_BACK")

    def wake(self) -> None:
        self.key("KEYCODE_WAKEUP")

    # -- low-power "screen off" ----------------------------------------------
    # Setting brightness to 0 makes the panel look off (no backlight heat/drain) while the game
    # keeps rendering to the framebuffer, so capture + taps still work. Also keep the screen from
    # actually sleeping while on USB.
    def _get_setting(self, ns: str, key: str) -> str:
        return self._run(["shell", "settings", "get", ns, key]).strip()

    def _put_setting(self, ns: str, key: str, value) -> None:
        self._run(["shell", "settings", "put", ns, key, str(value)])

    def enable_dim(self) -> None:
        self.wake()
        self._saved_screen = {
            "mode": self._get_setting("system", "screen_brightness_mode"),
            "bright": self._get_setting("system", "screen_brightness"),
            "stay": self._get_setting("global", "stay_on_while_plugged_in"),
        }
        # manual brightness, minimum, and stay awake while charging (3 = AC|USB).
        self._put_setting("system", "screen_brightness_mode", 0)
        self._put_setting("system", "screen_brightness", 0)
        self._put_setting("global", "stay_on_while_plugged_in", 3)

    def restore_dim(self) -> None:
        saved = getattr(self, "_saved_screen", None)
        if not saved:
            return
        if saved["mode"].isdigit():
            self._put_setting("system", "screen_brightness_mode", saved["mode"])
        if saved["bright"].isdigit():
            self._put_setting("system", "screen_brightness", saved["bright"])
        if saved["stay"].isdigit():
            self._put_setting("global", "stay_on_while_plugged_in", saved["stay"])
        self._saved_screen = None

    def is_connected(self) -> bool:
        try:
            self._run(["get-state"], timeout=5)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    # Quick smoke test: print device size and save one screenshot.
    devs = Device.list_devices()
    print("devices:", devs)
    if devs:
        d = Device(devs[0])
        print("size:", d.screen_size())
        img = d.screenshot()
        cv2.imwrite("_smoke_screenshot.png", img)
        print("saved _smoke_screenshot.png", img.shape)
