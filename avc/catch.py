"""Pokémon catch routine.

Per cycle:
  1. Double-tap the first slot of the nearby-Pokémon sidebar (the top one). The client
     brings that Pokémon up and opens the encounter; after a catch the list auto-advances,
     so the same slot position always holds the next target.
  2. Confirm we're actually in an encounter by finding the throwable Poké Ball.
  3. Swipe up from the ball to throw it.
  4. Wait out the catch animation, then repeat.

The Poké Ball is the anchor: it looks the same for every Pokémon, so one template covers
all of them, and detecting it is what gates the throw (no ball on screen -> no encounter ->
skip the swipe instead of flailing).
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass

import os

from .device import Device
from .resources import resource_path
from .vision import find, load_template


def _resolve(template_path: str) -> str:
    """Use an explicit/existing path as-is; otherwise resolve inside the bundle's templates/."""
    if os.path.isabs(template_path) or os.path.exists(template_path):
        return template_path
    return resource_path(template_path)


@dataclass
class CatchConfig:
    # Nearby sidebar is located dynamically via the distinctive '@' target icon at its bottom,
    # so it keeps working even when the bar moves. The first (top) slot sits a fixed distance
    # above that anchor.
    anchor_template: str = "templates/nearby_anchor.png"
    anchor_threshold: float = 0.7
    slot_offset_y: int = 770        # pixels above the '@' anchor to the first Pokémon slot
    # Fallback fixed slot, used only if the anchor can't be found and require_anchor is False.
    nearby_slot: tuple[int, int] = (940, 205)
    require_anchor: bool = True     # if True, skip the cycle when the '@' bar isn't on screen
    double_tap_gap_ms: int = 90

    # Poké Ball template + detection.
    ball_template: str = "templates/pokeball.png"
    ball_threshold: float = 0.7
    ball_fallback: tuple[int, int] = (610, 2485)  # used only if the ball isn't detected

    # Throw: swipe from the ball straight up toward the Pokémon.
    throw_dy: int = -1150          # how far up to flick (negative = upward)
    throw_duration_ms: int = 180

    # Human-ish jitter so the throw isn't pixel-identical every time.
    jitter_px: int = 8

    # Timing (seconds). These are *max* waits — the routine polls the screen and proceeds the
    # instant the expected state appears, so short cases stay fast and slow ones don't get missed.
    encounter_timeout: float = 5.0  # max wait for the Poké Ball to appear after double-tapping
    catch_timeout: float = 6.0      # max wait for the encounter to end (ball gone) after a throw
    poll_interval: float = 0.15     # extra pause between polls (a screencap already takes ~0.9s)
    idle_poll: float = 0.6          # pause between cycles when the nearby bar isn't visible

    # Stop conditions.
    max_catches: int = 0           # 0 = unlimited


@dataclass
class CatchStats:
    cycles: int = 0
    throws: int = 0


class CatchRoutine:
    def __init__(self, device: Device, config: CatchConfig | None = None) -> None:
        self.device = device
        self.config = config or CatchConfig()
        self._ball = load_template(_resolve(self.config.ball_template))
        self._anchor = load_template(_resolve(self.config.anchor_template))
        self.stats = CatchStats()
        # Control flags used by the GUI; ignored by the plain CLI loop.
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep in small slices so Stop takes effect promptly."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return
            time.sleep(min(0.05, deadline - time.monotonic()))

    def _wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.1)

    def _jitter(self, x: int, y: int) -> tuple[int, int]:
        j = self.config.jitter_px
        if j <= 0:
            return x, y
        return x + random.randint(-j, j), y + random.randint(-j, j)

    def _double_tap(self, x: int, y: int) -> None:
        jx, jy = self._jitter(x, y)
        self.device.tap(jx, jy)
        time.sleep(self.config.double_tap_gap_ms / 1000.0)
        self.device.tap(jx, jy)

    def _ball_in(self, frame) -> tuple[int, int] | None:
        matches = find(frame, self._ball, threshold=self.config.ball_threshold, scales=(0.95, 1.0, 1.05))
        return matches[0].center if matches else None

    def _slot_in(self, frame) -> tuple[int, int] | None:
        matches = find(frame, self._anchor, threshold=self.config.anchor_threshold, scales=(0.9, 1.0, 1.1))
        if not matches:
            return None
        ax, ay = matches[0].center
        return (ax, ay - self.config.slot_offset_y)

    def _poll(self, predicate, timeout: float):
        """Screenshot repeatedly until predicate(frame) is truthy or timeout. Returns its value or None."""
        deadline = time.monotonic() + timeout
        while True:
            if self.stop_event.is_set():
                return None
            self._wait_if_paused()
            result = predicate(self.device.screenshot())
            if result:
                return result
            if time.monotonic() >= deadline:
                return None
            time.sleep(self.config.poll_interval)

    def _throw(self, ball_xy: tuple[int, int]) -> None:
        bx, by = self._jitter(*ball_xy)
        ex, ey = self._jitter(bx, by + self.config.throw_dy)
        self.device.swipe(bx, by, ex, ey, duration_ms=self.config.throw_duration_ms)
        self.stats.throws += 1

    def run_once(self) -> bool:
        """One catch cycle. Returns True if a ball was thrown."""
        cfg = self.config
        self.stats.cycles += 1

        # Step 1: find the nearby bar via its '@' anchor. One screenshot — if the bar isn't there
        # (mid-animation, or genuinely no spawns), skip this cycle quickly.
        slot = self._slot_in(self.device.screenshot())
        if slot is None:
            if cfg.require_anchor:
                self._interruptible_sleep(cfg.idle_poll)
                return False
            slot = cfg.nearby_slot

        # Step 2: engage it, then WAIT (poll) for the encounter's ball to actually appear.
        # This is what fixes the "sometimes no pokemon" misses: the encounter takes a variable
        # amount of time to open, so we watch for the ball instead of guessing a fixed delay.
        self._double_tap(*slot)
        ball_xy = self._poll(self._ball_in, cfg.encounter_timeout)
        if ball_xy is None:
            return False

        # Step 3: throw, then wait for the encounter to actually end (ball gone) before the next
        # cycle — otherwise we'd double-tap during the catch animation and miss.
        self._throw(ball_xy)
        self._poll(lambda frame: self._ball_in(frame) is None, cfg.catch_timeout)
        return True

    def run(self, on_event=None) -> None:
        """Blocking loop. Honors stop_event / pause_event so a GUI can drive it in a thread."""
        cfg = self.config
        self.stop_event.clear()
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            threw = self.run_once()
            if on_event:
                on_event(self.stats, threw)
            if cfg.max_catches and self.stats.throws >= cfg.max_catches:
                break

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()
