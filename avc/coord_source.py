"""Local, in-memory coordinate queue fed by the Edge collector extension.

The HTTP bridge binds to loopback only. Coordinates are deliberately ephemeral: closing the
desktop app clears the queue, while the extension retains its own exportable history.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


COORD_RE = re.compile(r"^(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)$")


@dataclass(frozen=True)
class CoordItem:
    coordinate: str
    latitude: float
    longitude: float
    pokemon: str = ""
    source_url: str = ""
    discord_channel_url: str = ""
    captured_at: str = ""
    source: str = ""
    note: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CoordItem":
        raw = str(payload.get("coordinate", "")).strip()
        match = COORD_RE.fullmatch(raw)
        if not match:
            raise ValueError("coordinate must be 'latitude,longitude'")
        latitude = float(match.group(1))
        longitude = float(match.group(2))
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("coordinate is outside the valid latitude/longitude range")
        return cls(
            coordinate=f"{match.group(1)},{match.group(2)}",
            latitude=latitude,
            longitude=longitude,
            pokemon=str(payload.get("pokemon", ""))[:120],
            source_url=str(payload.get("url", payload.get("source_url", "")))[:500],
            discord_channel_url=str(payload.get("discordChannelUrl", payload.get("discord_channel_url", "")))[:500],
            captured_at=str(payload.get("capturedAt", payload.get("captured_at", "")))[:80],
            source=str(payload.get("source", ""))[:120],
            note=str(payload.get("note", ""))[:160],
        )

    @property
    def key(self) -> str:
        return self.source_url or f"{self.coordinate}|{self.captured_at}|{self.pokemon}"


class CoordQueue:
    """Thread-safe FIFO with source-link deduplication."""

    def __init__(self, max_items: int = 2000) -> None:
        self.max_items = max(1, int(max_items))
        self._items: deque[CoordItem] = deque()
        self._seen: set[str] = set()
        self._completed = 0
        self._condition = threading.Condition()

    def put(self, item: CoordItem) -> bool:
        with self._condition:
            if item.key in self._seen:
                return False
            if len(self._items) >= self.max_items:
                old = self._items.popleft()
                self._seen.discard(old.key)
            self._items.append(item)
            self._seen.add(item.key)
            self._condition.notify()
            return True

    def get(self, timeout: float = 0.0) -> CoordItem | None:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while not self._items:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            return self._items.popleft()

    def qsize(self) -> int:
        with self._condition:
            return len(self._items)

    def mark_completed(self) -> int:
        """Record one visually confirmed Pokémon check and return the session total."""
        with self._condition:
            self._completed += 1
            return self._completed

    def completed_count(self) -> int:
        with self._condition:
            return self._completed

    def clear(self) -> None:
        with self._condition:
            self._items.clear()
            self._seen.clear()
            self._completed = 0

    def snapshot(self, limit: int = 50) -> list[CoordItem]:
        with self._condition:
            return list(self._items)[:max(0, limit)]


class _BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, coord_queue: CoordQueue) -> None:
        self.coord_queue = coord_queue
        super().__init__(address, handler)


class _Handler(BaseHTTPRequestHandler):
    server: _BridgeServer

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/health":
            self._json(404, {"ok": False, "error": "not found"})
            return
        self._json(200, {
            "ok": True,
            "queued": self.server.coord_queue.qsize(),
            "completed": self.server.coord_queue.completed_count(),
        })

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/session":
            self.server.coord_queue.clear()
            self._json(200, {"ok": True, "queued": 0, "completed": 0})
            return
        if path != "/coords":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            item = CoordItem.from_payload(payload)
            added = self.server.coord_queue.put(item)
            self._json(200, {
                "ok": True,
                "added": added,
                "queued": self.server.coord_queue.qsize(),
                "item": asdict(item),
            })
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._json(400, {"ok": False, "error": str(error)})

    def log_message(self, _format: str, *_args) -> None:
        # Never write extension traffic to a console (the packaged app has none anyway).
        return


class CoordBridge:
    """Lifecycle wrapper for the loopback HTTP bridge."""

    def __init__(self, coord_queue: CoordQueue, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.coord_queue = coord_queue
        self.host = host
        self.port = int(port)
        self._server: _BridgeServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        if self._server is not None:
            return self.port
        server = _BridgeServer((self.host, self.port), _Handler, self.coord_queue)
        self._server = server
        self.port = int(server.server_address[1])
        self._thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.05),
            name="coord-bridge",
            daemon=True,
        )
        self._thread.start()
        return self.port

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
