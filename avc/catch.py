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


def _load_optional(template_path: str):
    """Load a template if present, else return None (feature simply stays disabled)."""
    path = _resolve(template_path)
    if not os.path.exists(path):
        return None
    try:
        return load_template(path)
    except FileNotFoundError:
        return None


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

    # Encounter detection via camera template + fallback throw position.
    ball_template: str = "templates/camera.png"
    ball_threshold: float = 0.7
    ball_fallback: tuple[int, int] = (610, 2485)  # used only if the ball isn't detected

    # Throw: swipe from the ball straight up toward the Pokémon. Bigger |throw_dy| = harder throw;
    # too hard sails over the Pokémon, so this is deliberately gentle and tunable in the GUI.
    throw_dy: int = -550           # how far up to flick (negative = upward); gentle by default
    throw_duration_ms: int = 240

    # Human-ish jitter so the throw isn't pixel-identical every time.
    jitter_px: int = 8

    # Timing (seconds). These are *max* waits — the routine polls the screen and proceeds the
    # instant the expected state appears, so short cases stay fast and slow ones don't get missed.
    anchor_timeout: float = 3.0     # max wait for the nearby bar to (re)appear at cycle start
    encounter_timeout: float = 3.0  # max wait for the Poké Ball to appear after double-tapping
    catch_timeout: float = 6.0      # max wait for the encounter to end (ball gone) after a throw
    settle_after_catch: float = 1.2  # let the nearby list refresh before the next cycle
    poll_interval: float = 0.08     # pause between polls; cheap now that frames come from the stream
    idle_poll: float = 0.6          # pause between cycles when the nearby bar isn't visible

    # Popups that block the flow. Both are opaque dialogs, so template detection is reliable.
    popup_autowalk_template: str = "templates/popup_autowalk.png"   # "Stop/Pause AutoWalk?" dialog
    popup_speed_template: str = "templates/popup_speed.png"         # "I'M A PASSENGER" green button
    claim_rewards_template: str = "templates/claim_rewards.png"      # "CLAIM REWARDS" level up button
    close_btn_template: str = "templates/close_btn.png"              # Close "X" button
    popup_threshold: float = 0.7

    # AutoWalk: after several empty cycles, tap the spoofer's AutoWalk button to start walking and
    # generate fresh spawns. The button's row is semi-transparent (poor template target), so we
    # instead locate the opaque yellow menu star and tap a fixed offset down to the AutoWalk row.
    menu_star_template: str = "templates/menu_star.png"
    menu_star_threshold: float = 0.55
    autowalk_offset_x: int = 20     # from the star center to the AutoWalk button
    autowalk_offset_y: int = 303
    idle_before_autowalk: int = 3   # consecutive empty cycles before tapping AutoWalk (0 = off)
    autowalk_wait: float = 3.0      # wait after tapping for spawns to appear

    # Stop conditions.
    max_catches: int = 0           # 0 = unlimited


@dataclass
class CatchStats:
    cycles: int = 0
    throws: int = 0
    autowalks: int = 0
    last_event: str = ""   # "throw" | "idle" | "autowalk"


