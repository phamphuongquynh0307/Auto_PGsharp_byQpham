"""Pokémon catch routine.

Per cycle:
  1. Double-tap the first slot of the nearby-Pokémon sidebar (the top one). The client
     brings that Pokémon up and opens the encounter; after a catch the list auto-advances,
     so the same slot position always holds the next target.
  2. Confirm we're actually in an encounter by finding the throwable Poké Ball.
  3. Swipe up from the ball to throw it.
  4. Wait out the catch animation, then repeat.

The camera icon marks the encounter opening; it only *times* the throw (throw the moment it
shows). If it never shows the routine throws anyway — a stray swipe on the map is harmless
and cheaper than a missed catch — but the cycle still counts as empty so the AutoWalk
dry-spell logic keeps working.
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
    # The '@' anchor lives on the nearby sidebar; its height varies with how many
    # Pokémon are listed. Searching just that strip is ~10x cheaper than the full frame.
    # The strip sits around x≈880 (anchor center), so the region spans x=760..1220 to
    # cover it with margin; a region that starts at x=950 misses the anchor entirely
    # (its 122px-wide box lands left of that edge) and the whole cycle is skipped.
    anchor_region: tuple[int, int, int, int] = (760, 200, 460, 1800)
    slot_offset_y: int = 770        # pixels above the '@' anchor to the first Pokémon slot
    # Fallback fixed slot, used only if the anchor can't be found and require_anchor is False.
    nearby_slot: tuple[int, int] = (940, 205)
    require_anchor: bool = True     # if True, skip the cycle when the '@' bar isn't on screen
    double_tap_gap_ms: int = 90

    # Encounter detection via camera template + fallback throw position.
    ball_template: str = "templates/camera.png"
    ball_threshold: float = 0.7
    # Throw start point. Sits on the encounter ball's upper half: high enough that a blind
    # throw on the map (y >= 2467 is the map's pokeball menu button) can't press the menu.
    ball_fallback: tuple[int, int] = (610, 2380)
    # The encounter camera icon sits at a fixed spot at the top center (~610, 181).
    ball_region: tuple[int, int, int, int] = (430, 40, 360, 300)

    # Out of balls: in an encounter the ball-count badge reads "x0" — a distinctive red pill at
    # the bottom center. When it shows we're out of Poké Balls: flee the encounter, alert Discord,
    # and hold off catching for a while (still AutoWalking) so the bag can refill instead of
    # burning cycles on an empty encounter. Matched in colour so a red "x0" can't be confused
    # with a neutral non-zero count.
    out_of_balls_template: str = "templates/out_of_balls.png"
    out_of_balls_threshold: float = 0.72
    out_of_balls_region: tuple[int, int, int, int] = (390, 2545, 340, 167)
    flee_xy: tuple[int, int] = (120, 170)   # encounter flee (running-man) button, top-left
    no_balls_pause: float = 600.0           # seconds to hold off catching when out of balls (10 min)
    no_balls_walk_interval: float = 15.0    # re-check AutoWalk this often during the hold-off

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
    close_btn_blue_template: str = "templates/close_btn_blue.png"    # Close "X" button (blue)
    close_btn_white_template: str = "templates/close_btn_white.png"  # Close "X" button (white)
    popup_threshold: float = 0.7
    # The Pokéstop photo-disc screen's own 'X' sits at a fixed spot at the bottom center;
    # used as the tap fallback when template matching misses it (the backdrop varies).
    pokestop_close_xy: tuple[int, int] = (610, 2540)

    # AutoWalk: after several empty cycles, tap the spoofer's AutoWalk button to start walking and
    # generate fresh spawns. The button's row is semi-transparent (poor template target), so we
    # instead locate the opaque yellow menu star and tap a fixed offset down to the AutoWalk row.
    # The star template is a tight crop of the star core (yellow body + pokéball) matched in
    # colour, so yellow map clutter (event Pikachu, balloons) can't outscore it.
    menu_star_template: str = "templates/menu_star.png"
    menu_star_threshold: float = 0.7
    autowalk_offset_x: int = 100    # from the star center onto the AutoWalk row
    autowalk_offset_y: int = 300
    # The AutoWalk row's paused icon ('⊘'). When visible, the walk stalled and a re-tap is safe;
    # without it a started walk is assumed running and is never tapped again (Stop dialog risk).
    autowalk_paused_template: str = "templates/autowalk_paused.png"
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
        self._close_btn_blue = _load_optional(self.config.close_btn_blue_template)
        self._close_btn_white = _load_optional(self.config.close_btn_white_template)
        self._aw_paused = _load_optional(self.config.autowalk_paused_template)
        self._noball_tpl = _load_optional(self.config.out_of_balls_template)
        self.stats = CatchStats()
        self._idle_streak = 0
        self._autowalk_active = False
        self._no_balls = False   # set by run_once when the "x0" badge is seen; consumed by run()
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
        # One adb invocation for both taps — two tap() round-trips over Wi-Fi adb are
        # too far apart (~0.5s) for the game to read them as a double-tap.
        jx, jy = self._jitter(x, y)
        self.device.double_tap(jx, jy)

    def _ball_in(self, frame) -> tuple[int, int] | None:
        matches = find(frame, self._ball, threshold=self.config.ball_threshold, scales=(0.95, 1.0, 1.05),
                       region=self.config.ball_region)
        return self.config.ball_fallback if matches else None

    def _is_out_of_balls(self, frame) -> bool:
        """True when the encounter's ball-count badge reads 'x0' (the red pill at the bottom
        centre) — i.e. we have no Poké Balls left. Colour match so it can't be confused with a
        neutral non-zero count."""
        if self._noball_tpl is None:
            return False
        matches = find(frame, self._noball_tpl, threshold=self.config.out_of_balls_threshold,
                       scales=(0.9, 1.0, 1.1), grayscale=False, region=self.config.out_of_balls_region)
        return bool(matches)

    def _slot_in(self, frame) -> tuple[int, int] | None:
        matches = find(frame, self._anchor, threshold=self.config.anchor_threshold, scales=(0.9, 1.0, 1.1),
                       region=self.config.anchor_region)
        if not matches:
            return None
        ax, ay = matches[0].center
        return (ax, ay - self.config.slot_offset_y)

    def _is_pokestop_screen(self, frame) -> bool:
        """True when the Pokéstop photo-disc screen is up. Its giant blue pin fills both
        sides of the screen at the disc's height (fixed UI, unaffected by day/night tint),
        so two small side patches being solidly blue identifies it. Knowing we're on this
        screen lets the close handler tap the X's known fixed spot instead of trusting a
        template match that sometimes lands a stray click elsewhere."""
        h, w = frame.shape[:2]
        y0, y1 = int(h * 0.42), int(h * 0.50)
        for x0, x1 in ((int(w * 0.04), int(w * 0.14)), (int(w * 0.86), int(w * 0.96))):
            patch = frame[y0:y1, x0:x1]
            b = patch[..., 0].astype(int)
            g = patch[..., 1].astype(int)
            r = patch[..., 2].astype(int)
            blueish = (b > 140) & (b - r > 60) & (b - g > 10)
            if blueish.mean() < 0.6:
                return False
        return True

    def _handle_popups(self) -> bool:
        """Dismiss blocking dialogs. Returns True if one was handled (and acted on)."""
        frame = self.device.screenshot()

        # Speed warning "You're going too fast" -> tap the green "I'M A PASSENGER" button.
        # Popups render at a fixed size on a given device, so a single scale is enough.
        if self._popup_speed is not None:
            m = find(frame, self._popup_speed, threshold=self.config.popup_threshold, scales=(1.0,))
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
            m = find(frame, self._claim_rewards, threshold=self.config.popup_threshold, scales=(1.0,))
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
                    for btn in (self._close_btn, self._close_btn_blue, self._close_btn_white):
                        if btn is not None:
                            m_close = find(f, btn, threshold=0.7, scales=(0.9, 1.0, 1.1), region=(400, 2000, 420, 712))
                            if m_close:
                                self.device.tap(*m_close[0].center)
                                self._interruptible_sleep(0.5)
                                break
                    self.device.tap(cx, cy)
                return True
        # Pokéstop photo-disc screen -> close it via its bottom-center 'X'. The X always sits
        # at the same spot, so search only a tight box around it and, if the template still
        # misses (the backdrop behind the X varies), tap that fixed spot directly. This makes
        # the close both guaranteed and immune to stray matches elsewhere on the screen.
        # (_ball_in guards against a false positive while an encounter is up.)
        if self._is_pokestop_screen(frame) and self._ball_in(frame) is None:
            fx, fy = self.config.pokestop_close_xy
            region = (fx - 160, fy - 160, 320, 320)
            for btn in (self._close_btn_white, self._close_btn, self._close_btn_blue):
                if btn is not None:
                    m = find(frame, btn, threshold=0.7, scales=(0.9, 1.0, 1.1), region=region)
                    if m:
                        fx, fy = m[0].center
                        break
            self.device.tap(fx, fy)
            self.stats.last_event = "popup"
            return True
        # Close button ('X') -> tap it to dismiss any other popup (searched in the center region with 0.7 threshold).
        # Supports teal/green, blue, and white variations of the close button.
        for btn in (self._close_btn, self._close_btn_blue, self._close_btn_white):
            if btn is not None:
                m = find(frame, btn, threshold=0.7, scales=(0.9, 1.0, 1.1), region=(400, 2000, 420, 712))
                if m:
                    x, y = m[0].center
                    self.device.tap(x, y)
                    self.stats.last_event = "popup"
                    return True
        return False

    def _try_autowalk(self) -> bool:
        """Make AutoWalk walk. Finds the yellow menu star (colour match on its tight core crop,
        robust wherever the movable menu sits) and taps a fixed offset down onto the AutoWalk row.
        Tapping a row that is already walking would raise the "Stop AutoWalk?" dialog, so after
        the first start we only tap again when the row shows the paused icon."""
        cfg = self.config
        frame = self.device.screenshot()
        matches = find(frame, self._star, threshold=cfg.menu_star_threshold, scales=(0.9, 1.0, 1.1), grayscale=False)
        if not matches:
            return False
        sx, sy = matches[0].center
        if self._autowalk_active:
            if self._aw_paused is None:
                return False
            # The paused icon sits on the AutoWalk row, a fixed offset below the star.
            region = (sx - 80, sy + cfg.autowalk_offset_y - 80, 280, 160)
            paused = find(frame, self._aw_paused, threshold=0.7, scales=(0.9, 1.0, 1.1), grayscale=False, region=region)
            if not paused:
                return False
        self.device.tap(sx + cfg.autowalk_offset_x, sy + cfg.autowalk_offset_y)
        return True

    def _wait_no_balls(self, on_event=None) -> None:
        """Out of Poké Balls: hold off catching for no_balls_pause seconds so we don't burn
        cycles on an empty bag. Keep AutoWalk moving during the wait so the avatar keeps
        travelling (passing Pokéstops / finding fresh spawns) instead of standing still, then
        resume normal catching — by then the bag has usually refilled."""
        cfg = self.config
        deadline = time.monotonic() + cfg.no_balls_pause
        # We may have fled from an encounter, so the walk state is unknown: force one fresh
        # AutoWalk start. Afterwards _try_autowalk only re-taps a stalled (paused) row.
        self._autowalk_active = False
        while time.monotonic() < deadline and not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                return
            self._handle_popups()
            if self._try_autowalk():
                self._autowalk_active = True
            self._interruptible_sleep(cfg.no_balls_walk_interval)

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
            self._interruptible_sleep(1.0)
            return False

        # Step 0.5: out of Poké Balls? If an encounter is up with an empty bag its ball badge
        # reads "x0". Checking here (before hunting the nearby bar) also rescues us when a useless
        # throw left us stuck in the encounter — the nearby bar never returns, but the badge does.
        # Flee via the running-man button and flag the loop to hold off catching.
        if self._noball_tpl is not None and self._is_out_of_balls(self.device.screenshot()):
            self.device.tap(*cfg.flee_xy)
            self._no_balls = True
            self.stats.last_event = "no_balls"
            self._interruptible_sleep(1.0)
            return False

        # Step 1: wait for the nearby bar (its '@' anchor). Polling here rides out the post-catch
        # transition/summary screen instead of wasting a whole cycle on it.
        slot = self._poll(self._slot_in, cfg.anchor_timeout)
        if slot is None:
            if cfg.require_anchor:
                self._interruptible_sleep(cfg.idle_poll)
                return False
            slot = cfg.nearby_slot

        # Step 2: engage it, then throw. The camera-icon poll only *times* the throw: the swipe
        # goes out the instant the encounter shows up. If the icon never shows we throw anyway
        # (a stray swipe on the map is harmless), but the cycle still counts as empty so the
        # AutoWalk dry-spell logic below keeps triggering on a dead map.
        self._double_tap(*slot)
        ball_xy = self._poll(self._ball_in, cfg.encounter_timeout)
        if self.stop_event.is_set():
            return False
        confirmed = ball_xy is not None

        # Step 3: throw, then wait until the nearby bar's '@' anchor reappears — that's the reliable
        # "encounter finished, we're back on the map" signal. (Waiting merely for the ball to vanish
        # fired too early: the ball leaves its rest spot the instant it's thrown, mid-animation.)
        self._throw(ball_xy or cfg.ball_fallback)
        # Give the throw/catch animation a moment so we don't detect the pre-throw map state.
        self._interruptible_sleep(cfg.settle_after_catch)
        self._poll(self._slot_in, cfg.catch_timeout)
        return confirmed

    def run(self, on_event=None) -> None:
        """Blocking loop. Honors stop_event / pause_event so a GUI can drive it in a thread."""
        cfg = self.config
        self.stop_event.clear()
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            threw = self.run_once()

            # Out of balls: notify the caller (Discord alert), then hold off catching for a
            # while — still AutoWalking so we keep moving — before resuming.
            if self._no_balls:
                self._no_balls = False
                self.stats.last_event = "no_balls"
                if on_event:
                    on_event(self.stats, False)
                self._wait_no_balls(on_event)
                self._idle_streak = 0
                continue

            self.stats.last_event = "throw" if threw else "idle"
            if on_event:
                on_event(self.stats, threw)

            # Dry spell handling: after several empty cycles, tap AutoWalk to go find new spawns.
            if threw:
                self._idle_streak = 0
            else:
                self._idle_streak += 1
                if cfg.idle_before_autowalk and self._idle_streak >= cfg.idle_before_autowalk:
                    # _try_autowalk itself refuses to tap an already-walking row, so calling it
                    # on every dry spell is safe — it re-taps only a stalled (paused) walk.
                    if self._try_autowalk():
                        self.stats.autowalks += 1
                        self.stats.last_event = "autowalk"
                        if on_event:
                            on_event(self.stats, False)
                        self._autowalk_active = True
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
