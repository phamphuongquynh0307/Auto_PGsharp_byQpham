"""ADB device control: capture the screen and dispatch taps/swipes.

Everything here shells out to `adb`. Screen capture uses `exec-out screencap -p` piped
straight into memory (no temp file on the phone) and decoded with OpenCV.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import subprocess
import socket
import struct
import sys
import threading
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


# ADB's server is shared by all subprocesses. Serialising connect operations prevents a
# refresh/reconnect and the Wireless Debug dialog from racing each other and leaving a freshly
# discovered transport in the transient ``offline`` state.
_ADB_CONNECT_LOCK = threading.Lock()


@dataclass(frozen=True)
class MdnsService:
    """One service advertised by ``adb mdns services``."""

    instance: str
    service_type: str
    endpoint: str


class Device:
    MUMU_SERIAL = "127.0.0.1:7555"

    # How stale a streamed frame may be before it counts as no frame at all, and how long to
    # wait for a fresh one before paying for a one-shot capture. See ScreenStream.latest: the
    # stream is relaunched every 175s and the frame from before that gap otherwise stays live.
    # 0.5s is well clear of the ~30ms a healthy stream delivers at, so a normal run never
    # touches this path; 0.6s of waiting is roughly what the screencap fallback costs anyway,
    # so a restart is ridden out rather than paid for whenever the stream comes back in time.
    STALE_FRAME_AGE = 0.5
    STALE_FRAME_WAIT = 0.6

    def __init__(self, serial: str | None = None, adb_path: str | None = None) -> None:
        self.adb_path = adb_path or find_adb()
        self.serial = serial
        self._size: tuple[int, int] | None = None
        self._stream = None  # ScreenStream when realtime capture is enabled
        self._last_frame_sequence = 0
        self._control_socket = None
        self._control_process = None
        self._control_port = None

    # -- realtime streaming ---------------------------------------------------
    def start_stream(self, half: bool = True, bitrate: str = "2M") -> None:
        """Switch screenshot() to pull frames from a live H.264 stream (near-zero latency).
        half=False streams at native resolution (sharper, hotter) — use when small text
        must survive the encode, e.g. the shundo IV read."""
        if self._stream is not None:
            return
        from .stream import ScreenStream

        self._stream = ScreenStream(self.serial, self.adb_path, bitrate=bitrate,
                                    native_size=self.screen_size(), half=half)
        self._last_frame_sequence = 0
        self._stream.start()

    def stop_stream(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream = None
            self._last_frame_sequence = 0

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
    def adb_connect(
        cls,
        serial: str,
        adb_path: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Connect and verify a TCP device ('ip:port'). Raises AdbError on failure.

        ``adb connect`` can print ``connected`` before the transport has actually entered the
        ``device`` state. Treating that intermediate result as ready is what caused the GUI to
        start an endless reconnect loop on Wireless Debugging.
        """
        adb = adb_path or find_adb()
        endpoint = cls.normalize_tcp_endpoint(serial)
        last_detail = "no response"
        for attempt in range(3):
            with _ADB_CONNECT_LOCK:
                proc = _quiet_run(
                    [adb, "connect", endpoint], capture_output=True, timeout=timeout,
                )
                out = cls._proc_text(proc.stdout)
                err = cls._proc_text(proc.stderr)
                # Success prints 'connected to …' or 'already connected to …'. Some adb builds
                # put the message on stderr, so inspect both streams.
                detail = (out + err).strip()
                if proc.returncode == 0 and "connected" in detail.lower():
                    state = _quiet_run(
                        [adb, "-s", endpoint, "get-state"],
                        capture_output=True,
                        timeout=min(5.0, timeout),
                    )
                    state_text = cls._proc_text(state.stdout).strip().lower()
                    if state.returncode == 0 and state_text == "device":
                        return
                    last_detail = f"transport state={state_text or 'unknown'}"
                else:
                    last_detail = detail or "adb connect failed"
            if attempt < 2:
                time.sleep(0.25)
        raise AdbError(f"adb connect {endpoint}: {last_detail}")

    @staticmethod
    def normalize_tcp_endpoint(endpoint: str) -> str:
        """Validate and canonicalise an ADB ``IP:port`` endpoint.

        Wireless Debugging deliberately changes its TLS port, so accepting a complete
        endpoint is safer than guessing or scanning ports. Hostnames are not accepted here:
        Android displays a literal LAN address and keeping this parser strict also prevents
        accidental command-like input from reaching adb.
        """
        raw = endpoint.strip()
        if raw.startswith("["):
            close = raw.find("]")
            if close < 0 or close + 1 >= len(raw) or raw[close + 1] != ":":
                raise ValueError("expected [IPv6]:port")
            host = raw[1:close]
            port_text = raw[close + 2:]
        else:
            host, separator, port_text = raw.rpartition(":")
            if not separator:
                raise ValueError("expected IP:port")
        try:
            address = ipaddress.ip_address(host)
            port = int(port_text)
        except (ValueError, TypeError) as exc:
            raise ValueError("expected a valid IP:port") from exc
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if address.version == 6:
            return f"[{address.compressed}]:{port}"
        return f"{address.compressed}:{port}"

    @staticmethod
    def _proc_text(value) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value or ""

    @classmethod
    def mdns_services(cls, adb_path: str | None = None) -> list[MdnsService]:
        """Return valid services found by adb's mDNS discovery backend."""
        adb = adb_path or find_adb()
        proc = _quiet_run(
            [adb, "mdns", "services"], capture_output=True, text=True, timeout=8,
        )
        if proc.returncode != 0:
            detail = (cls._proc_text(proc.stdout) + cls._proc_text(proc.stderr)).strip()
            raise AdbError(f"adb mdns services: {detail}")

        services: list[MdnsService] = []
        for raw_line in cls._proc_text(proc.stdout).splitlines():
            line = raw_line.strip()
            if not line or line.lower().startswith("list of discovered"):
                continue
            parts = line.split()
            if len(parts) != 3 or not parts[1].startswith("_adb"):
                continue
            try:
                endpoint = cls.normalize_tcp_endpoint(parts[2])
            except ValueError:
                continue
            services.append(MdnsService(parts[0], parts[1], endpoint))
        return services

    @classmethod
    def discover_wireless(cls, adb_path: str | None = None) -> list[str]:
        """Discover paired Android 11+ Wireless Debugging connect endpoints."""
        endpoints: list[str] = []
        for service in cls.mdns_services(adb_path):
            if service.service_type != "_adb-tls-connect._tcp":
                continue
            if service.endpoint not in endpoints:
                endpoints.append(service.endpoint)
        return endpoints

    @classmethod
    def connect_discovered_wireless(
        cls,
        preferred_hosts: list[str] | tuple[str, ...] = (),
        adb_path: str | None = None,
        discovery_attempts: int = 1,
        retry_delay: float = 0.5,
    ) -> str | None:
        """Connect a paired Wireless Debugging endpoint advertised over mDNS.

        Android may publish the service a moment after Wireless Debugging is enabled, and its
        TLS port can rotate after a reconnect. A short bounded retry window handles that race
        without making a refresh hang indefinitely. Previously used phone IPs are preferred when
        several devices are visible on the LAN.
        """
        preferred = {host.strip("[]") for host in preferred_hosts if host}
        attempts = max(1, int(discovery_attempts))
        delay = max(0.0, float(retry_delay))
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                endpoints = cls.discover_wireless(adb_path)
                last_error = None
            except (AdbError, subprocess.SubprocessError) as exc:
                # The adb mDNS backend can briefly report a stopped daemon while the phone or
                # adb server is settling. Keep the bounded retry window useful for that case.
                endpoints = []
                last_error = exc

            def priority(endpoint: str) -> tuple[int, str]:
                host = endpoint.rsplit(":", 1)[0].strip("[]")
                return (0 if host in preferred else 1, endpoint)

            for endpoint in sorted(endpoints, key=priority):
                try:
                    cls.adb_connect(endpoint, adb_path)
                    return endpoint
                except (AdbError, subprocess.SubprocessError):
                    continue
            if attempt + 1 < attempts and delay:
                time.sleep(delay)
        if last_error is not None:
            raise last_error
        return None

    @classmethod
    def adb_pair(cls, endpoint: str, pairing_code: str, adb_path: str | None = None) -> str:
        """Pair once with Android Wireless Debugging; the code is never persisted."""
        serial = cls.normalize_tcp_endpoint(endpoint)
        code = pairing_code.strip()
        if not re.fullmatch(r"\d{6}", code):
            raise ValueError("pairing code must contain exactly 6 digits")
        adb = adb_path or find_adb()
        proc = _quiet_run(
            [adb, "pair", serial, code], capture_output=True, timeout=15,
        )
        out = cls._proc_text(proc.stdout)
        err = cls._proc_text(proc.stderr)
        detail = (out + err).strip()
        if proc.returncode != 0 or "successfully paired" not in detail.lower():
            # Do not include the command (which contains the short-lived pairing code).
            raise AdbError(f"adb pair {serial}: {detail}")
        return serial

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
    def screenshot(self, fresh: bool = False, next_frame: bool = False) -> np.ndarray:
        """Current screen as a BGR image. Uses the live stream if started, else a one-shot capture.
        fresh=True forces a one-shot screencap even when streaming — slower (~1s) but free of
        H.264 compression smear, for when a template match on the stream frame fails."""
        if self._stream is not None and not fresh:
            frame, sequence = self._stream.latest(
                timeout=5.0 if next_frame else self.STALE_FRAME_WAIT,
                after_sequence=self._last_frame_sequence if next_frame else None,
                with_sequence=True,
                max_age=self.STALE_FRAME_AGE,
            )
            if frame is not None:
                self._last_frame_sequence = sequence
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

    def ui_dump(self, timeout: float = 8.0) -> str | None:
        """The Android view hierarchy as XML, or None if it could not be read.

        Costs ~1.6s (against ~25ms for a screenshot), so callers must treat it as an expensive
        one-off, never as something to poll. uiautomator also refuses outright while the UI is
        animating, which is a normal outcome here rather than an error — hence None instead of
        an exception, so callers fall back to their pixel path without special-casing.
        """
        remote = "/sdcard/avc-ui.xml"
        try:
            self._run(["shell", "uiautomator", "dump", remote], timeout=timeout)
            xml = self._run(["exec-out", "cat", remote], binary=True, timeout=timeout)
        except Exception:
            return None
        text = xml.decode("utf-8", "replace")
        return text if "<node" in text else None

    def adb_tap(self, x: int, y: int) -> None:
        """Send an independent Android input tap without reusing scrcpy touch state."""
        self._run(["shell", "input", "tap", str(int(x)), str(int(y))])

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
        time.sleep(0.08)
        self._touch(1, 0, bex, bey)
        time.sleep(0.08)
        # Wi-Fi control can occasionally lose an UP while accepting all preceding MOVE
        # packets, leaving the ball visibly held at the flick endpoint. Duplicate UPs are
        # harmless when already released and recover that lost-packet state when needed.
        self._touch(1, 1, ex, ey)
        self._touch(1, 0, bex, bey)
        time.sleep(0.08)
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

    def quick_catch_throw(self, berry_start: tuple[int, int], berry_end: tuple[int, int],
                          ball_start: tuple[int, int], ball_end: tuple[int, int],
                          throw_duration_ms: int = 100) -> None:
        """Perform only the two-finger Quick Catch throw; the routine exits adaptively.

        Keeping Flee outside this low-level gesture lets the vision loop confirm that the
        encounter is still open before retrying, instead of blindly tapping onto the map.
        """
        bsx, bsy = map(int, berry_start)
        bex, bey = map(int, berry_end)
        sx, sy = map(int, ball_start)
        ex, ey = map(int, ball_end)
        self._ensure_control()
        self._touch(0, 0, bsx, bsy)
        self._touch_line(0, (bsx, bsy), (bex, bey), 80)
        time.sleep(0.02)  # let the Berry drawer settle while pointer 0 remains held
        self._touch(0, 1, sx, sy)
        time.sleep(0.02)  # make sure pointer 1 owns the ball before the fast flick
        self._touch_line(1, (sx, sy), (ex, ey), throw_duration_ms)
        self._touch(1, 1, ex, ey)
        self._touch(1, 0, bex, bey)

    def control_swipe(self, x1: int, y1: int, x2: int, y2: int,
                      duration_ms: int = 240) -> None:
        """Low-latency one-finger swipe over the persistent scrcpy control socket."""
        try:
            self._ensure_control()
            self._touch(0, 0, int(x1), int(y1))
            self._touch_line(0, (int(x1), int(y1)), (int(x2), int(y2)), duration_ms)
            self._touch(1, 0, int(x2), int(y2))
            # A duplicate UP is harmless and covers a lossy Wi-Fi control packet without
            # forcing the next catch to rebuild the entire scrcpy control server.
            self._touch(1, 0, int(x2), int(y2))
        except Exception:
            self.close_control()
            self.swipe(x1, y1, x2, y2, duration_ms)

    def release_control_pointers(self) -> None:
        """Release stale scrcpy contacts while keeping the control channel connected."""
        if self._control_socket is None:
            return
        try:
            # Both pointer ids are used by Quick Catch. Extra UP packets on an already-released
            # contact do not create a tap, but recover a final UP lost on a Wi-Fi connection.
            for _ in range(2):
                self._touch(1, 1, 0, 0)
                self._touch(1, 0, 0, 0)
        except Exception:
            # A genuinely dead socket is rebuilt lazily by the next gesture.
            self.close_control()

    # -- interactive pointer (live view) --------------------------------------
    # A real press/move/release trio, so dragging a finger across the mirrored screen
    # behaves like it does on the phone: the map pans and flings instead of receiving a
    # single teleporting tap. Same control socket the routines use.
    def touch_down(self, x: int, y: int) -> None:
        self._ensure_control()
        self._touch(0, 0, int(x), int(y))

    def touch_move(self, x: int, y: int) -> None:
        if self._control_socket is None:
            return
        self._touch(2, 0, int(x), int(y))

    def touch_up(self, x: int, y: int) -> None:
        if self._control_socket is None:
            return
        self._touch(1, 0, int(x), int(y))

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

    def clear_text(self, max_chars: int = 64) -> None:
        """Delete a bounded existing field value using one ADB command."""
        count = max(1, min(256, int(max_chars)))
        self._run([
            "shell", "input", "keyevent", "KEYCODE_MOVE_END", *(["KEYCODE_DEL"] * count)
        ])

    def input_coordinate(self, coordinate: str) -> None:
        """Type a validated ``latitude,longitude`` with deterministic Android key events.

        ``adb shell input text`` occasionally loses punctuation or a leading minus through
        MuMu's active IME. Physical key events avoid that IME text-conversion path while still
        being sent in one ADB command.
        """
        text = str(coordinate).strip()
        if not text or any(char not in "-0123456789.," for char in text):
            raise ValueError("coordinate contains unsupported input characters")
        punctuation = {
            "-": "KEYCODE_MINUS",
            ".": "KEYCODE_PERIOD",
            ",": "KEYCODE_COMMA",
        }
        keycodes = [punctuation.get(char, f"KEYCODE_{char}") for char in text]
        self._run(["shell", "input", "keyevent", *keycodes])

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
