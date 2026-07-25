"""Pokémon catch routine.

Per cycle:
  0. If the bottom-right ball-selector is already showing we're inside an encounter (a
     break-out, or one that opened late) — throw at it right away. The encounter screen hides
     the sidebars, so anything that scans for them first can never get out of this state.
  1. Otherwise find a Pokémon to engage, in order:
       * the nearby-Pokémon sidebar's first slot — double-tap it; after a catch the list
         auto-advances, so the same slot position always holds the next target;
       * failing that, the PGSharp *feed* sidebar's first slot — tapping it teleports to that
         spawn, which fills the nearby bar for the next cycle instead of idling.
  2. Confirm we're actually in an encounter via the bottom-right ball-selector button (an
     opaque red Poké Ball shown for any loaded ball type — see _enc_ball_visible).
  3. Swipe up from the ball to throw it, then read the outcome: encounter closed (caught or
     fled), or the ball is back at the throw point (break-out) — throw again. After the last
     allowed throw the encounter is fled, so the flow always returns to the map.

The ball-selector is opaque, so it reads the same on any Pokémon's background — unlike the
old semi-transparent camera icon, whose contrast collapsed on bright scenes and silently
missed the encounter. When it isn't showing we're not in an encounter, so the cycle counts
as empty and the AutoWalk dry-spell logic keeps working.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, replace

import os
import numpy as np

from .device import Device
from .layout import (
    BASE_DENSITY, BASE_RESOLUTION, CALIBRATION_SWEEP, Layout, bracket_scales, scales_around,
)
from .resources import resource_path
from .vision import (
    best_matching_scale, find, find_enc_ball, find_fast, find_popup_close, load_template,
    slot_has_pokemon,
)


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
    force_slot: bool = False        # if True, always tap the fixed nearby_slot (skip '@' detection)
    double_tap_gap_ms: int = 90

    # Second Pokémon source: PGSharp's *feed* sidebar (the bar with the RSS icon at its bottom).
    # It queues freshly-spawned Pokémon; tapping its top entry teleports there, which fills the
    # Nearby bar for the next cycle. Consulted only when the Nearby bar is empty, so a busy
    # Nearby bar is still caught normally and no teleport happens. Off -> AutoWalk only.
    use_feed_bar: bool = True
    feed_rss_template: str = "templates/feed_rss.png"
    bar_handle_template: str = "templates/bar_handle.png"
    feed_threshold: float = 0.7
    feed_slot_dy: int = 100         # '≡' handle center -> first feed slot center
    handle_column_tol: int = 60     # max |x_handle - x_rss| to count as the same bar
    feed_teleport_wait: float = 4.0  # max wait for the teleported-to spawn to reach Nearby
    # Consecutive empty cycles required before the feed may teleport. The sprite test is
    # marginal against a busy translucent sidebar (event scenery, gyms) and loses the odd
    # frame on a bar that is actually full; teleporting on one such read jumps away from
    # catchable Pokémon. Several empty cycles in a row is evidence, one is noise.
    feed_after_idle: int = 2

    # Throw start point. Sits on the encounter ball's upper half: high enough that a blind
    # throw on the map (y >= 2467 is the map's pokeball menu button) can't press the menu.
    ball_fallback: tuple[int, int] = (610, 2380)
    # Encounter signal: the bottom-RIGHT ball-selector button. It's an opaque red Poké Ball shown
    # in every encounter *regardless of which ball is loaded to throw* (Great/Ultra included), so
    # spotting it detects the encounter for any ball type, unlike checking the throwable ball
    # (blue Great Balls / yellow Ultra Balls aren't red). Off the encounter (map, post-catch
    # "Gotcha") it is gone, which doubles as the leave/next-cycle signal. It is located by shape
    # in vision.find_enc_ball — there is deliberately no region to calibrate here.

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
    # A Pokémon that breaks out leaves the encounter open with a fresh ball at the throw point.
    # Throw again straight away (up to this many throws per encounter) instead of dropping back
    # to a Nearby scan that can't see anything behind the encounter screen. After the last one
    # the encounter is fled, so the flow always gets back to the map.
    max_throws_per_encounter: int = 3

    # Native Pokemon GO quick catch (no PGSharp key required): keep the Berry drawer
    # dragged open while throwing, then leave the encounter to skip the animation.
    quick_catch: bool = False
    quick_flick_ms: int = 100
    encounter_touch_delay_ms: int = 200
    post_throw_wait_ms: int = 350
    flee_taps: int = 2
    flee_gap_ms: int = 250
    berry_start: tuple[int, int] = (145, 2410)
    berry_end: tuple[int, int] = (390, 2410)

    # Human-ish jitter so the throw isn't pixel-identical every time.
    jitter_px: int = 8

    # Timing (seconds). These are *max* waits — the routine polls the screen and proceeds the
    # instant the expected state appears, so short cases stay fast and slow ones don't get missed.
    anchor_timeout: float = 3.0     # max wait for the nearby bar to (re)appear at cycle start
    encounter_timeout: float = 3.0  # max wait for the encounter to open after tapping a slot
    catch_timeout: float = 6.0      # max wait per throw for the encounter to end (ball gone)
    settle_after_catch: float = 1.2  # let the nearby list refresh before the next cycle
    poll_interval: float = 0.08     # pause between polls; cheap now that frames come from the stream
    idle_poll: float = 0.6          # pause between cycles when the nearby bar isn't visible

    # Popups that block the flow. Both are opaque dialogs, so template detection is reliable.
    popup_autowalk_template: str = "templates/popup_autowalk.png"   # "Stop/Pause AutoWalk?" dialog
    popup_speed_template: str = "templates/popup_speed.png"         # "I'M A PASSENGER" green button
    popup_weather_template: str = "templates/popup_weather.png"     # "I AM SAFE" green button (weather warning)
    claim_rewards_template: str = "templates/claim_rewards.png"      # "CLAIM REWARDS" level up button
    close_btn_template: str = "templates/close_btn.png"              # Close "X" button
    close_btn_blue_template: str = "templates/close_btn_blue.png"    # Close "X" button (blue)
    close_btn_white_template: str = "templates/close_btn_white.png"  # Close "X" button (white)
    # Post-catch safety net: if a throw's Flee lands too late the catch resolves into the Pokémon
    # detail/summary screen, whose green check (✓) button leaves it. Double-fleeing usually avoids
    # this screen entirely; this just recovers the odd one that slips through. Searched only in a
    # tight bottom-centre box so it can't be confused with anything on a live encounter.
    check_btn_template: str = "templates/check_btn.png"
    check_btn_region: tuple[int, int, int, int] = (450, 2360, 320, 300)
    # The "POKÉMON CAUGHT" XP summary that a late Flee resolves into shows first, with a big green
    # OK pill. Match it (its 'OK' text/width differ from the detail screen's POWER UP/EVOLVE pills)
    # in a screen-centre box and tap it. The box is centred so the left-aligned POWER UP/EVOLVE
    # buttons fall outside it — tapping those would spend Stardust/candy.
    caught_ok_template: str = "templates/caught_ok.png"
    caught_ok_region: tuple[int, int, int, int] = (250, 1600, 720, 560)
    # "WEEKLY CHALLENGE" (and similar) invite modal -> dismiss via its white "MAYBE LATER" text,
    # NOT the green "CHOOSE GROUP" button above it (which would join the challenge). Match the text
    # in a centre box; the green button sits above the box so it can't be hit.
    maybe_later_template: str = "templates/maybe_later.png"
    maybe_later_region: tuple[int, int, int, int] = (250, 1950, 720, 300)
    # PGSharp's "Go Plus is connected, teleport may trigger a softban. Continue?" dialog. Always
    # answer CANCEL — confirming risks the account. Its OK button sits ~105px to the right of
    # CANCEL's last letter, so the search box stops well short of it: a stray match must never
    # be able to land on OK and go through with the teleport.
    cancel_btn_template: str = "templates/cancel_btn.png"
    cancel_btn_region: tuple[int, int, int, int] = (620, 1480, 310, 220)
    popup_threshold: float = 0.7
    popup_debounce: float = 0.75  # ignore stale stream frames after one popup tap
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
    # The same row while the walk is running (route glyph, no '⊘'). Between the two templates the
    # row is locatable in either state, so the tap lands on the row *we actually found* instead of
    # on one fixed offset below the menu star — that offset is only right for the device it was
    # measured on, and being off by one row taps Feeds/Teleport instead. Whenever either icon is
    # seen the real star->row offset is re-learned, so even the fallback path self-corrects.
    autowalk_row_template: str = "templates/autowalk_row.png"
    autowalk_row_threshold: float = 0.72
    idle_before_autowalk: int = 3   # consecutive empty cycles before tapping AutoWalk (0 = off)
    autowalk_wait: float = 3.0      # wait after tapping for spawns to appear

    # Stop conditions.
    max_catches: int = 0           # 0 = unlimited

    # Actual device resolution. Left at BASE_RESOLUTION until scale_to() is called with the
    # connected phone's real size. The coordinate FIELDS above are stored already re-anchored
    # to this resolution; raw pixel literals inside the routine are in BASE_RESOLUTION units
    # and converted at use through s()/pt()/rect().
    screen: tuple[int, int] = BASE_RESOLUTION
    # Device density (dpi). Drives dp-correct scaling; None falls back to width-ratio.
    density: int | None = None

    @property
    def layout(self) -> Layout:
        return Layout(*self.screen, density=self.density)

    def s(self, v: float) -> int:
        """Scale a pure distance/size (swipe length, search radius, offset)."""
        return self.layout.scale(v)

    def pt(self, p: tuple[int, int], anchor: str) -> tuple[int, int]:
        """Map an absolute point authored in base coords; anchor e.g. 'BC', 'TL'."""
        return self.layout.point(p, anchor)

    def rect(self, r: tuple[int, int, int, int], anchor: str) -> tuple[int, int, int, int]:
        """Map an absolute box authored in base coords; anchor e.g. 'BC', 'TC'."""
        return self.layout.region(r, anchor)

    def scale_to(self, width: int, height: int, density: int | None = None) -> "CatchConfig":
        """Return a copy with every pixel coordinate re-anchored from BASE_RESOLUTION onto
        (width, height) at `density` dpi. Each field is tagged with the screen edge/corner it
        hugs so it lines up on any aspect ratio (see avc/layout.py). Timings, thresholds and
        template paths are untouched. No-op (returns self) at the base resolution+density."""
        L = Layout(width, height, density=density)
        if (width, height) == BASE_RESOLUTION and abs(L.s - 1.0) < 1e-9:
            return self
        return replace(
            self,
            screen=(width, height),
            density=density,
            # anchored positions/regions
            anchor_region=L.region(self.anchor_region, "TR"),   # nearby bar hugs right edge
            nearby_slot=L.point(self.nearby_slot, "TR"),
            ball_fallback=L.point(self.ball_fallback, "BC"),    # throw start, bottom-centre
            berry_start=L.point(self.berry_start, "BL"),        # Berry drawer, bottom-left
            berry_end=L.point(self.berry_end, "BL"),
            out_of_balls_region=L.region(self.out_of_balls_region, "BC"),
            check_btn_region=L.region(self.check_btn_region, "BC"),
            caught_ok_region=L.region(self.caught_ok_region, "MC"),
            maybe_later_region=L.region(self.maybe_later_region, "MC"),
            cancel_btn_region=L.region(self.cancel_btn_region, "MC"),  # centred system dialog
            flee_xy=L.point(self.flee_xy, "TL"),                # flee button, top-left
            pokestop_close_xy=L.point(self.pokestop_close_xy, "BC"),
            # pure distances/sizes/offsets
            slot_offset_y=L.scale(self.slot_offset_y),
            feed_slot_dy=L.scale(self.feed_slot_dy),
            handle_column_tol=L.scale(self.handle_column_tol),
            throw_dy=L.scale(self.throw_dy),
            jitter_px=max(1, L.scale(self.jitter_px)),
            autowalk_offset_x=L.scale(self.autowalk_offset_x),
            autowalk_offset_y=L.scale(self.autowalk_offset_y),
        )


@dataclass
class CatchStats:
    cycles: int = 0
    throws: int = 0        # balls actually thrown (a break-out costs more than one)
    encounters: int = 0    # Pokémon engaged — what max_catches counts
    autowalks: int = 0
    last_event: str = ""   # "throw" | "idle" | "autowalk"


class CatchRoutine:
    def __init__(self, device: Device, config: CatchConfig | None = None) -> None:
        self.device = device
        self.config = config or CatchConfig()
        # Templates are authored at BASE_RESOLUTION. Whether the game renders its UI bigger or
        # smaller on another device is unreliable (Pokémon GO/PGSharp don't re-layout cleanly
        # under a resolution override), so instead of baking one guessed size into each template
        # we keep them at base size and let find() sweep a bracket of scales (bracket_scales)
        # spanning the density estimate .. no-scaling. On the base device this stays a tight sweep.
        self._tpl_s = self.config.layout.s
        self._scales = bracket_scales(self._tpl_s)
        self._cal_scale: float | None = None   # measured render scale; None until calibrated
        self._anchor_cache: tuple[int, int] | None = None
        self._nearby_handle_cache: tuple[int, int] | None = None
        self._enc_ball_at: tuple[int, int] | None = None   # last seen selector, for the live view
        self._nearby_presence_streak = 0
        # Feed sidebar: cached (rss, handle, slot) positions, a presence streak matching the
        # Nearby one, and whether the bar has ever been located (so a user without the feed
        # bar on screen never pays for the slow fresh-capture retry).
        self._feed_cache: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None = None
        self._feed_presence_streak = 0
        self._feed_seen = False
        # Set when a CANCEL was just tapped, so the feed source can tell its own teleport was
        # refused (Go Plus warning) apart from a CANCEL on some unrelated dialog.
        self._cancelled_dialog = False
        self._teleport_blocked = False
        # Star -> AutoWalk-row offset measured on this device, replacing the config guess as
        # soon as the row is seen once.
        self._aw_offset: tuple[int, int] | None = None
        self._on_trace = None
        self._trace_last_key = ""
        self._trace_last_at = 0.0

        def load(path):
            return load_template(_resolve(path))

        def load_opt(path):
            return _load_optional(path)

        self._anchor = load(self.config.anchor_template)
        self._star = load(self.config.menu_star_template)
        # Feed-bar templates are optional: without them the feed source simply stays off.
        self._rss = load_opt(self.config.feed_rss_template)
        self._handle = load_opt(self.config.bar_handle_template)
        # Popup templates are optional — a missing one just disables that handler.
        self._popup_autowalk = load_opt(self.config.popup_autowalk_template)
        self._popup_speed = load_opt(self.config.popup_speed_template)
        self._popup_weather = load_opt(self.config.popup_weather_template)
        self._claim_rewards = load_opt(self.config.claim_rewards_template)
        self._close_btn = load_opt(self.config.close_btn_template)
        self._close_btn_blue = load_opt(self.config.close_btn_blue_template)
        self._close_btn_white = load_opt(self.config.close_btn_white_template)
        self._check_btn = load_opt(self.config.check_btn_template)
        self._caught_ok = load_opt(self.config.caught_ok_template)
        self._maybe_later = load_opt(self.config.maybe_later_template)
        self._cancel_btn = load_opt(self.config.cancel_btn_template)
        self._aw_paused = load_opt(self.config.autowalk_paused_template)
        self._aw_row = load_opt(self.config.autowalk_row_template)
        self._noball_tpl = load_opt(self.config.out_of_balls_template)
        self.stats = CatchStats()
        self._idle_streak = 0
        self._autowalk_active = False
        self._no_balls = False   # set by run_once when the "x0" badge is seen; consumed by run()
        self._popup_block_until = 0.0
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
        self.device.double_tap(jx, jy, self.config.double_tap_gap_ms)

    def _enc_ball_visible(self, frame) -> bool:
        """True when the bottom-right ball-selector is up, i.e. we are in an encounter.

        That button is an opaque red Poké Ball shown in every encounter whatever ball is
        loaded, so it detects the encounter for all ball types. It is found by its own
        red-dome-over-white-belly shape (see vision.find_enc_ball) rather than by sampling a
        hand-placed strip, so there is nothing to calibrate and being a few pixels out on a
        given device cannot blind it."""
        self._enc_ball_at = find_enc_ball(frame, scale=self.config.layout.s)
        return self._enc_ball_at is not None

    def _ball_in(self, frame) -> tuple[int, int] | None:
        # Only the red ball-selector at bottom-right is an encounter-safe signal.  The old
        # early signal sampled the large white throwable ball; bright map scenery and the
        # map's centre Poké Ball could satisfy it, causing a blind Quick Catch gesture that
        # opened the centre menu.  Waiting for the selector costs a fraction of a second but
        # guarantees we never throw/tap from the map.
        return self.config.ball_fallback if self._enc_ball_visible(frame) else None

    def _ball_ready(self, frame) -> bool:
        """True when a throwable ball is sitting at the throw start point.

        Only consulted while the encounter is known to be open, so the map's centre Poké Ball
        button can't be what we're seeing. During the flight/shake animation the ball has left
        that spot; it reappears there the moment the Pokémon breaks out, which is the cue to
        throw again immediately rather than waiting out ``catch_timeout``. The ball is a
        high-contrast red/white disc, so either the red dome or the white body identifies it
        against the encounter background.
        """
        bx, by = self.config.ball_fallback
        radius = max(6, self.config.s(34))
        patch = frame[max(0, by - radius):by + radius,
                      max(0, bx - radius):bx + radius]
        if patch.size == 0:
            return False
        p = patch.astype(int)
        b, g, r = p[..., 0], p[..., 1], p[..., 2]
        red = (r > 130) & (r - g > 45) & (r - b > 45)
        white = (r > 175) & (g > 175) & (b > 175)
        return float((red | white).mean()) >= 0.45

    def _is_out_of_balls(self, frame) -> bool:
        """True when the encounter's ball-count badge reads 'x0' (the red pill at the bottom
        centre) — i.e. we have no Poké Balls left. Colour match so it can't be confused with a
        neutral non-zero count."""
        if self._noball_tpl is None:
            return False
        matches = find(frame, self._noball_tpl, threshold=self.config.out_of_balls_threshold,
                       scales=self._scales, grayscale=False, region=self.config.out_of_balls_region)
        return bool(matches)

    def _slot_in(self, frame) -> tuple[int, int] | None:
        cfg = self.config
        region = cfg.anchor_region
        if self._anchor_cache is not None:
            ax, ay = self._anchor_cache
            radius = cfg.s(110)
            region = (ax - radius, ay - radius, radius * 2, radius * 2)
        matches = find(frame, self._anchor, threshold=cfg.anchor_threshold, scales=self._scales,
                       region=region, max_matches=1)
        if not matches and self._anchor_cache is not None:
            self._anchor_cache = None
            matches = find(frame, self._anchor, threshold=cfg.anchor_threshold, scales=self._scales,
                           region=cfg.anchor_region, max_matches=1)
        if not matches:
            return None
        ax, ay = matches[0].center
        self._anchor_cache = (ax, ay)
        # The anchor only confirms that the Nearby sidebar is present; the tap coordinate
        # comes from the bar's own geometry (see _bar_slot).
        return self._bar_slot(frame, (ax, ay))

    def _bar_slot(self, frame, anchor: tuple[int, int]) -> tuple[int, int]:
        """First (top) slot of the Nearby bar, measured from its '≡' drag handle.

        The '@' marks the bar's bottom and the handle its top; the list grows downward from
        the handle, so slot 1 sits a fixed distance below it however long the bar is. A fixed
        distance *above* '@' assumes a full list and drifts as the bar shortens, and the fixed
        `nearby_slot` only lines up on a device that was manually calibrated — both are kept
        as fallbacks, in that order, for when the handle isn't matchable.
        """
        cfg = self.config
        if self._handle is not None:
            ax, ay = anchor
            radius = cfg.s(120)
            hx, hy = self._nearby_handle_cache or (ax, 0)
            regions = [(hx - radius, hy - radius, radius * 2, radius * 2)] if self._nearby_handle_cache else []
            # Whole column above the '@', as a fallback: the feed bar shares this handle art,
            # so only a handle in the anchor's own column can belong to the Nearby bar.
            regions.append((ax - cfg.handle_column_tol * 2, 0, cfg.handle_column_tol * 4, ay))
            for region in regions:
                for h in find(frame, self._handle, threshold=cfg.feed_threshold,
                              scales=self._scales, region=region, max_matches=4):
                    hx, hy = h.center
                    if abs(hx - ax) <= cfg.handle_column_tol and hy < ay:
                        self._nearby_handle_cache = (hx, hy)
                        return (ax, hy + cfg.feed_slot_dy)
            self._nearby_handle_cache = None
            if cfg.slot_offset_y:
                return (ax, ay - cfg.slot_offset_y)
        return cfg.nearby_slot

    def _occupied_slot_in(self, frame) -> tuple[int, int] | None:
        """The first Nearby slot that actually holds a Pokémon sprite.

        Scans down the bar rather than inspecting slot 1 alone. The sidebar is translucent, so
        a busy map behind it (event scenery, a gym, confetti) can put more edges *around* the
        sprite than in it and make one slot fail the texture test while the bar is plainly
        full. Reading that as "Nearby is empty" is what sent the bot teleporting off through
        the feed bar with catchable Pokémon sitting right there. Any occupied slot is a fine
        target, so the topmost one that reads clean wins.
        """
        cfg = self.config
        slot = cfg.nearby_slot if cfg.force_slot else self._slot_in(frame)
        # The manually calibrated point is already expressed in native screen pixels.
        # Keep its inspection window tight as well: scaling 70x110 once more on a
        # high-resolution phone dilutes a small/dark sprite with adjacent sidebar rows.
        half_width = 70 if cfg.force_slot else cfg.s(70)
        height = 110 if cfg.force_slot else cfg.s(110)

        found = None
        if slot is not None:
            if slot_has_pokemon(frame, slot, half_width=half_width, height=height):
                found = slot
            elif not cfg.force_slot and self._anchor_cache is not None:
                # Walk down to just above the '@' that ends the bar. A step well under the
                # inspection window's height cannot skip past a sprite.
                step = max(12, cfg.s(40))
                bottom = self._anchor_cache[1] - cfg.s(80)
                y = slot[1] + step
                while y <= bottom:
                    if slot_has_pokemon(frame, (slot[0], y),
                                        half_width=half_width, height=height):
                        found = (slot[0], y)
                        break
                    y += step
        self._nearby_presence_streak = self._nearby_presence_streak + 1 if found else 0
        return found if found is not None and self._nearby_presence_streak >= 2 else None

    def _feed_slot_in(self, frame) -> tuple[int, int] | None:
        """First feed slot, when it actually holds a Pokémon sprite.

        The feed is a queue: tapping the top entry teleports to it and removes it, so the next
        spawn shifts up and slot 1 is always the right target. It is located as the '≡' drag
        handle sitting in the RSS icon's column, plus a fixed dy — both bars share the same
        handle art, so the column check is what tells the feed bar from the Nearby bar.
        """
        cfg = self.config
        if self._rss is None or self._handle is None:
            return None

        def occupied(slot: tuple[int, int]) -> tuple[int, int] | None:
            present = slot_has_pokemon(frame, slot, half_width=cfg.s(70), height=cfg.s(110))
            self._feed_presence_streak = self._feed_presence_streak + 1 if present else 0
            return slot if present and self._feed_presence_streak >= 2 else None

        if self._feed_cache is not None:
            (rx, ry), (hx, hy), slot = self._feed_cache
            radius = cfg.s(100)
            rss = find(frame, self._rss, threshold=cfg.feed_threshold, scales=self._scales,
                       region=(rx - radius, ry - radius, radius * 2, radius * 2), max_matches=1)
            handle = find(frame, self._handle, threshold=cfg.feed_threshold, scales=self._scales,
                          region=(hx - radius, hy - radius, radius * 2, radius * 2), max_matches=1)
            if rss and handle:
                return occupied(slot)
            self._feed_cache = None
            self._feed_presence_streak = 0
        # Both sidebars live in the same right-hand strip, so look there first and only pay
        # for a full-frame sweep if the feed bar has been moved out of it.
        rss = (find(frame, self._rss, threshold=cfg.feed_threshold, scales=self._scales,
                    region=cfg.anchor_region, max_matches=1)
               or find(frame, self._rss, threshold=cfg.feed_threshold, scales=self._scales,
                       max_matches=1))
        if not rss:
            return None
        rx, ry = rss[0].center
        column = (rx - cfg.handle_column_tol * 2, 0, cfg.handle_column_tol * 4, ry)
        for h in find(frame, self._handle, threshold=cfg.feed_threshold, scales=self._scales,
                      region=column, max_matches=4):
            hx, hy = h.center
            if abs(hx - rx) <= cfg.handle_column_tol:
                slot = (rx, hy + cfg.feed_slot_dy)
                self._feed_cache = ((rx, ry), (hx, hy), slot)
                self._feed_seen = True
                return occupied(slot)
        self._feed_presence_streak = 0
        return None

    def _tap_feed_spawn(self) -> bool:
        """Nearby is empty — teleport to the feed's top spawn if it has one. Returns True when
        a jump was made, which keeps the cycle productive instead of idling into AutoWalk."""
        cfg = self.config
        if (not cfg.use_feed_bar or self._teleport_blocked
                or self._rss is None or self._handle is None):
            return False
        frame = self.device.screenshot(next_frame=True)
        # Only jump when the Nearby bar itself is on screen — that is what proves we are on the
        # map looking at an empty bar. Without its '@' in view we are somewhere else entirely
        # (an encounter, a summary, a dialog, a transition), and tapping a remembered feed
        # position there fires a teleport in the middle of a catch.
        if self._slot_in(frame) is None:
            return False
        slot = self._feed_slot_in(frame)
        if slot is None and self._feed_seen:
            # H.264 smear between keyframes periodically drops the small RSS/handle templates
            # below threshold; a crisp one-shot capture is worth its ~1s only once the bar has
            # actually been seen on this device.
            slot = self._feed_slot_in(self.device.screenshot(fresh=True))
        if slot is None:
            return False
        self.device.tap(*slot)
        self._trace("feed_tap", f"Nearby trống; nhảy tới spawn trên thanh feed tại {slot}.", 0.0)
        # Teleporting far raises the speed warning; clear it, then stop waiting the instant the
        # spawn lands in the Nearby bar so the next cycle can engage it.
        self._interruptible_sleep(min(0.75, cfg.feed_teleport_wait))
        self._cancelled_dialog = False
        self._drain_popups()
        if self._cancelled_dialog:
            # The teleport was refused (Go Plus warning answered with CANCEL), so this jump
            # never happened and the next one wouldn't either. Retrying would just loop
            # tap -> warning -> CANCEL forever, so drop the feed source for the rest of the
            # run and let Nearby + AutoWalk carry the flow.
            self._teleport_blocked = True
            self._cancelled_dialog = False
            self._trace("feed_disabled",
                        "Teleport bị chặn (Go Plus đang kết nối) — tắt nguồn feed, "
                        "chỉ dùng Nearby + AutoWalk.", 0.0)
            return False
        self._poll(self._occupied_slot_in, cfg.feed_teleport_wait)
        return True

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

    def _handle_popups(self, frame=None) -> bool:
        """Dismiss blocking dialogs. Returns True if one was handled (and acted on)."""
        if time.monotonic() < self._popup_block_until:
            return False
        if frame is None:
            frame = self.device.screenshot()
        fast_cache = {}

        # PGSharp "Go Plus is connected, teleport may trigger a softban. Continue?" -> CANCEL.
        # Handled before anything else: it is a modal that eats every other tap, and the answer
        # is never OK. Matched on the CANCEL word itself (colour, tight box that excludes OK).
        if self._cancel_btn is not None:
            m = find(frame, self._cancel_btn, threshold=self.config.popup_threshold,
                     scales=self._scales, grayscale=False,
                     region=self.config.cancel_btn_region, max_matches=1)
            if m:
                self.device.tap(*m[0].center)
                self._cancelled_dialog = True
                self.stats.last_event = "popup"
                self._trace("teleport_warning",
                            "Cảnh báo Go Plus khi teleport; đã bấm CANCEL.", 0.0)
                return True

        # Weather warning "Weather conditions are potentially dangerous" -> tap the green
        # "I AM SAFE" button to dismiss it (it's a full modal that blocks the whole flow).
        if self._popup_weather is not None:
            m = find_fast(frame, self._popup_weather, threshold=self.config.popup_threshold,
                          scales=self._scales, cache=fast_cache)
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True

        # Speed warning "You're going too fast" -> tap the green "I'M A PASSENGER" button.
        # Popups render at a fixed size on a given device, so a single scale is enough.
        if self._popup_speed is not None:
            m = find_fast(frame, self._popup_speed, threshold=self.config.popup_threshold,
                          scales=self._scales, cache=fast_cache)
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True
        # "WEEKLY CHALLENGE"/invite modal -> tap its white "MAYBE LATER" text to dismiss (never the
        # green "CHOOSE GROUP" above it). Searched by text in a centre box, so the button is missed.
        if self._maybe_later is not None:
            m = find_fast(frame, self._maybe_later, threshold=self.config.popup_threshold,
                          scales=self._scales, grayscale=False, region=self.config.maybe_later_region)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # "Stop/Pause AutoWalk?" dialog -> tap CANCEL to dismiss it.
        if self._popup_autowalk is not None:
            m = find_fast(frame, self._popup_autowalk, threshold=self.config.popup_threshold,
                          scales=self._scales, cache=fast_cache)
            if m:
                # Aim at the CANCEL word itself when it can be read: the offset below is only
                # true for the device the dialog was measured on. Searched inside the dialog's
                # own box, so this can't pick up a CANCEL belonging to something else.
                target = None
                if self._cancel_btn is not None:
                    box = (m[0].x - self.config.s(60), m[0].y,
                           m[0].width + self.config.s(500), m[0].height + self.config.s(360))
                    hit = find(frame, self._cancel_btn, threshold=self.config.popup_threshold,
                               scales=self._scales, grayscale=False, region=box, max_matches=1)
                    if hit:
                        target = hit[0].center
                if target is None:
                    cx, cy = m[0].center
                    target = (cx + self.config.s(185), cy + self.config.s(168))
                self.device.tap(*target)
                self.stats.last_event = "popup"
                return True
        # Level-up "CLAIM REWARDS" screen -> tap claim, then tap screen to dismiss rewards until default screen
        if self._claim_rewards is not None:
            # The level-up screen renders at a different scale from the PGSharp overlay
            # used for calibration (MuMu: claim ~=0.67, menu star ~=0.55).
            m = find_fast(frame, self._claim_rewards, threshold=self.config.popup_threshold,
                          scales=CALIBRATION_SWEEP, cache=fast_cache)
            if m:
                rx, ry = m[0].center
                self.device.tap(rx, ry)
                self.stats.last_event = "popup"
                
                # Repeatedly tap center to dismiss items until map screen (nearby anchor) is back
                cx, cy = self.config.pt((610, 1000), "TC")
                deadline = time.monotonic() + 15.0
                while time.monotonic() < deadline and not self.stop_event.is_set():
                    self._interruptible_sleep(0.5)
                    f = self.device.screenshot()
                    if self._slot_in(f) is not None:
                        break
                    # If close button appears in the center bottom region, tap it immediately
                    for btn in (self._close_btn, self._close_btn_blue, self._close_btn_white):
                        if btn is not None:
                            m_close = find_fast(f, btn, threshold=0.7, scales=self._scales,
                                                region=self.config.rect((400, 2000, 420, 712), "BC"))
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
            r = self.config.s(160)
            region = (fx - r, fy - r, self.config.s(320), self.config.s(320))
            close = None
            for btn in (self._close_btn_white, self._close_btn, self._close_btn_blue):
                if btn is not None:
                    m = find_fast(frame, btn, threshold=0.7, scales=self._scales, region=region)
                    if m:
                        close = m[0].center
                        break
            if close is not None:
                self.device.tap(*close)
                self.stats.last_event = "popup"
                return True
        # "POKÉMON CAUGHT" XP summary (a slipped-through catch) -> tap its green OK pill. It shows
        # first, and its ball-selector bleeds through the dialog so the encounter check reads true;
        # handle it here before anything else touches the screen.
        if self._caught_ok is not None:
            m = find_fast(frame, self._caught_ok, threshold=0.72, scales=self._scales,
                          grayscale=False, region=self.config.caught_ok_region)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # Pokémon detail/summary screen (a slipped-through catch) -> tap its green check (✓) to
        # leave. Colour match in a tight bottom-centre box; the ✓ never appears on a live encounter.
        # Do not gate this on _ball_in(): the large white detail card can resemble the
        # throwable ball's bright centre.  The tight bottom-centre region plus the teal
        # button/template is already specific and excludes the encounter's controls.
        if self._check_btn is not None:
            m = find_fast(frame, self._check_btn, threshold=0.75, scales=self._scales,
                          grayscale=False, region=self.config.check_btn_region)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # Generic modal X. The safe search area is derived from this frame's dimensions,
        # and a wide scale fallback covers phones/emulators whose game UI ignores density.
        if self._ball_in(frame) is None:
            close = find_popup_close(
                frame,
                (self._close_btn, self._close_btn_blue, self._close_btn_white),
                threshold=self.config.popup_threshold,
                scales=self._scales,
                cache=fast_cache,
            )
            if close is not None:
                self.device.tap(*close.center)
                self.stats.last_event = "popup"
                return True
        return False

    def _drain_popups(self, frame=None) -> bool:
        """Tap once, then debounce stale stream frames so the same control cannot toggle."""
        if not self._handle_popups(frame):
            return False
        self._popup_block_until = time.monotonic() + self.config.popup_debounce
        self._interruptible_sleep(max(0.06, self.config.poll_interval))
        return True

    def _autowalk_row_in(self, frame, star: tuple[int, int] | None):
        """Find the AutoWalk row. Returns ((x, y), paused) or None.

        Both row states are tried: the '⊘' paused icon and the plain route glyph. Knowing which
        one matched is what makes the re-tap decision safe, and either one gives the row's real
        position on this device. The search is confined to the column of menu rows hanging off
        the star so a similar glyph on the map can't win."""
        cfg = self.config
        region = None
        if star is not None:
            sx, sy = star
            region = (sx - cfg.s(150), sy, cfg.s(300), cfg.s(700))
        if self._aw_paused is not None:
            m = find(frame, self._aw_paused, threshold=0.7, scales=self._scales,
                     grayscale=False, region=region, max_matches=1)
            if m:
                return m[0].center, True
        if self._aw_row is not None:
            m = find(frame, self._aw_row, threshold=cfg.autowalk_row_threshold,
                     scales=self._scales, region=region, max_matches=1)
            if m:
                return m[0].center, False
        return None

    def _try_autowalk(self) -> bool:
        """Make AutoWalk walk.

        The row is located by its own icon wherever the (movable) menu sits, which is what makes
        this work on any device. The yellow menu star is still matched, but only to bound the
        search and to back-stop it: if neither row icon is readable we fall back to star + offset,
        preferring an offset measured from a previous sighting over the config's default guess.
        Tapping a row that is already walking would raise the "Stop AutoWalk?" dialog, so after
        the first start we only tap again when the row shows the paused icon."""
        cfg = self.config
        frame = self.device.screenshot()
        m = find(frame, self._star, threshold=cfg.menu_star_threshold, scales=self._scales,
                 grayscale=False, max_matches=1)
        star = m[0].center if m else None

        row = self._autowalk_row_in(frame, star)
        if row is not None:
            target, paused = row
            if star is not None:
                self._aw_offset = (target[0] - star[0], target[1] - star[1])
        elif star is not None:
            # Row icon unreadable this frame (occluded, odd tint): aim by offset instead.
            dx, dy = self._aw_offset or (cfg.autowalk_offset_x, cfg.autowalk_offset_y)
            target, paused = (star[0] + dx, star[1] + dy), None
        else:
            return False

        if self._autowalk_active and paused is not True:
            # Already walking, and nothing says the row stalled — leave it alone.
            return False
        self.device.tap(*target)
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
            self._drain_popups()
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
            result = predicate(self.device.screenshot(next_frame=True))
            if result:
                return result
            if time.monotonic() >= deadline:
                return None

    def _throw_vector(self, ball_xy: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
        """Start and end point of one flick. The start is jittered in both axes so the throw
        isn't pixel-identical every time, but the end only follows it — jittering the two ends
        independently tilted the flick by up to 2*jitter_px sideways, which is exactly how a
        throw sails past the Pokémon. Only the throw *length* stays random."""
        bx, by = self._jitter(*ball_xy)
        j = max(0, self.config.jitter_px)
        ey = by + self.config.throw_dy + (random.randint(-j, j) if j else 0)
        return (bx, by), (bx, ey)

    def _throw(self, ball_xy: tuple[int, int]) -> None:
        (bx, by), (ex, ey) = self._throw_vector(ball_xy)
        self.device.control_swipe(bx, by, ex, ey, duration_ms=self.config.throw_duration_ms)

    def _quick_throw(self, ball_xy: tuple[int, int]) -> None:
        (bx, by), (ex, ey) = self._throw_vector(ball_xy)
        self.device.quick_catch_throw(
            self.config.berry_start, self.config.berry_end,
            (bx, by), (ex, ey), self.config.quick_flick_ms,
        )
        # MuMu can show the Flee button before the throw is committed. A small floor keeps
        # the first exit tap safe; configured extra wait is still honoured on slower phones.
        # MuMu commonly needs close to one second before Flee becomes actionable.  An
        # earlier tap is delivered but ignored (or cancels the throw), leaving the bot
        # visibly stuck in the encounter.
        commit_wait = max(1.0, self.config.post_throw_wait_ms / 1000.0)
        self._interruptible_sleep(commit_wait)
        # Start Flee on a clean control session.  MuMu may keep the just-finished
        # multi-touch pointer state attached to this scrcpy socket, causing an otherwise
        # valid tap at flee_xy to be silently ignored.  A standalone tap on a new socket
        # is accepted immediately.
        self.device.close_control()
        attempts = max(1, self.config.flee_taps)
        for attempt in range(attempts):
            if self.stop_event.is_set():
                return
            # Keep Flee independent from the multi-touch socket used by the throw.  On
            # Wi-Fi devices that socket can retain/lossily deliver pointer state, while a
            # standalone Android input tap reliably exits the encounter.
            self.device.adb_tap(*self.config.flee_xy)
            # Always send every configured Flee tap.  A held/moved ball makes _ball_in()
            # return None even though the encounter is still open; using that detector to
            # stop early caused the bot to mistake a failed first tap for a successful exit.
            # flee_xy is an inert top-left area after returning to the map, so retries are safe.
            if attempt + 1 < attempts:
                self._interruptible_sleep(
                    max(0.25, self.config.flee_gap_ms / 1000.0)
                )

    def _trace(self, key: str, message: str, repeat_after: float = 1.5) -> None:
        """Send a debounced detector trace to the GUI without affecting the catch loop."""
        callback = self._on_trace
        if callback is None:
            return
        now = time.monotonic()
        if key == self._trace_last_key and now - self._trace_last_at < repeat_after:
            return
        self._trace_last_key = key
        self._trace_last_at = now
        try:
            callback(f"[Nhận diện] {message}")
        except Exception:  # noqa: BLE001 - diagnostics must never stop automation
            pass

    def _throw_outcome(self, timeout: float) -> str:
        """Watch an encounter after a throw: 'closed' (caught or fled — the ball-selector is
        gone), 'breakout' (a fresh ball is back at the throw point) or 'timeout'.

        The ball only counts as back once it has been seen *gone* — the frames right after the
        flick still show it at the throw point, and reading those as a break-out would fire a
        second throw into every catch animation."""
        deadline = time.monotonic() + timeout
        ball_left = False
        while not self.stop_event.is_set():
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            if not self._enc_ball_visible(frame):
                return "closed"
            if not self._ball_ready(frame):
                ball_left = True
            elif ball_left:
                return "breakout"
            if time.monotonic() >= deadline:
                return "timeout"
        return "timeout"

    def _run_encounter(self, ball_xy: tuple[int, int]) -> bool:
        """Throw at the open encounter until it ends, then leave it either way.

        A Pokémon that breaks out keeps the encounter open, which hides the Nearby bar — the
        old flow returned to scanning for that bar and could never see it again, so the bot sat
        in the encounter doing nothing. Here every throw's outcome is read: a break-out throws
        again straight away, and once the throws are spent the encounter is fled so the next
        cycle is back on the map. Returns True if at least one ball was thrown."""
        cfg = self.config
        threw = False
        closed = False
        for attempt in range(max(1, cfg.max_throws_per_encounter)):
            if self.stop_event.is_set():
                return threw
            if attempt == 0:
                self._interruptible_sleep(cfg.encounter_touch_delay_ms / 1000.0)
            # Reconfirm on a new frame immediately before touching the screen. This closes the
            # stale-frame race where the encounter vanished during the delay and the queued
            # throw landed on the map's centre Poké Ball.
            if not self._enc_ball_visible(self.device.screenshot(next_frame=True)):
                closed = True
                if attempt == 0:
                    self._trace("throw_safety_cancel",
                                "Hủy ném: frame mới không còn thấy bóng đỏ trong đúng khung căn tay.", 0.0)
                break
            self._trace(
                "throw_start",
                f"Ném lần {attempt + 1}/{cfg.max_throws_per_encounter} tại {ball_xy} "
                f"({'nhanh' if cfg.quick_catch else 'thường'}).",
                0.0,
            )
            self.stats.throws += 1
            threw = True
            if cfg.quick_catch:
                self._quick_throw(ball_xy)
            else:
                self._throw(ball_xy)
            outcome = self._throw_outcome(cfg.catch_timeout)
            if outcome == "closed":
                closed = True
                self._trace("throw_committed", "Encounter đã đóng; cú ném được ghi nhận.", 0.0)
                break
            if outcome == "breakout":
                self._trace("throw_breakout", "Pokémon thoát ra, bóng đã về chỗ ném; ném lại ngay.", 0.0)
            else:
                self._trace(
                    "throw_commit_timeout",
                    f"Hết {cfg.catch_timeout:.1f}s mà encounter chưa đóng; thử lại.",
                    0.0,
                )
        if not closed and not self.stop_event.is_set():
            # Still in the encounter after the last throw. Leaving is what keeps the flow
            # moving — flee_xy is inert once we're back on the map, so an extra tap is safe.
            self._trace("encounter_give_up", "Hết lượt ném; thoát encounter để quay lại bản đồ.", 0.0)
            self.device.adb_tap(*cfg.flee_xy)
            self._poll(lambda f: True if not self._enc_ball_visible(f) else None, 2.0)
        if threw:
            self.stats.encounters += 1
        if cfg.settle_after_catch > 0:
            self._poll(self._slot_in, cfg.settle_after_catch)
        return threw

    def _ensure_calibrated(self) -> None:
        """Measure how big the UI actually renders on this device (once), from the always-on
        PGSharp menu star, and centre the match-scale sweep on it. This sidesteps guessing the
        scale from resolution/density — which is unreliable because the game doesn't re-layout
        cleanly. Until it locks, the wide bracket set in __init__ stays in effect, so detection
        keeps working; a hidden/covered star just leaves it to retry next cycle."""
        if self._cal_scale is not None or self._star is None:
            return
        s, score = best_matching_scale(self.device.screenshot(), self._star,
                                       CALIBRATION_SWEEP, grayscale=False)
        if s is not None and score >= 0.82:
            self._cal_scale = s
            self._scales = scales_around(s)

    def run_once(self) -> bool:
        """One catch cycle. Returns True if a ball was thrown."""
        cfg = self.config
        self.stats.cycles += 1
        self._ensure_calibrated()
        frame = self.device.screenshot()

        # Step 0: clear any blocking popup (speed warning, AutoWalk dialog) before doing anything.
        if self._drain_popups(frame):
            return False

        # Step 0.5: out of Poké Balls? If an encounter is up with an empty bag its ball badge
        # reads "x0". Checking here (before hunting the nearby bar) also rescues us when a useless
        # throw left us stuck in the encounter — the nearby bar never returns, but the badge does.
        # Flee via the running-man button and flag the loop to hold off catching.
        if self._noball_tpl is not None and self._is_out_of_balls(frame):
            self.device.tap(*cfg.flee_xy)
            self._no_balls = True
            self.stats.last_event = "no_balls"
            self._interruptible_sleep(1.0)
            return False

        # Step 0.75: already inside an encounter? A break-out from the previous throw, an
        # encounter that opened a beat after the last cycle gave up, or a stray tap all land
        # here. The encounter screen hides the Nearby bar, so scanning for it is hopeless —
        # this check is what stops the bot from sitting in an encounter it can't see out of.
        ball_xy = self._ball_in(frame)
        if ball_xy is not None:
            self._trace("encounter_open", "Đang ở trong encounter; ném luôn.", 0.0)
            return self._run_encounter(ball_xy)

        # Step 1: wait for the nearby bar (its '@' anchor). Polling here rides out the post-catch
        # transition/summary screen instead of wasting a whole cycle on it.
        slot = self._occupied_slot_in(frame)
        if slot is None:
            slot = self._poll(self._occupied_slot_in, cfg.anchor_timeout)
        if slot is None:
            # Nothing on Nearby — does the PGSharp feed list a fresh spawn? Teleporting to it
            # fills the Nearby bar for the next cycle, which beats idling until the dry-spell
            # timer fires. Only after several empty cycles in a row though: one empty read is
            # usually the sprite test dropping a frame, not an empty bar, and acting on it
            # teleports away from Pokémon that are sitting right there. The jump counts as
            # progress, so the AutoWalk streak resets.
            if self._idle_streak >= cfg.feed_after_idle and self._tap_feed_spawn():
                self._idle_streak = 0
                return False
            self._trace("nearby_empty", "Không thấy Pokémon trên thanh Nearby lẫn thanh feed.")
            self._interruptible_sleep(cfg.idle_poll)
            return False

        # Step 2: engage it. The ball-selector poll returns the instant the encounter opens; if
        # it never shows within encounter_timeout the slot was empty or the Pokémon fled.
        self._double_tap(*slot)
        tapped_at = time.monotonic()
        self._trace(
            "nearby_tap",
            f"Đã xác nhận Pokémon tại {slot} và bấm mở encounter.",
            0.0,
        )
        # Start the gesture on the first stream frame where the throwable ball is ready.
        # The early centre-ball signal appears before the selector animation. A short
        # fallback cap prevents a lagging stream from stalling the catch.
        ball_xy = self._poll(self._ball_in, min(cfg.encounter_timeout, 1.5))
        if ball_xy is None:
            # Do not rely on the user's device behaving like ours. If a fresh frame still
            # shows the same occupied Nearby slot, the first double-tap did not open it.
            # Retry once with a plain tap; if the sidebar has disappeared, never tap blindly.
            retry_frame = self.device.screenshot(next_frame=True)
            # The encounter may simply have been slow: check this newer frame before touching
            # anything. On devices that keep the sidebars visible during an encounter the
            # "slot still occupied" test below is true even once it opened, so without this
            # the retry fires a stray tap onto the encounter screen.
            ball_xy = self._ball_in(retry_frame)
            if ball_xy is not None:
                self._trace("encounter_late_open",
                            "Encounter mở trễ; bỏ qua tap thử lại và ném luôn.", 0.0)
                return self._run_encounter(ball_xy)
            retry_slot = self._occupied_slot_in(retry_frame)
            same_slot = (
                retry_slot is not None
                and abs(retry_slot[0] - slot[0]) <= cfg.s(80)
                and abs(retry_slot[1] - slot[1]) <= cfg.s(80)
            )
            if same_slot:
                self.device.tap(*retry_slot)
                self._trace(
                    "nearby_tap_retry",
                    f"Nearby vẫn còn sau double-click; thử lại một tap tại {retry_slot}.",
                    0.0,
                )
            # Slow MuMu streams can lag the ball in; spend the rest of encounter_timeout on it.
            ball_xy = self._poll(self._ball_in, max(0.0, cfg.encounter_timeout - 1.5))
        if self.stop_event.is_set():
            return False
        if ball_xy is None:
            # No encounter opened (empty nearby slot / Pokémon fled). Never throw blind here:
            # a fallback swipe on the map just drags the camera and burns the cycle. If it was
            # merely slow to open, step 0.75 of the next cycle picks it up within idle_poll.
            self._trace(
                "encounter_initial_miss",
                f"Chưa thấy bóng sau {time.monotonic() - tapped_at:.2f}s; quét lại ở vòng sau.",
                0.0,
            )
            self._interruptible_sleep(cfg.idle_poll)
            return False
        return self._run_encounter(ball_xy)

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

            # Count Pokémon, not balls: a break-out spends several throws on one of them.
            if cfg.max_catches and self.stats.encounters >= cfg.max_catches:
                break

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    # -- live-view annotation --------------------------------------------------------
    def annotate(self, frame, canvas=None):
        """The catch routine's own detections drawn for the GUI's live view: which Nearby slot
        it would engage, the feed fallback, the throw vector, and the boxes the encounter /
        out-of-balls detectors read.

        Detection runs against `frame`; the drawing goes onto `canvas`, which defaults to a
        copy of the frame. Passing a blank canvas yields a transparent-style overlay layer the
        caller can composite onto live frames, so a mirror does not have to run this (fairly
        expensive) pass for every frame it displays."""
        import cv2

        cfg = self.config
        img = frame.copy() if canvas is None else canvas

        def box(rect, colour, label):
            x, y, w, h = rect
            cv2.rectangle(img, (x, y), (x + w, y + h), colour, 3)
            cv2.putText(img, label, (x, max(24, y - 10)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.9, colour, 2)

        # Encounter + out-of-balls detector windows.
        in_enc = self._enc_ball_visible(frame)
        if self._enc_ball_at is not None:
            cv2.circle(img, self._enc_ball_at, cfg.s(70), (0, 0, 255), 4)
            cv2.putText(img, "ENC", (self._enc_ball_at[0] - cfg.s(40),
                                     self._enc_ball_at[1] - cfg.s(80)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        box(cfg.out_of_balls_region, (0, 140, 255), "x0")

        # Throw: start point and where the flick ends.
        bx, by = cfg.ball_fallback
        ready = self._ball_ready(frame)
        cv2.circle(img, (bx, by), max(10, cfg.s(34)), (0, 255, 0) if ready else (0, 160, 0), 4)
        cv2.arrowedLine(img, (bx, by), (bx, by + cfg.throw_dy), (0, 255, 0), 4, tipLength=0.08)
        cv2.putText(img, "THROW", (bx + cfg.s(45), by), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (0, 255, 0), 2)

        # Nearby bar: the '@' that proves it is on screen, slot 1, and the slot actually chosen.
        slot1 = cfg.nearby_slot if cfg.force_slot else self._slot_in(frame)
        if self._anchor_cache is not None:
            cv2.circle(img, self._anchor_cache, cfg.s(40), (255, 255, 0), 4)
        if slot1 is not None:
            cv2.drawMarker(img, slot1, (255, 255, 0), cv2.MARKER_CROSS, cfg.s(70), 4)
            streak = self._nearby_presence_streak      # keep the routine's own streak intact
            target = self._occupied_slot_in(frame)
            self._nearby_presence_streak = streak
            half_w, half_h = cfg.s(70), cfg.s(55)
            if target is not None:
                cv2.rectangle(img, (target[0] - half_w, target[1] - half_h),
                              (target[0] + half_w, target[1] + half_h), (0, 255, 255), 5)
                cv2.putText(img, "DBL TAP", (target[0] - half_w, target[1] - half_h - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            else:
                cv2.putText(img, "NEARBY EMPTY", (slot1[0] - half_w, slot1[1] - half_h - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (160, 160, 160), 2)

        # Feed bar: only a fallback, so draw it dimmer than the Nearby target.
        if cfg.use_feed_bar and self._rss is not None:
            streak = self._feed_presence_streak
            feed = self._feed_slot_in(frame)
            self._feed_presence_streak = streak
            if feed is not None:
                cv2.circle(img, feed, cfg.s(48), (255, 120, 0), 4)
                cv2.putText(img, "FEED", (feed[0] - cfg.s(40), feed[1] - cfg.s(58)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 120, 0), 2)

        # Flee button, and a banner for the states that drive the flow.
        cv2.drawMarker(img, cfg.flee_xy, (255, 0, 255), cv2.MARKER_TILTED_CROSS, cfg.s(60), 4)
        if in_enc:
            cv2.putText(img, "IN ENCOUNTER", (cfg.s(60), cfg.s(230)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
        if self._teleport_blocked:
            cv2.putText(img, "FEED OFF (Go Plus)", (cfg.s(60), cfg.s(300)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 140, 255), 3)
        return img
