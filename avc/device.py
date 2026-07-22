"""ADB device control: capture the screen and dispatch taps/swipes.

Everything here shells out to `adb`. Screen capture uses `exec-out screencap -p` piped
straight into memory (no temp file on the phone) and decoded with OpenCV.
"""
from __future__ import annotations

import subprocess
import socket
import struct
import sys
import time

import cv2
import numpy as np

from .resources import find_adb, resource_path

# adb is a console program; in a windowed (no-console) build every call would otherwise flash
# a terminal window. CREATE_NO_WINDOW suppresses that. No-op on non-Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _quiet_run(cmd, **kwargs):
    return subprocess.run(cmd, creationflags=_NO_WINDOW, **kwargs)


class AdbError(RuntimeError):
    pass


class Device:
    MUMU_SERIAL = "127.0.0.1:7555"

    def __init__(self, serial: str | None = None, adb_path: str | None = None) -> None:
        self.adb_path = adb_path or find_adb()
        self.serial = serial
        self._size: tuple[int, int] | None = None
        self._stream = None  # ScreenStream when realtime capture is enabled
        self._control_socket = None
        self._control_process = None
        self._control_port = None

    # -- realtime streaming ---------------------------------------------------
    def start_stream(self, half: bool = True, bitrate: str = "4M") -> None:
        """Switch screenshot() to pull frames from a live H.264 stream (near-zero latency).
        half=False streams at native resolution (sharper, hotter) — use when small text
        must survive the encode, e.g. the shundo IV read."""
        if self._stream is not None:
            return
        from .stream import ScreenStream

        self._stream = ScreenStream(self.serial, self.adb_path, bitrate=bitrate,
                                    native_size=self.screen_size(), half=half)
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
        def query() -> list[str]:
            out = _quiet_run([adb, "devices"], capture_output=True, text=True, timeout=15).stdout
            found = []
            for line in out.splitlines()[1:]:
                line = line.strip()
                if line and "\tdevice" in line:
                    found.append(line.split("\t")[0])
            return found

        serials = query()

        # MuMu exposes adbd directly on localhost, but it is not added to a newly started
        # desktop adb server until somebody runs `adb connect`.  The bundled adb daemon is
        # deliberately independent from MuMu's old adb_server.exe, so make local MuMu
        # discovery automatic whenever its default endpoint is actually listening.
        mumu_serial = cls.MUMU_SERIAL
        if mumu_serial not in serials:
            try:
                with socket.create_connection(("127.0.0.1", 7555), timeout=0.2):
                    pass
                proc = _quiet_run(
                    [adb, "connect", mumu_serial],
                    capture_output=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    serials = query()
            except (OSError, subprocess.SubprocessError):
                # MuMu is not running (or adb is temporarily busy); keep normal USB/Wi-Fi
                # discovery working and let the next Refresh try again.
                pass
        return serials

    @classmethod
    def adb_connect(cls, serial: str, adb_path: str | None = None) -> None:
        """Connect the adb server to a TCP device ('ip:port'). Raises AdbError on failure."""
        adb = adb_path or find_adb()
        proc = _quiet_run([adb, "connect", serial], capture_output=True, timeout=10)
        out = (proc.stdout or b"").decode("utf-8", "replace")
        # Success prints 'connected to …' or 'already connected to …'.
        if "connected" not in out:
            err = (proc.stderr or b"").decode("utf-8", "replace")
            raise AdbError(f"adb connect {serial}: {(out + err).strip()}")

    def wifi_ip(self) -> str | None:
        """The phone's Wi-Fi IPv4 address, or None if Wi-Fi is down."""
        try:
            out = self._run(["shell", "ip", "addr", "show", "wlan0"])
        except AdbError:
            return None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
        return None

    def enable_wifi_adb(self, port: int = 5555) -> str:
        """Switch this (USB-connected) device's adbd to TCP mode and connect over Wi-Fi.
        Returns the new serial 'ip:port'; afterwards the USB cable can be unplugged."""
        ip = self.wifi_ip()
        if not ip:
            raise AdbError("phone has no Wi-Fi IP — check that Wi-Fi is connected")
        self._run(["tcpip", str(port)])
        time.sleep(2.0)  # adbd restarts in TCP mode
        serial = f"{ip}:{port}"
        Device.adb_connect(serial, self.adb_path)
        return serial

    def screen_size(self) -> tuple[int, int]:
        """(width, height) in pixels. Cached after first read."""
        if self._size is not None:
            return self._size
        out = self._run(["shell", "wm", "size"])
        # "Physical size: 1220x2712" and, when the resolution is overridden (e.g. `wm size`),
        # an extra "Override size: 1080x1920" line. The override is what screencap returns and
        # what taps address, so it must win — and it can appear *after* the physical line.
        physical = override = None
        for line in out.splitlines():
            key, _, val = line.partition(":")
            tok = val.strip()
            if "x" not in tok or not tok.replace("x", "").isdigit():
                continue
            w, h = tok.split("x")
            if key.strip().lower().startswith("override"):
                override = (int(w), int(h))
            elif key.strip().lower().startswith("physical"):
                physical = (int(w), int(h))
        self._size = override or physical
        if self._size is None:
            raise AdbError(f"could not parse screen size from: {out!r}")
        return self._size

    def density(self) -> int | None:
        """Display density in dpi, or None if it can't be read. Like `wm size`, `wm density`
        prints an "Override density" line when set — it wins over "Physical density"."""
        try:
            out = self._run(["shell", "wm", "density"])
        except AdbError:
            return None
        physical = override = None
        for line in out.splitlines():
            key, _, val = line.partition(":")
            tok = val.strip()
            if not tok.isdigit():
                continue
            if key.strip().lower().startswith("override"):
                override = int(tok)
            elif key.strip().lower().startswith("physical"):
                physical = int(tok)
        return override or physical

    # -- capture --------------------------------------------------------------
    def screenshot(self, fresh: bool = False) -> np.ndarray:
        """Current screen as a BGR image. Uses the live stream if started, else a one-shot capture.
        fresh=True forces a one-shot screencap even when streaming — slower (~1s) but free of
        H.264 compression smear, for when a template match on the stream frame fails."""
        if self._stream is not None and not fresh:
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
        x, y = int(x), int(y)
        try:
            self._ensure_control()
            self._control_tap(x, y)
        except Exception:
            self.close_control()
            self._run(["shell", "input", "tap", str(x), str(y)])

    def double_tap(self, x: int, y: int, gap_ms: int = 90) -> None:
        """Send a real double-tap through scrcpy's persistent control socket.

        MuMu takes roughly 700 ms to execute each ``input tap`` command, even when
        both are chained inside one adb shell.  That is far beyond Android's
        double-tap window.  The control socket emits touch down/up events immediately.
        """
        x, y = int(x), int(y)
        gap_s = max(1, int(gap_ms)) / 1000.0
        try:
            self._ensure_control()
            self._control_tap(x, y)
            time.sleep(gap_s)
            self._control_tap(x, y)
        except Exception:
            # Preserve compatibility with devices where scrcpy control cannot start.
            self.close_control()
            self._run(["shell", f"input tap {x} {y}; sleep {gap_s:.3f}; input tap {x} {y}"])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run(
            ["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))]
        )

    def quick_catch(self, berry_start: tuple[int, int], berry_end: tuple[int, int],
                    ball_start: tuple[int, int], ball_end: tuple[int, int],
                    flee_xy: tuple[int, int], throw_duration_ms: int = 240,
                    post_throw_wait_ms: int = 1000, flee_taps: int = 3,
                    flee_gap_ms: int = 200) -> None:
        """Perform a real two-finger Pokemon GO quick-catch via scrcpy control."""
        bsx, bsy = map(int, berry_start)
        bex, bey = map(int, berry_end)
        sx, sy = map(int, ball_start)
        ex, ey = map(int, ball_end)
        fx, fy = map(int, flee_xy)
        self._ensure_control()

        # Exact native Quick Catch sequence: drag Berry right and HOLD, throw/release
        # the ball with the second finger, release Berry, then press Flee three times.
        self._touch(0, 0, bsx, bsy)
        self._touch_line(0, (bsx, bsy), (bex, bey), 60)
        self._touch(0, 1, sx, sy)
        self._touch_line(1, (sx, sy), (ex, ey), throw_duration_ms)
        self._touch(1, 1, ex, ey)
        self._touch(1, 0, bex, bey)
        # Let the throw commit, then press Flee exactly three times at 200 ms gaps. No extra tap at the
        # throw endpoint: that was not part of the gesture and added visible delay.
        # MuMu needs about a second after pointer-up to commit the throw. Fleeing sooner
        # cancels the ball gesture even though the swipe events were delivered correctly.
        time.sleep(max(0, int(post_throw_wait_ms)) / 1000.0)
        tap_count = max(1, int(flee_taps))
        for i in range(tap_count):
            self._control_tap(fx, fy)
            if i + 1 < tap_count:
                time.sleep(max(0, int(flee_gap_ms)) / 1000.0)

    def control_swipe(self, x1: int, y1: int, x2: int, y2: int,
                      duration_ms: int = 240) -> None:
        """Low-latency one-finger swipe over the persistent scrcpy control socket."""
        try:
            self._ensure_control()
            self._touch(0, 0, int(x1), int(y1))
            self._touch_line(0, (int(x1), int(y1)), (int(x2), int(y2)), duration_ms)
            self._touch(1, 0, int(x2), int(y2))
        except Exception:
            self.close_control()
            self.swipe(x1, y1, x2, y2, duration_ms)

    def _ensure_control(self) -> None:
        """Start scrcpy-server in control-only mode and connect its local socket."""
        if self._control_socket is not None:
            return
        server = resource_path("tools/scrcpy-server-v4.0")
        remote = "/data/local/tmp/avc-scrcpy-server-v4.0.jar"
        self._run(["push", server, remote], timeout=30.0)
        scid = (int(time.time() * 1000) ^ id(self)) & 0x7fffffff
        abstract = f"localabstract:scrcpy_{scid:08x}"
        port = int(self._run(["forward", "tcp:0", abstract]).strip())
        command = (
            f"CLASSPATH={remote} app_process / com.genymobile.scrcpy.Server 4.0 "
            f"scid={scid:08x} log_level=warn video=false audio=false control=true "
            "tunnel_forward=true cleanup=false"
        )
        proc = subprocess.Popen(
            self._base_cmd() + ["shell", command], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=_NO_WINDOW,
        )
        deadline = time.monotonic() + 8.0
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            try:
                sock.connect(("127.0.0.1", port))
                # scrcpy handshake: dummy byte proving the device socket is live,
                # followed by the fixed 64-byte device-name field.
                handshake = b""
                while len(handshake) < 65:
                    chunk = sock.recv(65 - len(handshake))
                    if not chunk:
                        raise ConnectionError("scrcpy control socket closed during handshake")
                    handshake += chunk
                if handshake[0] != 0:
                    raise ConnectionError("invalid scrcpy handshake")
                break
            except OSError:
                sock.close()
                if time.monotonic() >= deadline or proc.poll() is not None:
                    proc.terminate()
                    self._run(["forward", "--remove", f"tcp:{port}"])
                    raise AdbError("could not start scrcpy multi-touch control")
                time.sleep(0.1)
        sock.settimeout(5.0)
        self._control_socket = sock
        self._control_process = proc
        self._control_port = port

    def _touch(self, action: int, pointer_id: int, x: int, y: int) -> None:
        w, h = self.screen_size()
        pressure = 0 if action == 1 else 0xffff
        msg = struct.pack(">BBQiiHHHII", 2, action, pointer_id, int(x), int(y),
                          w, h, pressure, 0, 0)
        self._control_socket.sendall(msg)

    def _touch_line(self, pointer_id: int, start: tuple[int, int],
                    end: tuple[int, int], duration_ms: int) -> None:
        steps = max(3, min(12, int(duration_ms) // 25))
        delay = max(0.005, duration_ms / steps / 1000.0)
        x1, y1 = start
        x2, y2 = end
        for i in range(1, steps + 1):
            x = round(x1 + (x2 - x1) * i / steps)
            y = round(y1 + (y2 - y1) * i / steps)
            self._touch(2, pointer_id, x, y)
            time.sleep(delay)

    def _control_tap(self, x: int, y: int) -> None:
        self._touch(0, 0, x, y)
        time.sleep(0.04)
        self._touch(1, 0, x, y)

    def close_control(self) -> None:
        if self._control_socket is not None:
            try:
                self._control_socket.close()
            except OSError:
                pass
            self._control_socket = None
        if self._control_process is not None:
            try:
                self._control_process.terminate()
            except OSError:
                pass
            self._control_process = None
        if self._control_port is not None:
            try:
                self._run(["forward", "--remove", f"tcp:{self._control_port}"])
            except Exception:
                pass
            self._control_port = None

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
        try:
            self._run(["shell", "cmd", "display", "set-brightness", "0.0"])
        except Exception:
            pass

    def restore_dim(self) -> None:
        saved = getattr(self, "_saved_screen", None)
        if not saved:
            return
        if saved["mode"].isdigit():
            self._put_setting("system", "screen_brightness_mode", saved["mode"])
        if saved["bright"].isdigit():
            self._put_setting("system", "screen_brightness", saved["bright"])
            try:
                val = float(saved["bright"]) / 255.0
                val = max(0.0, min(1.0, val))
                self._run(["shell", "cmd", "display", "set-brightness", f"{val:.4f}"])
            except Exception:
                pass
        if saved["stay"].isdigit():
            self._put_setting("global", "stay_on_while_plugged_in", saved["stay"])
        self._saved_screen = None

    def battery_info(self) -> dict:
        """Battery snapshot: {'level': %, 'temp': °C, 'charging': bool}. Missing keys if unparsable."""
        info: dict = {}
        out = self._run(["shell", "dumpsys", "battery"])
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("level:"):
                info["level"] = int(line.split(":")[1])
            elif line.startswith("temperature:"):
                info["temp"] = int(line.split(":")[1]) / 10.0
            elif line.startswith(("AC powered:", "USB powered:", "Wireless powered:")):
                info["charging"] = info.get("charging", False) or line.endswith("true")
        return info

    def kill_server(self) -> None:
        """Stop the background adb server daemon. Important for frozen one-file builds: the
        daemon's executable image is the bundled adb.exe living under PyInstaller's _MEI temp
        dir, and while it runs Windows won't let that dir be deleted — which surfaces as a
        'Failed to remove temporary directory' warning when the app exits. Killing the daemon
        releases the file so cleanup succeeds. Best-effort; errors are ignored."""
        try:
            _quiet_run([self.adb_path, "kill-server"], capture_output=True, timeout=10)
        except Exception:
            pass

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