class CatchRoutine:
    def __init__(self, device: Device, config: CatchConfig | None = None) -> None:
        self.device = device
        self.config = config or CatchConfig()
        self._ball = load_template(_resolve(self.config.ball_template))
        self._anchor = load_template(_resolve(self.config.anchor_template))
        self._star = load_template(_resolve(self.config.menu_star_template))
        # Popup templates are optional — a missing one just disables that handler.
        self._popup_autowalk = _load_optional(self.config.popup_autowalk_template)
        self._popup_speed = _load_optional(self.config.popup_speed_template)
        self._claim_rewards = _load_optional(self.config.claim_rewards_template)
        self._close_btn = _load_optional(self.config.close_btn_template)
        self.stats = CatchStats()
        self._idle_streak = 0
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
        return self.config.ball_fallback if matches else None

    def _slot_in(self, frame) -> tuple[int, int] | None:
        matches = find(frame, self._anchor, threshold=self.config.anchor_threshold, scales=(0.9, 1.0, 1.1))
        if not matches:
            return None
        ax, ay = matches[0].center
        return (ax, ay - self.config.slot_offset_y)

    def _handle_popups(self) -> bool:
        """Dismiss blocking dialogs. Returns True if one was handled (and acted on)."""
        frame = self.device.screenshot()

        # If the map screen (nearby anchor) is already visible, there's no blocking popup.
        # This prevents false positives (like matching the close button on the Poké Ball button or calendar).
        if self._slot_in(frame) is not None:
            return False

        # Speed warning "You're going too fast" -> tap the green "I'M A PASSENGER" button.
        if self._popup_speed is not None:
            m = find(frame, self._popup_speed, threshold=self.config.popup_threshold, scales=(0.9, 1.0, 1.1))
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True
        # "Stop/Pause AutoWalk?" dialog -> tap CANCEL to dismiss it.
        if self._popup_autowalk is not None:
            m = find(frame, self._popup_autowalk, threshold=self.config.popup_threshold, scales=(1.0,))
            if m:
                cx, cy = m[0].center
                self.device.tap(cx + 185, cy + 168)
                self.stats.last_event = "popup"
                return True
        # Level-up "CLAIM REWARDS" screen -> tap claim, then tap screen to dismiss rewards until default screen
        if self._claim_rewards is not None:
            m = find(frame, self._claim_rewards, threshold=self.config.popup_threshold, scales=(0.9, 1.0, 1.1))
            if m:
                rx, ry = m[0].center
                self.device.tap(rx, ry)
                self.stats.last_event = "popup"
                
                # Repeatedly tap center to dismiss items until map screen (nearby anchor) is back
                cx, cy = 610, 1000
                deadline = time.monotonic() + 15.0
                while time.monotonic() < deadline and not self.stop_event.is_set():
                    self._interruptible_sleep(0.5)
                    f = self.device.screenshot()
                    if self._slot_in(f) is not None:
                        break
                    # If close button appears in the center bottom region, tap it immediately
                    if self._close_btn is not None:
                        m_close = find(f, self._close_btn, threshold=0.6, scales=(0.9, 1.0, 1.1), region=(400, 2000, 420, 712))
                        if m_close:
                            self.device.tap(*m_close[0].center)
                            self._interruptible_sleep(0.5)
                            continue
                    self.device.tap(cx, cy)
                return True
        # Close button ('X') -> tap it to dismiss any other popup (searched in the center region with 0.6 threshold)
        if self._close_btn is not None:
            m = find(frame, self._close_btn, threshold=0.6, scales=(0.9, 1.0, 1.1), region=(400, 2000, 420, 712))
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True
        return False

    def _try_autowalk(self) -> bool:
        """Tap the AutoWalk button to start walking. Finds the opaque yellow menu star (robust
        wherever the movable menu sits) and taps a fixed offset down onto the AutoWalk row."""
        frame = self.device.screenshot()
        matches = find(frame, self._star, threshold=self.config.menu_star_threshold, scales=(0.8, 0.9, 1.0, 1.1, 1.2))
        if not matches:
            return False
        sx, sy = matches[0].center
        self.device.tap(sx + self.config.autowalk_offset_x, sy + self.config.autowalk_offset_y)
        return True

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

        # Step 0: clear any blocking popup (speed warning, AutoWalk dialog) before doing anything.
        if self._handle_popups():
            self._interruptible_sleep(0.4)

        # Step 1: wait for the nearby bar (its '@' anchor). Polling here rides out the post-catch
        # transition/summary screen instead of wasting a whole cycle on it.
        slot = self._poll(self._slot_in, cfg.anchor_timeout)
        if slot is None:
            if cfg.require_anchor:
                self._interruptible_sleep(cfg.idle_poll)
                return False
            slot = cfg.nearby_slot

        # Step 2: engage it, then WAIT (poll) for the encounter's ball to actually appear.
        # Watching for the ball (instead of a fixed delay) is what stops the "sometimes no
        # pokemon" misses; a short timeout keeps a genuinely-empty slot from stalling long.
        self._double_tap(*slot)
        ball_xy = self._poll(self._ball_in, cfg.encounter_timeout)
        if ball_xy is None:
            return False

        # Step 3: throw, then wait until the nearby bar's '@' anchor reappears — that's the reliable
        # "encounter finished, we're back on the map" signal. (Waiting merely for the ball to vanish
        # fired too early: the ball leaves its rest spot the instant it's thrown, mid-animation.)
        self._throw(ball_xy)
        # Give the throw/catch animation a moment so we don't detect the pre-throw map state.
        self._interruptible_sleep(cfg.settle_after_catch)
        self._poll(self._slot_in, cfg.catch_timeout)
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
            self.stats.last_event = "throw" if threw else "idle"
            if on_event:
                on_event(self.stats, threw)

            # Dry spell handling: after several empty cycles, tap AutoWalk to go find new spawns.
            if threw:
                self._idle_streak = 0
            else:
                self._idle_streak += 1
                if cfg.idle_before_autowalk and self._idle_streak >= cfg.idle_before_autowalk:
                    if self._try_autowalk():
                        self.stats.autowalks += 1
                        self.stats.last_event = "autowalk"
                        if on_event:
                            on_event(self.stats, False)
                        self._interruptible_sleep(cfg.autowalk_wait)
                    self._idle_streak = 0

            if cfg.max_catches and self.stats.throws >= cfg.max_catches:
                break

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()
