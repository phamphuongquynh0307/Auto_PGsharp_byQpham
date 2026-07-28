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
from . import uidump
from .resources import resource_path
from .vision import (
    best_matching_scale, camera_icon_visible, find, find_enc_ball, find_fast, find_popup_close,
    find_dialog_buttons, load_template, slot_has_pokemon,
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
    # With force_slot the calibrated point *is* slot 1 and there is no '@' to bound a walk down
    # the bar, so the remaining slots are stepped off at a fixed pitch instead. Inspecting slot 1
    # alone is what made a bar whose top slot happened to be empty read as an empty bar, with
    # catchable Pokémon sitting in the slots below it. Pitch measured on a 1220x2712 MuMu.
    slot_pitch: int = 106
    force_slot_count: int = 5       # slots below slot 1 to inspect; keep clear of the '@' at the end
    # The '@' floor is a safety bound, not a detection, and it only moves when the bar is dragged
    # or the list length changes. Re-matching it on every polled frame costs ~7-11ms — most of the
    # scan — for an answer that is almost always the previous one, so it is cached this long.
    force_bottom_ttl: float = 2.0
    double_tap_gap_ms: int = 90
    # A single tap lands on the slot first, then the double-tap follows after this pause. The
    # lone tap wakes/selects the row so the double-tap that follows is read as a real
    # double-tap rather than the first two touches of a cold slot. Set to 0 to go straight to
    # the double-tap.
    pre_tap_delay: float = 0.8
    # Corroboration for a Nearby sighting: a second hit within this many seconds confirms the
    # first. Counting over a window rather than over *consecutive* frames is what stops one
    # smeared stream frame from wiping the evidence and leaving the bot idle in front of a full
    # bar. 0 accepts a single frame (fastest, most false positives).
    nearby_presence_window: float = 1.5
    # Last word before declaring the bar empty: re-read it on a one-shot capture, which has no
    # H.264 smear to hide a small sprite. Costs ~1s, so it is spent at most this often. Negative
    # disables it.
    nearby_fresh_cooldown: float = 5.0
    # PGSharp draws its own overlay as real Android views, so its view tree states outright how
    # many Pokémon are on the Nearby bar and where each one sits — no threshold, no calibration.
    # A dump costs ~1.6s though, so it is asked only where the flow already pays for a decisive
    # answer (just before declaring the bar empty) and never inside a poll. Turn it off for a
    # build whose overlay is not readable; every path that uses it falls back to pixels.
    use_ui_dump: bool = True
    ui_dump_cooldown: float = 4.0

    # Pace the catches. Each Nearby tap moves the player to that Pokémon, so catching as fast as
    # the screen allows implies a travel speed the game will not accept — once a broken stream
    # was fixed a cycle went from ~52s to ~2.7s and the cooldowns started immediately. Holding a
    # floor between encounters keeps the implied speed plausible, and it is far cheaper than
    # sitting out the cooldown it prevents. 0 disables the floor.
    min_catch_interval: float = 3.0

    # Tapping a distant Nearby entry makes PGSharp jump the player there, and a long jump earns a
    # Niantic cooldown: catching through it is what gets an account soft-banned, and the implied
    # speed also stops fresh spawns appearing. The distance itself is not readable — the Nearby
    # nodes are bare ImageViews — but PGSharp publishes the *consequence*, counting the cooldown
    # down as text in its own overlay. Reading that verdict beats estimating distance, because it
    # is computed from Niantic's real cooldown table rather than guessed. Needs use_ui_dump.
    respect_cooldown: bool = True
    cooldown_check_interval: float = 25.0   # how often to spend a dump purely on the cooldown
    cooldown_margin: float = 5.0            # extra seconds waited past PGSharp's countdown

    # Diagnostics: append a per-cycle phase breakdown to timing_log so a slow cycle can be
    # attributed to a step instead of guessed at. Off by default — it writes a line per cycle.
    trace_timing: bool = False
    timing_log: str = "timing.log"

    # Second Pokémon source: PGSharp's *feed* sidebar (the bar with the RSS icon at its bottom).
    # It queues freshly-spawned Pokémon; tapping its top entry teleports there, which fills the
    # Nearby bar for the next cycle. Consulted only when the Nearby bar is empty, so a busy
    # Nearby bar is still caught normally and no teleport happens. Off -> AutoWalk only.
    # Regular auto-catch only works through Nearby. The PGSharp feed is reserved for
    # Shundo hunting and must never make Catch mode teleport.
    use_feed_bar: bool = False
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
    #
    # Second opinion: the camera/AR button at top centre, present in every encounter and absent
    # on the map. The ball-selector's failure mode is a phantom just after a Flee — the bot then
    # throws at the map — while this one's is missing a real encounter on a washed-out scene.
    # Two different failure modes, so requiring both to agree cuts the phantom without inheriting
    # the miss. enc_signal picks the rule: "both" (AND, safest), "any" (OR, most eager),
    # "ball" or "camera" to use one alone.
    enc_signal: str = "both"
    enc_camera_region: tuple[int, int, int, int] = (545, 130, 130, 105)
    # Sampled on a live 1220x2712 MuMu — encounter 0.199/0.200/0.201, map 0.000 .. 0.073 (the top
    # of that range is PGSharp's white-on-pink timer pill drifting through the box). The window
    # sits in the gap, well clear of both. A first cut at 0.06 was under the map's own maximum.
    enc_camera_min_fill: float = 0.12   # below this the glyph isn't there
    enc_camera_max_fill: float = 0.45   # above it the box is a bright backdrop, not an outline
    # The selector never moves within a run, so once an encounter has been confirmed by *both*
    # signals its position is remembered and later detections must land near it. A red blob
    # elsewhere in the corner is then no longer mistaken for the button: the phantom that sent
    # the bot throwing at the map was measured 120px right of the real one.
    enc_ball_home_tol: int = 80

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
    throw_duration_ms: int = 130
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
    anchor_timeout: float = 1.5     # max wait for the nearby bar to (re)appear at cycle start
    encounter_timeout: float = 3.0  # max wait for the encounter to open after tapping a slot
    catch_timeout: float = 6.0      # max wait per throw for the encounter to end (ball gone)
    settle_after_catch: float = 1.2  # let the nearby list refresh before the next cycle
    poll_interval: float = 0.08     # pause between polls; cheap now that frames come from the stream
    idle_poll: float = 0.3          # pause between cycles when the nearby bar isn't visible

    # Popups that block the flow. Both are opaque dialogs, so template detection is reliable.
    # System AlertDialog ("Tap to Walk/Teleport - Stop AutoWalk?") raised whenever a tap lands
    # on the map. It blocks everything until answered, and the bundled templates do not match it
    # on this PGSharp build — swept across every scale they scored under 0.55 — so it is found by
    # the shape of its own buttons instead. The answer is always the left one, CANCEL.
    dialog_region: tuple[int, int, int, int] = (150, 1150, 950, 500)

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
    autowalk_paused_threshold: float = 0.7   # match score required for the '⊘' icon
    idle_before_autowalk: int = 3   # consecutive empty cycles before tapping AutoWalk (0 = off)
    autowalk_wait: float = 3.0      # wait after tapping for spawns to appear
    # A tap on the paused row is verified by re-reading the row: '⊘' gone means it landed. The
    # icon is 56px on a movable menu located in a compressed stream frame, so a miss is a real
    # possibility and an unverified tap looks exactly like a successful one.
    autowalk_verify_delay: float = 0.8   # pause before re-reading the row
    autowalk_tap_retries: int = 1        # extra taps allowed while '⊘' is still showing

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
            enc_camera_region=L.region(self.enc_camera_region, "TC"),   # camera button, top-centre
            check_btn_region=L.region(self.check_btn_region, "BC"),
            caught_ok_region=L.region(self.caught_ok_region, "MC"),
            maybe_later_region=L.region(self.maybe_later_region, "MC"),
            cancel_btn_region=L.region(self.cancel_btn_region, "MC"),  # centred system dialog
            flee_xy=L.point(self.flee_xy, "TL"),                # flee button, top-left
            pokestop_close_xy=L.point(self.pokestop_close_xy, "BC"),
            # pure distances/sizes/offsets
            slot_offset_y=L.scale(self.slot_offset_y),
            slot_pitch=L.scale(self.slot_pitch),
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
        self._force_bottom_cache: tuple[int, int] | None = None   # '@' ending a calibrated bar
        self._force_bottom_value: int | None = None               # its floor, cached for a TTL
        self._force_bottom_at = 0.0
        self._enc_ball_at: tuple[int, int] | None = None   # last seen selector, for the live view
        self._enc_camera_seen = False                      # last camera-button read, for the live view
        self._enc_ball_home: tuple[int, int] | None = None  # where the selector really lives here
        # When the Nearby bar was last seen holding a sprite (corroboration window), and when
        # the slow one-shot re-read was last spent (rate limit).
        self._nearby_last_seen_at: float | None = None
        self._nearby_fresh_at = 0.0
        self._ui_dump_at = 0.0
        self._phases: list[tuple[str, float]] = []
        self._phase_t0 = 0.0
        self._cooldown_until = 0.0      # monotonic deadline; 0 means clear
        self._cooldown_checked_at = 0.0
        self._last_engage_at = 0.0      # when the last encounter was engaged, for pacing
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
        at = find_enc_ball(frame, scale=self.config.layout.s)
        home = self._enc_ball_home
        if at is not None and home is not None:
            # Known where the button lives on this device, so a red blob somewhere else in the
            # corner cannot be it. The home is only ever learned from a frame both signals agreed
            # on, and it is refreshed on every such frame, so a UI that genuinely moves re-learns.
            tol = self.config.enc_ball_home_tol
            if abs(at[0] - home[0]) > tol or abs(at[1] - home[1]) > tol:
                self._trace("enc_ball_offsite",
                            f"Bỏ qua bóng đỏ tại {at}: lệch khỏi vị trí đã học {home}.")
                at = None
        self._enc_ball_at = at
        return at is not None

    def _enc_camera_visible(self, frame) -> bool:
        """True when the encounter's top-centre camera/AR button is showing."""
        cfg = self.config
        return camera_icon_visible(frame, cfg.enc_camera_region,
                                   min_fill=cfg.enc_camera_min_fill,
                                   max_fill=cfg.enc_camera_max_fill)

    def _in_encounter(self, frame, *, strict: bool = False) -> bool:
        """Are we in an encounter? Two signals, and which rule applies depends on when we ask.

        The camera button only renders about a second *into* the encounter, so for that first
        second a real encounter shows the ball-selector alone. Demanding both signals at that
        moment reads a live encounter as closed — it cancels the throw and walks away from the
        Pokémon. So the strict rule is reserved for the moments where the opposite error is the
        one that bites:

          * strict (enc_signal, "both" by default) — asked with no context, at the start of a
            cycle or after a throw, where the danger is a phantom ball-selector left over from an
            encounter we already fled. By then a real encounter is well past the camera's lag, so
            requiring the camera costs nothing and kills the phantom.
          * eager (ball or camera) — asked while an encounter is opening or known to be open, so
            a signal that has not rendered yet cannot be read as "gone".

        Both signals are always evaluated so the live view shows what each one saw.
        """
        # Camera first, always: it reads a 130x105 box for ~0.08ms, while the ball sweep runs
        # connected components over 391x543 for ~8ms — a hundredfold difference. Asking the cheap
        # question first lets most frames skip the expensive one entirely, and neither rule's
        # result changes, only the order they are evaluated in.
        camera = self._enc_camera_visible(frame)
        self._enc_camera_seen = camera
        mode = self.config.enc_signal

        if not strict:
            # Eager is an OR, so the cheap signal alone already settles it when it fires.
            return True if camera else self._enc_ball_visible(frame)
        if mode == "camera":
            return camera
        if mode == "ball":
            return self._enc_ball_visible(frame)
        if mode == "any":
            return True if camera else self._enc_ball_visible(frame)
        # "both" is an AND, so no camera means no encounter and the sweep can be skipped. That is
        # the common case while polling on the map, which is where this is asked most often.
        if not camera:
            self._enc_ball_at = None
            return False
        ball = self._enc_ball_visible(frame)
        if ball and self._enc_ball_at is not None:
            # Two independent signals agreeing is the only evidence trusted to place the button.
            self._enc_ball_home = self._enc_ball_at
        return ball

    def _ball_in(self, frame, *, strict: bool = False) -> tuple[int, int] | None:
        # Only the red ball-selector at bottom-right is an encounter-safe signal.  The old
        # early signal sampled the large white throwable ball; bright map scenery and the
        # map's centre Poké Ball could satisfy it, causing a blind Quick Catch gesture that
        # opened the centre menu.  Waiting for the selector costs a fraction of a second but
        # guarantees we never throw/tap from the map.
        return self.config.ball_fallback if self._in_encounter(frame, strict=strict) else None

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

    def _force_bar_bottom(self, frame, slot: tuple[int, int]) -> int:
        """Lowest y worth inspecting on a manually calibrated bar.

        The '@' that ends the bar reads as a Pokémon to slot_has_pokemon — a bright glyph on a
        dark disc is exactly the compact texture the test looks for — so a scan that runs into it
        double-taps the tracker instead of a Pokémon. Finding it puts a floor under the scan
        wherever the bar has been dragged to, which is what makes moving the bar safe: without it
        the only thing standing between the scan and the tracker is force_slot_count happening to
        run out in time.

        Falls back to the plain count when the '@' can't be matched, so a bar it cannot see still
        behaves as before rather than refusing to scan at all.
        """
        cfg = self.config
        floor = slot[1] + max(0, cfg.force_slot_count) * cfg.slot_pitch
        if self._anchor is None:
            return floor
        # Answer from the last match while it is still fresh. This is the whole cost of scanning
        # an empty bar, and the bar's end does not move between frames.
        now = time.monotonic()
        if (self._force_bottom_value is not None
                and now - self._force_bottom_at <= cfg.force_bottom_ttl):
            return self._force_bottom_value
        radius = cfg.s(110)
        regions = []
        if self._force_bottom_cache is not None:
            ax, ay = self._force_bottom_cache
            regions.append((ax - radius, ay - radius, radius * 2, radius * 2))
        # The bar is a column at the calibrated x; search it from just below slot 1 downward.
        regions.append((slot[0] - radius, slot[1] + cfg.slot_pitch // 2,
                        radius * 2, floor + cfg.slot_pitch * 2))
        for region in regions:
            m = find(frame, self._anchor, threshold=cfg.anchor_threshold, scales=self._scales,
                     region=region, max_matches=1)
            if m:
                ax, ay = m[0].center
                self._force_bottom_cache = (ax, ay)
                return self._remember_bottom(ay - cfg.s(80))
        # Cache the miss too, so a bar whose '@' cannot be matched does not pay for a full
        # search on every single polled frame — that is the slowest case there is.
        self._force_bottom_cache = None
        return self._remember_bottom(floor)

    def _remember_bottom(self, value: int) -> int:
        self._force_bottom_value = value
        self._force_bottom_at = time.monotonic()
        return value

    def _scan_slots(self, frame) -> tuple[int, int] | None:
        """The first Nearby slot that holds a Pokémon sprite in this one frame.

        Scans down the bar rather than inspecting slot 1 alone. The sidebar is translucent, so
        a busy map behind it (event scenery, a gym, confetti) can put more edges *around* the
        sprite than in it and make one slot fail the texture test while the bar is plainly
        full. Reading that as "Nearby is empty" is what sent the bot teleporting off through
        the feed bar with catchable Pokémon sitting right there.

        The returned target is always slot 1, whichever slot the sprite was actually read in.
        The list has no gaps — it fills from the top and closes up after each catch — so a sprite
        anywhere below proves slot 1 is occupied as well, and the read that missed it was the
        detector's failure, not an empty slot. Lower slots therefore serve as *evidence* that the
        bar is busy while the tap goes to the top entry, which is both the freshest and the one
        the calibrated point is known to line up with.

        Pure detection: no corroboration, no device I/O, so it is safe to call from the GUI's
        live view and from inside a poll.
        """
        cfg = self.config
        slot = cfg.nearby_slot if cfg.force_slot else self._slot_in(frame)
        if slot is None:
            return None
        # The manually calibrated point is already expressed in native screen pixels.
        # Keep its inspection window tight as well: scaling 70x110 once more on a
        # high-resolution phone dilutes a small/dark sprite with adjacent sidebar rows.
        half_width = 70 if cfg.force_slot else cfg.s(70)
        height = 110 if cfg.force_slot else cfg.s(110)

        if slot_has_pokemon(frame, slot, half_width=half_width, height=height):
            return slot
        if cfg.force_slot:
            # Step off slots at the measured pitch, stopping above the '@' that ends the bar.
            bottom = self._force_bar_bottom(frame, slot)
            for n in range(1, max(0, cfg.force_slot_count) + 1):
                y = slot[1] + n * cfg.slot_pitch
                if y > bottom or y >= frame.shape[0]:
                    break
                if slot_has_pokemon(frame, (slot[0], y), half_width=half_width, height=height):
                    self._trace("nearby_infer_top",
                                f"Đọc được Pokémon ở slot dưới (y={y}); danh sách không có chỗ "
                                f"trống nên tap slot đầu {slot}.")
                    return slot
            return None
        if self._anchor_cache is None:
            return None
        # Walk down to just above the '@' that ends the bar. A step well under the
        # inspection window's height cannot skip past a sprite.
        step = max(12, cfg.s(40))
        bottom = self._anchor_cache[1] - cfg.s(80)
        y = slot[1] + step
        while y <= bottom:
            if slot_has_pokemon(frame, (slot[0], y), half_width=half_width, height=height):
                self._trace("nearby_infer_top",
                            f"Đọc được Pokémon ở slot dưới (y={y}); danh sách không có chỗ "
                            f"trống nên tap slot đầu {slot}.")
                return slot
            y += step
        return None

    def _occupied_slot_in(self, frame) -> tuple[int, int] | None:
        """A Nearby slot to engage — a sighting that a second one has corroborated.

        One frame alone is not enough: the sprite test is marginal against a translucent
        sidebar, and acting on a false positive double-taps an empty slot. Requiring two
        *consecutive* frames was the old rule, and it erred the other way — H.264 smear drops
        the odd frame, so a bar that is plainly full alternates hit/miss, the streak never
        reaches two, and the bot idles in front of catchable Pokémon. Evidence is therefore
        counted over a short time window instead: two sightings close together, with misses in
        between allowed.
        """
        found = self._scan_slots(frame)
        if found is None:
            return None
        now = time.monotonic()
        last = self._nearby_last_seen_at
        self._nearby_last_seen_at = now
        if last is None:
            return None
        return found if now - last <= self.config.nearby_presence_window else None

    def _ui_state(self, *, force: bool = False):
        """PGSharp's own view hierarchy, or None. Rate-limited — a dump costs ~1.6s.

        force skips the rate limit, for the one moment where the answer cannot wait: straight
        after a teleport, when a cooldown may have just started."""
        cfg = self.config
        if not cfg.use_ui_dump:
            return None
        now = time.monotonic()
        if not force and now - self._ui_dump_at < cfg.ui_dump_cooldown:
            return None
        self._ui_dump_at = now
        state = uidump.parse(self.device.ui_dump() or "")
        if state is None:
            self._trace("ui_dump_fail",
                        "Không đọc được view tree (UI đang animate?); dùng nhận diện ảnh.", 0.0)
            return None
        # Every dump refreshes the cooldown for free, whatever it was taken for.
        self._note_cooldown(state.cooldown)
        return state

    def _mark(self, name: str) -> None:
        """Record how far into the cycle we are. No-op unless trace_timing is on."""
        if self.config.trace_timing:
            self._phases.append((name, time.monotonic() - self._phase_t0))

    def _flush_phases(self, outcome: str) -> None:
        """Write one line per cycle: the exit branch and the cost of each step up to it."""
        if not self.config.trace_timing or not self._phases:
            return
        total = time.monotonic() - self._phase_t0
        prev = 0.0
        parts = []
        for name, at in self._phases:
            parts.append(f"{name}={at - prev:.2f}")
            prev = at
        line = (f"{time.strftime('%H:%M:%S')} {outcome:<22} tong={total:5.2f}s  "
                + " ".join(parts))
        try:
            with open(self.config.timing_log, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass
        self._phases = []

    def _note_cooldown(self, seconds: float) -> None:
        """Record PGSharp's countdown as a local deadline, so it can be honoured without
        re-dumping: the clock runs down on its own once the end time is known."""
        self._cooldown_checked_at = time.monotonic()
        self._cooldown_until = (
            time.monotonic() + seconds + self.config.cooldown_margin if seconds > 0 else 0.0
        )

    def _cooldown_left(self) -> float:
        """Seconds still to wait before catching is safe again.

        Spends a dump on the question only every cooldown_check_interval — while a cooldown is
        already known the deadline counts itself down, and no dump is needed at all."""
        cfg = self.config
        if not cfg.respect_cooldown or not cfg.use_ui_dump:
            return 0.0
        now = time.monotonic()
        if self._cooldown_until > now:
            return self._cooldown_until - now
        if now - self._cooldown_checked_at >= cfg.cooldown_check_interval:
            self._ui_state()        # refreshes the deadline through _note_cooldown
            self._cooldown_checked_at = now
        return max(0.0, self._cooldown_until - time.monotonic())

    def _bar_visible(self, frame) -> bool:
        """True when the Nearby bar's '@' is on screen — i.e. we are back on the map.

        _slot_in only searches anchor_region, which hugs the right edge. A bar the user has
        dragged to the left of the screen is invisible to it, so any caller using it as a
        "the map is back" test never succeeds and instead waits out its whole timeout. The
        level-up handler did exactly that: fifteen seconds of tapping the screen centre twice a
        second, every single level-up, landing on whatever the map had at that spot.

        On a calibrated bar the '@' is looked for in the calibrated column instead, which is
        where it actually is whatever side the bar has been moved to.
        """
        if self._slot_in(frame) is not None:
            return True
        cfg = self.config
        if not cfg.force_slot or self._anchor is None:
            return False
        x, y = cfg.nearby_slot
        radius = cfg.s(120)
        region = (x - radius, y, radius * 2, cfg.slot_pitch * (cfg.force_slot_count + 3))
        return bool(find(frame, self._anchor, threshold=cfg.anchor_threshold,
                         scales=self._scales, region=region, max_matches=1))

    def _occupied_slot_ui(self) -> tuple[int, int] | None:
        """Ask PGSharp directly which Nearby slots are occupied, and where they are.

        This is not another estimate. PGSharp draws the bar as real Android views, so a node per
        occupied slot either exists or it does not — there is no threshold to get wrong, and the
        tap coordinate is the widget's own centre rather than a hand-calibrated guess. Verified
        against the pixel path on a live device: same slots, centres within 3px, three dumps
        running.

        Returns the top slot, matching _scan_slots: the bar has no gaps, and the top entry is the
        freshest. None means either an empty bar or a dump that could not be read, which the
        caller resolves by falling back to pixels.
        """
        state = self._ui_state()
        if state is None or not state.nearby:
            return None
        target = state.nearby[0]
        self._nearby_last_seen_at = time.monotonic()
        self._trace("nearby_ui_hit",
                    f"PGSharp báo {len(state.nearby)} Pokémon trên Nearby; tap slot đầu {target}.",
                    0.0)
        return target

    def _occupied_slot_fresh(self) -> tuple[int, int] | None:
        """Last word before declaring Nearby empty: re-read it on a one-shot capture.

        The stream's H.264 smear between keyframes is what makes a small or dark sprite fail
        the texture test, and that is exactly the failure that leaves the bot idling in front
        of a full bar. A crisp capture costs ~1s, so it is rate-limited and only spent once the
        cheap stream reads have already given up. A sighting here needs no corroborating frame:
        there was no smear that could have invented it.
        """
        cfg = self.config
        if cfg.nearby_fresh_cooldown < 0:
            return None
        now = time.monotonic()
        if now - self._nearby_fresh_at < cfg.nearby_fresh_cooldown:
            return None
        self._nearby_fresh_at = now
        found = self._scan_slots(self.device.screenshot(fresh=True))
        if found is not None:
            self._nearby_last_seen_at = time.monotonic()
            self._trace("nearby_fresh_hit",
                        f"Ảnh chụp nét thấy Pokémon tại {found} (stream đọc trượt).", 0.0)
        return found

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
        # A feed entry can sit arbitrarily far away — the feed lists fresh spawns, not close
        # ones — so this jump is the one action in the whole flow that earns a cooldown. Read it
        # now rather than waiting up to cooldown_check_interval to notice: that window is exactly
        # when the bot would otherwise keep catching through a soft-ban, and when the Nearby bar
        # still describes the place we just left.
        if cfg.respect_cooldown:
            self._ui_state(force=True)
            left = self._cooldown_left()
            if left > 0:
                self._trace("feed_cooldown",
                            f"Nhảy feed xong, PGSharp báo cooldown {left:.0f}s; ngừng bắt.", 0.0)
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

        # "Stop AutoWalk?" and its siblings: a stock two-button dialog. Handled before the
        # template-based popups because it is the one that actually blocks the flow here, and
        # because it is recognised by geometry rather than by a template that can go stale.
        buttons = find_dialog_buttons(frame, self.config.dialog_region)
        if len(buttons) >= 2:
            target = min(buttons, key=lambda b: b[0])      # leftmost = CANCEL
            self.device.tap(*target)
            self.stats.last_event = "popup"
            self._trace("dialog_cancel",
                        f"Hộp thoại chặn luồng ({len(buttons)} nút); bấm CANCEL tại {target}.",
                        0.0)
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
                    if self._bar_visible(f):
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
            m = find(frame, self._aw_paused, threshold=cfg.autowalk_paused_threshold,
                     scales=self._scales, grayscale=False, region=region, max_matches=1)
            if m:
                return m[0].center, True
        if self._aw_row is not None:
            m = find(frame, self._aw_row, threshold=cfg.autowalk_row_threshold,
                     scales=self._scales, region=region, max_matches=1)
            if m:
                return m[0].center, False
        return None

    def _paused_row_in(self, frame) -> tuple[tuple[int, int], float] | None:
        """Where the AutoWalk row is while it shows '⊘', plus the match score.

        The menu star is required here, unlike in _autowalk_row_in: without it that search widens
        to the whole frame, and a colour match on a 56px icon does find look-alikes out on the
        map — a tap landing on scenery rather than on the menu. No star in view also means the
        PGSharp overlay isn't up, so there is no row to tap anyway.
        """
        cfg = self.config
        if self._aw_paused is None or self._star is None:
            return None
        m = find(frame, self._star, threshold=cfg.menu_star_threshold, scales=self._scales,
                 grayscale=False, max_matches=1)
        if not m:
            return None
        sx, sy = m[0].center
        region = (sx - cfg.s(150), sy, cfg.s(300), cfg.s(700))
        hit = find(frame, self._aw_paused, threshold=cfg.autowalk_paused_threshold,
                   scales=self._scales, grayscale=False, region=region, max_matches=1)
        if not hit:
            return None
        target = hit[0].center
        # Same self-correction as _try_autowalk: every real sighting re-learns the offset.
        self._aw_offset = (target[0] - sx, target[1] - sy)
        return target, hit[0].score

    def _tap_autowalk_paused(self) -> bool:
        """Restart a stalled AutoWalk. Returns True only once the walk is confirmed running.

        Called on every empty Nearby cycle: a walk sitting paused is the most likely reason no
        spawns are arriving, so there is no point teleporting or idling before restarting it.
        Only a row showing '⊘' is tapped, so a walk that is already running is never touched and
        this can't raise the "Stop AutoWalk?" dialog however often it fires.

        The tap is then verified rather than assumed. A miss and a hit look identical from here —
        the icon is small, the menu is movable, and the stream frame it was located in may already
        be stale — so the row is re-read afterwards. '⊘' gone means the walk started; still there
        means the tap missed, and the retry re-locates it on a one-shot capture free of the H.264
        smear that shifts small-template matches in the first place.
        """
        cfg = self.config
        for attempt in range(max(0, cfg.autowalk_tap_retries) + 1):
            # First look rides the stream (cheap); retries pay ~1s for a crisp capture.
            frame = self.device.screenshot(fresh=attempt > 0, next_frame=attempt == 0)
            found = self._paused_row_in(frame)
            if found is None:
                # Nothing paused. On the first pass there was never anything to do; on a later
                # one the '⊘' we just tapped is gone, which is the walk confirmed running.
                if attempt > 0:
                    self._autowalk_active = True
                    self._trace("autowalk_paused_ok",
                                "Hàng AutoWalk đã chạy lại (icon '⊘' biến mất).", 0.0)
                return attempt > 0
            # About to touch the PGSharp menu, so prove on this very frame that it is the right
            # thing to touch. Both guards read the frame we are acting on, not an earlier one.
            #
            # Never from inside an encounter: this device keeps the menu visible there, so the
            # row is perfectly tappable while a Pokémon is on screen — and starting a walk mid
            # encounter loses it. The eager rule is deliberate here; any hint of an encounter at
            # all, from either signal, is enough to hold off.
            if self._in_encounter(frame):
                self._trace("autowalk_skip_encounter",
                            "Đang trong encounter; không bấm AutoWalk.", 0.0)
                return False
            # And only when Nearby really is empty on this same frame. The caller decided that
            # several frames ago; a Pokémon that has landed since is worth more than a walk.
            if self._scan_slots(frame) is not None:
                self._trace("autowalk_skip_nearby",
                            "Nearby vừa có Pokémon trở lại; bỏ qua AutoWalk.", 0.0)
                return False
            target, score = found
            self.device.tap(*target)
            self._trace("autowalk_paused_tap",
                        f"Nearby trống; tap hàng AutoWalk tạm dừng tại {target} "
                        f"(khớp {score:.2f}, lần {attempt + 1}).", 0.0)
            self._interruptible_sleep(cfg.autowalk_verify_delay)
            if self.stop_event.is_set():
                return False
        # Out of retries with '⊘' still on screen. Report the miss instead of claiming a walk:
        # the caller then falls through to the feed/idle path rather than waiting on a walk that
        # never started.
        self._trace("autowalk_paused_miss",
                    f"Đã tap {cfg.autowalk_tap_retries + 1} lần nhưng icon '⊘' vẫn còn — "
                    "nhiều khả năng tap trượt hàng AutoWalk.", 0.0)
        return False

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
        # Same rule as _tap_autowalk_paused: the menu stays tappable during an encounter on this
        # device, and starting a walk from inside one abandons the Pokémon.
        if self._in_encounter(frame):
            self._trace("autowalk_skip_encounter",
                        "Đang trong encounter; không bấm AutoWalk.", 0.0)
            return False
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
            # Strict: a throw has been made, so the camera has long since rendered. Insisting on
            # it here is what stops a phantom selector from holding the routine in an encounter
            # it already left.
            if not self._in_encounter(frame, strict=True):
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
                # Throw the moment the ball is actually grabbable, not after a fixed pause.
                # encounter_touch_delay_ms exists because the ball is not interactive the instant
                # the encounter opens — but it is a worst case, not a required wait, and on this
                # setup it was configured at 1.5s and paid in full every time. Polling for the
                # ball turns it into a cap: ready in 200ms means we throw at 200ms.
                if not self._poll(self._ball_ready, cfg.encounter_touch_delay_ms / 1000.0):
                    self._trace("ball_not_ready",
                                "Chưa thấy bóng ở điểm ném sau khi chờ; vẫn thử ném.", 0.0)
            # Reconfirm on a new frame immediately before touching the screen. This closes the
            # stale-frame race where the encounter vanished during the delay and the queued
            # throw landed on the map's centre Poké Ball.
            if not self._in_encounter(self.device.screenshot(next_frame=True)):
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
            # Out of throws without ever seeing the encounter close — but "never saw it close" is
            # not "still open": _throw_outcome returns 'timeout' precisely when it could not tell.
            # So read the screen once more before touching it. The old code tapped flee blind on
            # the assumption that flee_xy is inert once back on the map; it is not on a layout
            # where the PGSharp overlay occupies the top-left corner, and a stray tap there hits
            # the bar's drag handle. Strict: a throw has been made, so the camera has long since
            # rendered and demanding it costs nothing.
            if self._in_encounter(self.device.screenshot(next_frame=True), strict=True):
                self._trace("encounter_give_up",
                            "Hết lượt ném và vẫn còn trong encounter; bấm thoát.", 0.0)
                self.device.adb_tap(*cfg.flee_xy)
                self._poll(lambda f: True if not self._in_encounter(f, strict=True) else None, 2.0)
            else:
                self._trace("encounter_already_left",
                            "Hết lượt ném nhưng encounter đã đóng; bỏ qua tap thoát.", 0.0)
        if threw:
            self.stats.encounters += 1
        if cfg.settle_after_catch > 0:
            # Settle until the *next* Pokemon is on the bar, not merely until the map is back.
            # Two thirds of a cycle used to be spent on the map, and the tail of it was this: the
            # bar had already refilled while the routine was still waiting to be told the map had
            # returned, then went round the whole preamble again before looking. Ending the wait
            # on a sighting hands the next cycle a bar it can engage at once.
            #
            # Landing a sighting here also stamps _nearby_last_seen_at, so the corroboration in
            # _occupied_slot_in is already half satisfied and the next cycle can confirm on its
            # first frame instead of waiting for a second one.
            #
            # _bar_visible is still accepted, so an empty bar ends the wait as soon as the map is
            # back rather than burning the whole budget on a spawn that may not come.
            found = self._poll(
                lambda f: self._scan_slots(f) or (True if self._bar_visible(f) else None),
                cfg.settle_after_catch,
            )
            if isinstance(found, tuple):
                self._trace("settle_next_ready",
                            f"Encounter đóng, Pokémon kế tiếp đã sẵn tại {found}.", 0.0)
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
        self._phase_t0 = time.monotonic()
        self._phases = []
        self._ensure_calibrated()
        frame = self.device.screenshot()
        self._mark("chup")

        # Step 0: clear any blocking popup (speed warning, AutoWalk dialog) before doing anything.
        if self._drain_popups(frame):
            self._mark("popup"); self._flush_phases("popup")
            return False
        self._mark("popup")

        # Step 0.25: is PGSharp still counting down a jump cooldown? Catching through one is
        # exactly what gets an account soft-banned, so sit the rest of it out. AutoWalk keeps
        # running via the dry-spell path in run(), which is safe at normal walking speed.
        left = self._cooldown_left()
        self._mark("cooldown")
        if left > 0:
            self._flush_phases("cooldown")
            self._trace("cooldown_wait",
                        f"PGSharp báo cooldown còn {left:.0f}s; tạm dừng bắt.", 10.0)
            self._interruptible_sleep(min(left, 5.0))
            return False

        # Step 0.3: pace. Engaging again the instant the previous catch ends is what earns the
        # cooldown in the first place, so wait out the remainder of the floor before looking for
        # anything to engage. Popups and the cooldown check above still run, so the screen keeps
        # being tended to while we hold.
        if cfg.min_catch_interval > 0 and self._last_engage_at:
            wait = cfg.min_catch_interval - (time.monotonic() - self._last_engage_at)
            if wait > 0:
                self._trace("pacing",
                            f"Giữ nhịp: còn {wait:.1f}s nữa mới bắt con tiếp theo.", 5.0)
                self._interruptible_sleep(min(wait, 1.0))
                self._flush_phases("giu-nhip")
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
        # Strict: nothing here says an encounter should be open, so a lone ball-selector is more
        # likely a leftover from the one we just fled than a real encounter.
        self._mark("het-bong")
        ball_xy = self._ball_in(frame, strict=True)
        self._mark("check-enc")
        if ball_xy is not None:
            self._flush_phases("dang-trong-encounter")
            self._trace("encounter_open", "Đang ở trong encounter; ném luôn.", 0.0)
            return self._run_encounter(ball_xy)

        # Step 1: wait for the nearby bar (its '@' anchor). Polling here rides out the post-catch
        # transition/summary screen instead of wasting a whole cycle on it.
        slot = self._occupied_slot_in(frame)
        self._mark("quet-nearby")
        if slot is None:
            slot = self._poll(self._occupied_slot_in, cfg.anchor_timeout)
            self._mark("poll-nearby")
        if slot is None:
            # The stream said empty. Ask PGSharp itself before believing it — its view tree is
            # definitive where the pixels are only suggestive — and fall back to a crisp capture
            # when the dump cannot be read.
            slot = self._occupied_slot_ui() or self._occupied_slot_fresh()
            self._mark("ui+anh-net")
        if slot is None:
            # Nothing on Nearby — is the walk simply stalled? Restarting it is cheaper and less
            # disruptive than a teleport, and a paused walk is the most likely reason nothing is
            # spawning, so it gets first refusal. Only a row showing '⊘' is tapped, so a walk
            # that is already running falls straight through to the feed below.
            if self._tap_autowalk_paused():
                self._mark("autowalk"); self._flush_phases("autowalk")
                self.stats.autowalks += 1
                self._idle_streak = 0
                self._interruptible_sleep(cfg.autowalk_wait)
                return False
            # Still nothing — does the PGSharp feed list a fresh spawn? Teleporting to it
            # fills the Nearby bar for the next cycle, which beats idling until the dry-spell
            # timer fires. Only after several empty cycles in a row though: one empty read is
            # usually the sprite test dropping a frame, not an empty bar, and acting on it
            # teleports away from Pokémon that are sitting right there. The jump counts as
            # progress, so the AutoWalk streak resets.
            self._mark("autowalk")
            if self._idle_streak >= cfg.feed_after_idle and self._tap_feed_spawn():
                self._flush_phases("feed-teleport")
                self._idle_streak = 0
                return False
            self._mark("feed"); self._flush_phases("NEARBY-TRONG")
            self._trace("nearby_empty", "Không thấy Pokémon trên thanh Nearby lẫn thanh feed.")
            self._interruptible_sleep(cfg.idle_poll)
            return False

        # Step 1.5: prove the sidebar is still there before tapping into it. In force_slot mode
        # nothing else checks — the calibrated point is trusted outright — so a slot that reads
        # occupied while the bar is hidden or collapsed is really the map showing through where
        # the bar would be. The tap then lands on the map, and PGSharp answers a map tap with its
        # "Tap to Walk/Teleport — Stop AutoWalk?" dialog, which stops the walk and blocks
        # everything until dismissed. Read on a current frame, not the one the cycle opened with,
        # because the slot may have been found several frames later.
        if not self._bar_visible(self.device.screenshot()):
            self._trace("nearby_bar_gone",
                        "Thanh Nearby không còn trên màn hình; bỏ tap để khỏi chạm vào map.", 0.0)
            self._mark("chan-tap")
            self._flush_phases("BAR-KHONG-HIEN")
            self._interruptible_sleep(cfg.idle_poll)
            return False

        # Step 2: engage it. A single tap goes in first and the double-tap follows after
        # pre_tap_delay. The ball-selector poll returns the instant the encounter opens; if it
        # never shows within encounter_timeout the slot was empty or the Pokémon fled.
        if cfg.pre_tap_delay > 0:
            self.device.tap(*self._jitter(*slot))
            self._trace("nearby_pre_tap",
                        f"Tap đơn mở đầu tại {slot}; chờ {cfg.pre_tap_delay:.1f}s rồi double-tap.",
                        0.0)
            self._interruptible_sleep(cfg.pre_tap_delay)
            if self.stop_event.is_set():
                return False
            # No encounter check in between: the single tap on its own does not open the
            # encounter, and the ball-selector test can read positive on the map right after it,
            # which threw a ball at nothing. The double-tap below is what actually engages the
            # Pokémon, so it always runs.
        self._mark("tap-don")
        self._last_engage_at = time.monotonic()
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
        self._mark("cho-encounter")
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
            self._mark("thu-lai"); self._flush_phases("KHONG-MO-DUOC")
            self._interruptible_sleep(cfg.idle_poll)
            return False
        threw = self._run_encounter(ball_xy)
        self._mark("encounter")
        self._flush_phases("BAT-XONG")
        return threw

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
        # The live view draws both detectors, so it asks for both rather than letting
        # _in_encounter short-circuit past the ball sweep.
        self._enc_ball_visible(frame)
        in_enc = self._in_encounter(frame)
        if self._enc_ball_at is not None:
            cv2.circle(img, self._enc_ball_at, cfg.s(70), (0, 0, 255), 4)
            cv2.putText(img, "ENC", (self._enc_ball_at[0] - cfg.s(40),
                                     self._enc_ball_at[1] - cfg.s(80)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        box(cfg.out_of_balls_region, (0, 140, 255), "x0")
        # Camera button: the encounter's second signal. Green when it reads present.
        box(cfg.enc_camera_region, (0, 255, 0) if self._enc_camera_seen else (120, 120, 120),
            "CAM" + ("" if self._enc_camera_seen else "?"))

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
            # Draw what a single frame sees. Going through _occupied_slot_in would both consume
            # the routine's corroboration window and hide a real sighting behind it.
            target = self._scan_slots(frame)
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
