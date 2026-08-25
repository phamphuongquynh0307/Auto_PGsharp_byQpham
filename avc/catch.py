"""Pokémon catch routine.

Per cycle:
  0. If the bottom-left Berry button is already showing we're inside an encounter (a
     break-out, or one that opened late) — throw at it right away. The encounter screen hides
     the sidebars, so anything that scans for them first can never get out of this state.
  1. Otherwise find a Pokémon to engage, in order:
       * the nearby-Pokémon sidebar's first slot — double-tap it; after a catch the list
         auto-advances, so the same slot position always holds the next target;
       * failing that, the PGSharp *feed* sidebar's first slot — tapping it teleports to that
         spawn, which fills the nearby bar for the next cycle instead of idling.
  2. Confirm we're actually in an encounter via the bottom-left Berry button.
  3. Swipe up from the ball to throw it, then read the outcome: encounter closed (caught or
     fled), or the ball is back at the throw point (break-out) — throw again. After the last
     allowed throw the encounter is fled, so the flow always returns to the map.

The Berry glyph is read only inside its fixed circular button. When it isn't showing we're
not in an encounter, so the cycle counts as empty and the AutoWalk dry-spell logic keeps working.
"""
from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field, replace

import os
import numpy as np

from .device import Device
from .layout import (
    BASE_DENSITY, BASE_GAME_SPAN, BASE_RESOLUTION, CALIBRATION_MIN_SCORE,
    CALIBRATION_SWEEP, Layout,
    bracket_scales, scales_around,
)
from . import uidump
from .resources import resource_path
from .vision import (
    best_matching_scale, find, find_berry_button, find_enc_ball, find_fast, find_popup_close,
    find_dialog_buttons, find_disconnected_goplus, find_pokestops, load_template,
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


# Pokémon GO moved the on-ball quantity badge to the right of the centre ball. Builds using
# the first box below only searched the hub itself and could never see the new ``x0`` position.
# Keep the old value named so the GUI can migrate an unchanged saved calibration safely.
LEGACY_OUT_OF_BALLS_REGION = (390, 2545, 340, 167)
CURRENT_OUT_OF_BALLS_REGION = (350, 2400, 600, 312)

# Do not tap on the very first transition frame after an encounter closes. After this short
# floor, the routine compares the old slot's visual fingerprint with fresh Nearby frames and can
# proceed as soon as the row really changed. The longer value is only a fallback ceiling for an
# identical next sprite or an unreadable transition, not a fixed sleep on every catch.
MIN_POST_CATCH_REFRESH = 0.25
DEFAULT_POST_CATCH_REFRESH_TIMEOUT = 1.2
SLOT_REFRESH_HIST_DISTANCE = 0.30


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
    # the minimum safety delay below; fully removing the priming tap made this phone accept only
    # every other encounter gesture.
    # The single primer only needs to precede the double-tap by one short Android input beat.
    # 0.8s was visibly idle time on every successful encounter; 120ms keeps the cold-row fix
    # while opening the common encounter roughly 0.7s sooner.
    pre_tap_delay: float = 0.12
    pre_tap_min_delay: float = 0.12
    # Corroboration for a Nearby sighting: a second hit within this many seconds confirms the
    # first. Counting over a window rather than over *consecutive* frames is what stops one
    # smeared stream frame from wiping the evidence and leaving the bot idle in front of a full
    # bar. 0 accepts a single frame (fastest, most false positives).
    nearby_presence_window: float = 1.5
    # A PGSharp sprite is drawn above the translucent sidebar and retains full-value pixels;
    # gyms/map art bleeding through an empty bar is darkened. Shared by Nearby and Feed scans.
    slot_foreground_bright_fraction: float = 0.008
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
    # Optional in Catch mode. Off by default: existing users keep Nearby + AutoWalk only.
    # When enabled, one Feed entry is tapped only after Nearby is confirmed empty. A pending
    # Feed jump stays locked until its Pokemon appears on Nearby and that encounter is handled.
    use_feed_bar: bool = False
    feed_rss_template: str = "templates/feed_rss.png"
    bar_handle_template: str = "templates/bar_handle.png"
    feed_threshold: float = 0.7
    feed_slot_dy: int = 100         # '≡' handle center -> first feed slot center
    handle_column_tol: int = 60     # max |x_handle - x_rss| to count as the same bar
    feed_teleport_wait: float = 4.0  # fast-path wait right after the tap, before polling
    # Ceiling on the poll that follows. The lock exists so a slow teleport cannot consume a
    # second Feed item, and it used to have no ceiling at all — so a tap PGSharp silently
    # dropped, or a spawn that despawned before it loaded, parked the whole routine here for
    # as long as the user let it run (observed: 11 minutes standing still). Giving up hands the
    # cycle back to Nearby + AutoWalk; the next Feed tap still has to earn its idle streak
    # again. 0 restores the old behaviour of waiting indefinitely.
    feed_nearby_timeout: float = 45.0
    # How often a crisp capture may be spent looking for a feed bar that stream frames have
    # never managed to match. Bounded because a user who ticked the box but has no feed bar
    # open would otherwise pay for one every dry cycle.
    feed_fresh_cooldown: float = 20.0
    # Consecutive empty cycles required before the feed may teleport. The sprite test is
    # marginal against a busy translucent sidebar (event scenery, gyms) and loses the odd
    # frame on a bar that is actually full; teleporting on one such read jumps away from
    # catchable Pokémon. Several empty cycles in a row is evidence, one is noise.
    feed_after_idle: int = 1

    # Throw start point. Sits on the encounter ball's upper half: high enough that a blind
    # throw on the map (y >= 2467 is the map's pokeball menu button) can't press the menu.
    ball_fallback: tuple[int, int] = (610, 2380)
    # "Is there still a ball to throw?" is read at the ball's round centre button — a light grey
    # hub inside a thick black band — not at its dome. The dome's colour is the *ball type*
    # (red Poké, blue Great, black/yellow Ultra, purple Master), so a red-only dome test called
    # a full bag empty the moment the game switched type; the hub looks the same on every type.
    ball_hub: tuple[int, int] = (610, 2615)
    ball_hub_radius: int = 90
    # Encounter signal: the raspberry glyph inside the bottom-left Berry button. The fixed
    # circular footprint prevents red Pokemon, thrown balls, and map controls from being
    # mistaken for an encounter. The detector scans for and returns the button's real centre;
    # ``berry_start`` below remains only the Quick Catch drag coordinate.
    enc_berry_radius: int = 95
    enc_berry_min_fill: float = 0.06

    # Out of balls: in an encounter the ball-count badge reads "x0" — a distinctive red pill at
    # the lower-right edge of the centre ball. When it shows we're out of Poké Balls: flee, alert,
    # and hold off catching for a while (still AutoWalking) so the bag can refill instead of
    # burning cycles on an empty encounter. Matched in colour so a red "x0" can't be confused
    # with a neutral non-zero count. The box also includes the old badge position.
    out_of_balls_template: str = "templates/out_of_balls.png"
    out_of_balls_threshold: float = 0.72
    out_of_balls_region: tuple[int, int, int, int] = CURRENT_OUT_OF_BALLS_REGION
    # Newer game builds remove the whole ball selector when the bag is empty instead of showing
    # the old red ``x0`` badge. Keep the template as the instant/legacy signal, then treat a
    # stable encounter with no throwable ball for this long as the current signal. Requiring
    # several distinct frames prevents the selector's entrance animation from looking empty.
    # The window also has to outlast the swap the game does when one ball type runs out and the
    # next takes over, which briefly leaves the selector empty while the bag is not.
    no_balls_missing_timeout: float = 2.0
    no_balls_missing_frames: int = 3
    flee_xy: tuple[int, int] = (120, 170)   # encounter flee (running-man) button, top-left
    no_balls_pause: float = 600.0           # seconds to hold off catching when out of balls (10 min)
    no_balls_walk_interval: float = 15.0    # re-check AutoWalk this often during the hold-off
    # PGSharp's Go Plus support requires a paid key. The GUI only enables this for normal/keyed
    # catching; the quick/no-key path always leaves the accessory alone.
    start_goplus_on_no_balls: bool = True
    goplus_after_autowalk_wait: float = 1.0  # let AutoWalk settle before starting Go Plus

    # ---- PokéStop spinning (the "Quay stop" mode, and optionally the out-of-balls hold) ----
    # An unspun stop is one flat bright blue and a spun one is violet, so the colour test is
    # also the "worth tapping" test — see vision.find_pokestops. Needs no PGSharp key and no
    # Go Plus, which is the whole point: it is the refill path for users who have neither.
    #
    # The search area is the *ellipse inscribed in this box*. A circle rather than the whole
    # screen because the screen's edges are HUD: the right icon rail, the PGSharp menu column and
    # the bottom controls are all blue-ish, and one tap that strayed onto the rail opened a
    # full-screen map view that took a Back press to leave — which then asked whether to quit
    # Pokémon GO. The box is drag/resizable in the calibration window, since how far a stop can
    # sit and still be in range depends on the player's zoom level, not on the app.
    #
    # Default: radius 450 around the avatar's feet (610, 1750) — half the box the player drew
    # over their own map. Wide enough to cover the pole a stop's cube stands on (~170 px above
    # its ground disc), which is why it is not the ~220 px ring the game itself paints.
    # See App._spin_config, which rebuilds this from the GUI's radius setting.
    spin_region: tuple[int, int, int, int] = (160, 1300, 900, 900)
    # px² of solid blue before a blob counts as a stop. Deliberately small: the point is to spot
    # the *colour*, not to outline a whole stop. A stop standing next to the avatar is drawn as a
    # disc over a cube barely 45 px across, so a floor set to the size of the far-away pillar
    # (2000+) skipped exactly the stops that were close enough to tap.
    spin_min_area: int = 700
    spin_interval: float = 2.0      # pause between stop taps
    spin_settle: float = 1.2        # let the tap land (and PGSharp's dialog appear) before reading
    # A tapped stop keeps its blue for a moment, and one that was out of range keeps it for good.
    # Remembering where we just tapped is what stops the loop from spending every cycle on the
    # same unreachable stop while the walk carries real ones past it.
    spin_skip_seconds: float = 60.0
    spin_skip_radius: int = 140
    spin_on_no_balls: bool = False  # spin PokéStops during the empty-bag AutoWalk hold

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
    # Some phones spend longer than encounter_timeout on the white map -> encounter transition.
    # This is an upper bound, not a fixed sleep: polling returns on the first Berry-button frame,
    # so a normal fast opening does not pay any of the extra budget.
    encounter_transition_grace: float = 2.0
    # A rejected Nearby gesture leaves both the bar and its Pokemon visibly in place. Do not
    # spend the entire encounter timeout waiting for a transition that never started: after a
    # short grace, two fresh frames proving that state return control to the next retry.
    engage_miss_grace: float = 0.8
    engage_miss_frames: int = 2
    catch_timeout: float = 6.0      # max wait per throw for the encounter to end (ball gone)
    settle_after_catch: float = DEFAULT_POST_CATCH_REFRESH_TIMEOUT  # adaptive refresh ceiling
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
    # The menu's Settings gear — its last row, and so the cheapest proof that the menu is
    # expanded. The star renders in both states and cannot answer the question. Nothing used to
    # open the menu because leaving it expanded is the normal state, but collapsed it hides the
    # AutoWalk row, Feeds and Teleport, and every path that reaches for them then fails silently.
    pgsharp_menu_template: str = "templates/pgsharp_menu.png"
    pgsharp_menu_threshold: float = 0.7
    # How far below the star to search for that gear. It is the menu's *last* row, so this has to
    # reach further than the AutoWalk row's box: measured on a 1220x2712 device the gear centre
    # sits 690px below the star and the icon is 80px tall, putting its bottom edge at 770. The
    # AutoWalk row's 700 clipped it by 30px and read an open menu as shut.
    menu_gear_span: int = 850
    menu_open_wait: float = 0.6     # let the menu animate out before the next cycle reads it
    # How many full calibration sweeps to spend before accepting that this device's star cannot
    # be matched. The sweep is the routine's single most expensive operation (~2.7s), and not
    # locking is already a supported state — see _ensure_calibrated.
    cal_max_attempts: int = 3
    # The star sits on the always-on PGSharp menu and only moves when the user drags the menu, so
    # a match is re-checked in a box around the last one before the full-frame search is paid for.
    # Full frame costs ~0.6-0.9s; this box costs ~10ms, and _paused_row_in now runs on every
    # empty Nearby cycle, which is exactly where those hundreds of ms were going.
    star_cache_radius: int = 130
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
    # The device's *measured* render scale, once the routine has matched a known icon against
    # the real screen (see CatchRoutine._ensure_calibrated). Outranks the density guess, which
    # can be well out: a 1080x2400 panel reporting 480dpi guesses 1.000 against a true 0.885,
    # which drops the first Nearby slot 88px from where it is — most of a 106px slot pitch, so
    # the bot inspects and taps the wrong entry. None until measured.
    render_scale: float | None = None
    # The measured render scale of Pokémon GO's *own* UI, which need not match the overlay's.
    # Measured from the distance between two game controls the routine can already find without
    # any template — see CatchRoutine._sample_game_scale. None until measured, in which case the
    # game layer falls back to the same density estimate as before.
    game_scale: float | None = None
    # The BASE_RESOLUTION original this was scaled from, kept so the coordinates can be derived
    # again at the measured scale rather than nudged from an already-scaled copy — anchoring is
    # not a plain multiply, so re-scaling a scaled config does not round-trip. Set by scale_to.
    base_config: "CatchConfig | None" = field(default=None, repr=False, compare=False)

    @property
    def layout(self) -> Layout:
        return Layout(*self.screen, density=self.density, scale=self.render_scale)

    def s(self, v: float) -> int:
        """Scale a pure distance/size (swipe length, search radius, offset)."""
        return self.layout.scale(v)

    def pt(self, p: tuple[int, int], anchor: str) -> tuple[int, int]:
        """Map an absolute point authored in base coords; anchor e.g. 'BC', 'TL'."""
        return self.layout.point(p, anchor)

    def rect(self, r: tuple[int, int, int, int], anchor: str) -> tuple[int, int, int, int]:
        """Map an absolute box authored in base coords; anchor e.g. 'BC', 'TC'."""
        return self.layout.region(r, anchor)

    def rescale(self, scale: float) -> "CatchConfig":
        """Re-derive every coordinate at a *measured* render scale, replacing the density guess.

        Always works from the BASE_RESOLUTION original rather than from the already-scaled copy:
        edge anchoring subtracts from the device's width/height, so scaling a scaled config does
        not compose into scaling once by the product.
        """
        base = self.base_config or self
        return base.scale_to(*self.screen, self.density, scale=scale,
                             game_scale=self.game_scale)

    def rescale_game(self, game_scale: float) -> "CatchConfig":
        """Re-derive only Pokémon GO's own coordinates at a measured game render scale,
        leaving the overlay layer on whatever it is already using."""
        base = self.base_config or self
        return base.scale_to(*self.screen, self.density, scale=self.render_scale,
                             game_scale=game_scale)

    def scale_to(self, width: int, height: int, density: int | None = None,
                 *, scale: float | None = None,
                 game_scale: float | None = None) -> "CatchConfig":
        """Return a copy with every pixel coordinate re-anchored from BASE_RESOLUTION onto
        (width, height) at `density` dpi. Each field is tagged with the screen edge/corner it
        hugs so it lines up on any aspect ratio (see avc/layout.py). Timings, thresholds and
        template paths are untouched. No-op (returns self) at the base resolution+density.

        `scale` overrides the density estimate with a measured render scale; see `rescale`.

        Two layouts, because the screen holds two UIs that need not render alike. `L` covers
        everything drawn as native Android views — PGSharp's overlay and the system dialogs it
        raises — which is what the scale is ever measured from, since those are the only icons
        reliably on screen. `G` covers Pokémon GO's own UI, which is drawn by the game engine and
        answers to nothing measured here.

        Keeping them apart is what stops an overlay measurement from dragging the Berry button,
        the flee button and the throw with it.

        Their *defaults* differ too, and each is the model its own layer was measured to follow.
        The overlay is native Android views laid out in dp, so its default is the density ratio;
        on MuMu the measured overlay scale (0.57) sits by the density estimate (0.5625) and 17%
        from the width ratio. The game is engine-drawn and follows the *screen*, not the density:
        the berry↔ball span measured 0.6641 on MuMu and 1.0506 on a 1280x2772@520 phone, against
        width ratios of 0.6639 and 1.0492 (0.03% and 0.13% off) where the density ratio was 18%
        and 3% out. Defaulting `G` to width means every device starts ~0.1% right instead of
        paying that error until its first encounter lets _sample_game_scale correct it; the
        measurement stays as the check, overriding the default when the two disagree.
        """
        L = Layout(width, height, density=density, scale=scale)
        G = Layout(width, height, scale=game_scale)   # no density: width ratio is the default
        if ((width, height) == BASE_RESOLUTION
                and abs(L.s - 1.0) < 1e-9 and abs(G.s - 1.0) < 1e-9):
            return self
        return replace(
            self,
            screen=(width, height),
            density=density,
            render_scale=scale,
            game_scale=game_scale,
            base_config=self.base_config or self,
            # anchored positions/regions
            # --- PGSharp overlay and system dialogs (native views) ---
            anchor_region=L.region(self.anchor_region, "TR"),   # nearby bar hugs right edge
            nearby_slot=L.point(self.nearby_slot, "TR"),
            dialog_region=L.region(self.dialog_region, "MC"),  # centred Android AlertDialog
            cancel_btn_region=L.region(self.cancel_btn_region, "MC"),  # centred system dialog
            slot_offset_y=L.scale(self.slot_offset_y),
            slot_pitch=L.scale(self.slot_pitch),
            feed_slot_dy=L.scale(self.feed_slot_dy),
            handle_column_tol=L.scale(self.handle_column_tol),
            autowalk_offset_x=L.scale(self.autowalk_offset_x),
            autowalk_offset_y=L.scale(self.autowalk_offset_y),
            # --- Pokémon GO's own UI (engine-drawn; never follows a measured overlay scale) ---
            ball_fallback=G.point(self.ball_fallback, "BC"),    # throw start, bottom-centre
            ball_hub=G.point(self.ball_hub, "BC"),              # ball centre button
            ball_hub_radius=max(8, G.scale(self.ball_hub_radius)),
            berry_start=G.point(self.berry_start, "BL"),        # Berry drawer, bottom-left
            berry_end=G.point(self.berry_end, "BL"),
            out_of_balls_region=G.region(self.out_of_balls_region, "BC"),
            check_btn_region=G.region(self.check_btn_region, "BC"),
            caught_ok_region=G.region(self.caught_ok_region, "MC"),
            maybe_later_region=G.region(self.maybe_later_region, "MC"),
            flee_xy=G.point(self.flee_xy, "TL"),                # flee button, top-left
            pokestop_close_xy=G.point(self.pokestop_close_xy, "BC"),
            # The avatar is drawn about the middle of the map, so the scan circle around it is
            # anchored to the screen centre rather than to any edge.
            spin_region=G.region(self.spin_region, "MC"),
            spin_skip_radius=max(8, G.scale(self.spin_skip_radius)),
            throw_dy=G.scale(self.throw_dy),
            jitter_px=max(1, G.scale(self.jitter_px)),
            enc_berry_radius=max(8, G.scale(self.enc_berry_radius)),
        )


@dataclass
class CatchStats:
    cycles: int = 0
    throws: int = 0        # balls actually thrown (a break-out costs more than one)
    encounters: int = 0    # Pokémon engaged — what max_catches counts
    autowalks: int = 0
    spins: int = 0         # PokéStops tapped
    last_event: str = ""   # "throw" | "idle" | "autowalk" | "spin"


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
        # A device that already renders at base scale has no uncertainty for the bracket to
        # absorb, and the popup sweep is where paying for it hurts: every template is looked for
        # on every cycle, and all but one of them is absent almost every time. Measured on a
        # 1220x2712 @480dpi device, matching at 1.0 alone against a scene rendered ±6% off still
        # scores 0.751 .. 0.912 across the five templates on screen at once — clear of the 0.7
        # popup threshold — so the other two scales buy nothing there. Off the base scale the
        # bracket spans a real span (s .. 1.0) and is kept.
        self._base_scale = abs(self._tpl_s - 1.0) < 1e-3
        # PGSharp/system dialogs and Pokemon GO dialogs are separate render layers. On MuMu
        # they were measured at ~0.57 and ~0.66 respectively; using the overlay scale for both
        # is why warning/medal popups worked on the authoring phone but disappeared on others.
        self._popup_scales = (1.0,) if self._base_scale else self._scales
        game_s = Layout(*self.config.screen, scale=self.config.game_scale).s
        game_base_scale = abs(game_s - 1.0) < 1e-3
        self._game_popup_scales = ((1.0,) if game_base_scale else bracket_scales(game_s))
        # The level-up screen was measured rendering at a different scale from the PGSharp
        # overlay on MuMu (claim ~0.67 against a 0.55 star), which is why it swept the full
        # calibration range. That divergence is a property of a device that rescales the UI; at
        # base scale there is nothing to diverge from, and the wide sweep was half the cost of
        # the entire popup pass (88.8ms of 178ms) for a screen that shows up once a level.
        self._claim_scales = (
            self._game_popup_scales if game_base_scale else CALIBRATION_SWEEP
        )
        self._cal_scale: float | None = None   # measured render scale; None until calibrated
        self._anchor_cache: tuple[int, int] | None = None
        self._star_cache: tuple[int, int] | None = None   # last star match, to skip the full sweep
        self._cal_attempts = 0            # calibration sweeps spent; capped, see _ensure_calibrated
        self._nearby_handle_cache: tuple[int, int] | None = None
        self._force_bottom_cache: tuple[int, int] | None = None   # '@' ending a calibrated bar
        self._force_bottom_value: int | None = None               # its floor, cached for a TTL
        self._force_bottom_at = 0.0
        self._enc_berry_at: tuple[int, int] | None = None  # actual detected Berry-button centre
        # Game-UI render scale measurement: readings collected, and whether the question is
        # settled (either adopted or judged close enough). See _sample_game_scale.
        self._game_samples: list[float] = []
        self._game_scale_done = False
        # When the Nearby bar was last seen holding a sprite (corroboration window), and when
        # the slow one-shot re-read was last spent (rate limit).
        self._nearby_last_seen_at: float | None = None
        self._nearby_fresh_at = 0.0
        # Colour histogram of the top Nearby sprite that was actually engaged. It lets the
        # post-catch wait finish when the list visibly advances rather than sleeping a fixed
        # 1.2 seconds after every encounter.
        self._engaged_slot_signature: np.ndarray | None = None
        # Manual calibration is only a starting estimate. PGSharp's UI hierarchy supplies the
        # real centre of slot 1; once observed it wins for the rest of the run. This prevents a
        # stale manual y-coordinate from repeatedly tapping below a lone Pokemon.
        self._ui_nearby_slot: tuple[int, int] | None = None
        # Set by _occupied_slot_ui when a readable dump located the Nearby bar and found it
        # empty. That is a definite answer, so the ~2.85s crisp capture behind it is skipped.
        self._ui_empty_confirmed = False
        self._engage_still_nearby = False
        # Classification for the current run_once result. A tap retry or an encounter
        # transition is active Pokémon work, not an empty Nearby cycle; run() uses this to keep
        # AutoWalk and dry-spell alerts out of the middle of an encounter.
        self._cycle_result = "idle"
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
        # Why the last _feed_slot_in came back empty, and when a crisp capture was last spent
        # hunting a bar the stream cannot match. Without the first, "không thấy Pokémon trên
        # thanh feed" covers four different situations and none of them can be told apart.
        self._feed_miss: str | None = None
        self._feed_fresh_at = 0.0
        # A Feed tap consumes/moves the queue immediately, while its Pokemon may need many
        # seconds to load into Nearby. Keep the queue locked across catch cycles so an ordinary
        # timeout cannot tap the next Feed entry and abandon the first spawn.
        self._feed_pending = False
        self._feed_pending_at = 0.0
        # Set when a CANCEL was just tapped, so the feed source can tell its own teleport was
        # refused (Go Plus warning) apart from a CANCEL on some unrelated dialog.
        self._cancelled_dialog = False
        self._teleport_blocked = False
        # Star -> AutoWalk-row offset measured on this device, replacing the config guess as
        # soon as the row is seen once.
        self._aw_offset: tuple[int, int] | None = None
        # (when, x, y) of stops already tapped, so the loop moves on instead of re-tapping one
        # that stayed blue because it was out of range. Expired by spin_skip_seconds.
        self._spin_seen: list[tuple[float, int, int]] = []
        self._on_trace = None
        self._trace_last_key = ""
        self._trace_last_at = 0.0

        def load(path):
            return load_template(_resolve(path))

        def load_opt(path):
            return _load_optional(path)

        self._anchor = load(self.config.anchor_template)
        self._star = load(self.config.menu_star_template)
        self._gear = load_opt(self.config.pgsharp_menu_template)
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
        # AutoWalk's counter above is reset the moment it fires, so with idle_before_autowalk at
        # 1 it never holds anything but 0 — and the feed, which read the same counter, could
        # never clear its own threshold, so _tap_feed_spawn was short-circuited away and never
        # once called. Two features cannot share one counter when one of them resets it. This
        # one counts consecutive dry cycles for the feed alone.
        self._dry_streak = 0
        self._autowalk_active = False
        self._no_balls = False   # set by run_once when the "x0" badge is seen; consumed by run()
        # One genuine empty-bag episode should produce one Discord warning, not another warning
        # every time the refill wait expires. A successful throw arms the warning again.
        self._no_balls_alerted = False
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

    def _in_encounter(self, frame, *, strict: bool = False) -> bool:
        """True only when the fixed bottom-left Berry control is visibly present.

        ``strict`` stays in the signature for existing callers. There is deliberately one
        encounter answer now: camera and Poke Ball detections no longer participate.
        """
        cfg = self.config
        self._enc_berry_at = find_berry_button(
            frame,
            scale=cfg.layout.s,
            radius=cfg.enc_berry_radius,
            min_berry_fill=cfg.enc_berry_min_fill,
        )
        if self._enc_berry_at is not None:
            # Measuring is strictly a bonus; deciding whether we are in an encounter is not.
            # Nothing about the former may be allowed to break the latter.
            try:
                self._sample_game_scale(frame)
            except Exception:  # noqa: BLE001
                pass
        return self._enc_berry_at is not None

    # The ruler itself is a base-device fact and lives with the others, in avc/layout.py.
    #
    # A *distance* is the right thing to measure, and the reason is that the obvious alternative
    # is wrong: comparing a detected Berry centre against `berry_start` would look equivalent but
    # berry_start is the Quick Catch drag point, not the button's centre (base 2410 against a
    # detected 2467), so every reading would inherit that 57px bias.
    #
    # These two are judgement, not arithmetic — how much agreement is enough to believe a
    # detector that documents itself as tolerating false positives.
    GAME_SCALE_SAMPLES = 3          # readings required before the answer is believed
    GAME_SCALE_SPREAD = 0.03        # they must agree this closely, or the set is discarded
    # The adopt threshold, by contrast, is not chosen at all: how far apart the accepted readings
    # landed *is* how precisely this device measured, so anything a few times wider than that
    # cannot be measurement noise. A steady device therefore earns a tighter threshold and gets
    # smaller real errors corrected, while a jittery one is made to prove more — neither of which
    # a single number written in advance can do, since it has to be loose enough for the worst
    # device and is then far too loose for every other one.
    GAME_DRIFT_SPREAD_FACTOR = 3.0
    # A few readings can agree by luck, and perfect agreement would otherwise derive a threshold
    # of zero and rescale on any difference at all. This floor is what the derivation cannot
    # bargain below; it also absorbs a systematic bias between the two detectors, which spread
    # cannot see because it shifts every reading the same way.
    GAME_DRIFT_FLOOR = 0.01

    def _sample_game_scale(self, frame) -> None:
        """Measure how big Pokémon GO draws its own UI, from two controls found without templates.

        This is the one layer nothing could correct. The render scale the routine measures comes
        from PGSharp's overlay, and there is no reason the game engine follows it — so applying
        it here was ruled out, which left the game's coordinates on the density estimate with no
        way to ever find out it was wrong. On MuMu the density estimate (0.5625) and the
        resolution ratio (0.6639) are 18% apart, and nothing on screen could say which was right.

        Two guards, because a single reading cannot be trusted: `find_berry_button` documents
        itself as tolerating false positives, and one was seen on a live map frame during this
        work. Both are cheap and both catch it — that phantom implied 0.448 across and 0.824
        down, so requiring several readings to agree rejects it outright.
        """
        cfg = self.config
        if cfg.game_scale is not None or self._game_scale_done:
            return
        ball = find_enc_ball(frame, scale=cfg.layout.s)
        if ball is None or self._enc_berry_at is None:
            return
        bx, by = self._enc_berry_at
        span = math.hypot(ball[0] - bx, ball[1] - by)
        if span <= 0:
            return
        self._game_samples.append(span / BASE_GAME_SPAN)
        if len(self._game_samples) < self.GAME_SCALE_SAMPLES:
            return
        recent = self._game_samples[-self.GAME_SCALE_SAMPLES:]
        measured = sum(recent) / len(recent)
        if not measured:
            return
        spread = (max(recent) - min(recent)) / measured
        if spread > self.GAME_SCALE_SPREAD:
            self._game_samples = self._game_samples[-1:]   # disagreement: keep collecting
            return
        self._game_scale_done = True
        # Even when the coordinate drift is too small to justify moving every game control,
        # centre popup matching on what the game actually rendered. Popup templates are less
        # tolerant than tap coordinates, and they must never inherit PGSharp's overlay scale.
        self._game_popup_scales = scales_around(measured)
        self._claim_scales = (
            self._game_popup_scales
            if abs(measured - 1.0) < 1e-3 else CALIBRATION_SWEEP
        )
        # No density: the game layer's default is the width ratio, and `current` must be
        # whatever scale_to actually used or the comparison is against the wrong baseline.
        current = Layout(*cfg.screen, scale=cfg.game_scale).s
        min_drift = max(self.GAME_DRIFT_FLOOR, self.GAME_DRIFT_SPREAD_FACTOR * spread)
        if not current or abs(measured - current) / current < min_drift:
            return
        try:
            rescaled = cfg.rescale_game(measured)
        except Exception:  # noqa: BLE001 - a bad re-derive must not end the run
            return
        hook = getattr(self, "_on_rescale", None)
        if hook is not None:
            try:
                rescaled = hook(rescaled) or rescaled
            except Exception:  # noqa: BLE001
                pass
        self.config = rescaled
        self._trace("game_scale_fixed",
                    f"Đo được scale giao diện game {measured:.3f} (đang dùng {current:.3f}, "
                    f"sai số phép đo {spread*100:.2f}%, ngưỡng {min_drift*100:.1f}%); "
                    f"đã căn lại toạ độ berry/ball/flee theo máy này.", 0.0)

    def _ball_in(self, frame, *, strict: bool = False) -> tuple[int, int] | None:
        # Return the throw point only after the independent Berry-button detector proves that
        # the encounter UI is open.
        return self.config.ball_fallback if self._in_encounter(frame, strict=strict) else None

    def _ball_ready(self, frame) -> bool:
        """True when a throwable ball — *of any type* — is sitting at the throw start point.

        Only consulted while the encounter is known to be open, so the map's centre Poké Ball
        button can't be what we're seeing. During the flight/shake animation the ball has left
        that spot; it reappears there the moment the Pokémon breaks out, which is the cue to
        throw again immediately rather than waiting out ``catch_timeout``.

        Read at the ball's centre button rather than at its dome. Only the dome carries the
        ball type's colour, so testing it for red answered "no ball left" for a bag full of
        Great/Ultra/Master Balls — the routine then fled and sat out ``no_balls_pause`` with
        balls in hand. The centre button is identical on every type: a light, near-grey hub
        ringed by a thick black band. Requiring *both* — some black band and a light hub —
        is also what keeps flat scenery out: dark ground gives the band with no hub, and a
        pale sky or snow map gives the hub with no band.
        """
        cx, cy = self.config.ball_hub
        radius = max(8, self.config.ball_hub_radius)
        patch = frame[max(0, cy - radius):cy + radius,
                      max(0, cx - radius):cx + radius]
        if patch.size == 0:
            return False
        p = patch.astype(int)
        hi, lo = p.max(axis=2), p.min(axis=2)
        band = float((hi < 80).mean())                      # black ring around the hub
        hub = float(((lo > 140) & (hi - lo < 45)).mean())    # the light grey hub itself
        # Measured on a real encounter: band 0.26-0.38 and hub 0.33-0.53 across +/-25px of
        # placement error, several radii and three device scales. The bounds sit well outside
        # that, since the cost of reading a present ball as absent is a ten-minute pause.
        return 0.10 <= band <= 0.70 and hub >= 0.18

    def _is_out_of_balls(self, frame) -> bool:
        """True when the encounter's ball-count badge reads 'x0' (the red pill at the bottom
        centre) — i.e. we have no Poké Balls left. Colour match so it can't be confused with a
        neutral non-zero count."""
        if self._noball_tpl is None:
            return False
        matches = find(frame, self._noball_tpl, threshold=self.config.out_of_balls_threshold,
                       scales=self._scales, grayscale=False, region=self.config.out_of_balls_region)
        return bool(matches)

    def _ball_selector_present(self, frame) -> bool:
        """Whether the fixed bottom-right ball-selector control is visible.

        The large centre ball is animated: it can be upside down, lifted above its resting
        point, or remain held when a lossy Wi-Fi control packet drops a pointer-up. This control
        tells us when releasing stale pointers may restore that ball, but it is not inventory
        proof: the live empty-bag screen keeps drawing the same selector button.
        """
        cfg = self.config
        # This control is drawn by the game engine, whose default scale follows screen width,
        # not PGSharp's density-based overlay scale. Once measured, game_scale is definitive.
        scale = cfg.game_scale or (frame.shape[1] / BASE_RESOLUTION[0])
        return find_enc_ball(frame, scale=scale) is not None

    def _wait_for_ball_state(self, timeout: float) -> str:
        """Return ``ready``, ``closed`` or ``empty`` for the current encounter.

        Pokemon GO used to leave an ``x0`` count badge behind when the last ball was spent. In
        current builds the complete ball selector disappears, so the absence itself has to be
        read. Absence is only trusted while the independent Berry detector keeps proving the
        encounter is open, and only after both a time window and multiple frames. That keeps a
        slow selector animation (or one smeared stream frame) from becoming a false empty-bag
        alert.
        """
        cfg = self.config
        deadline = time.monotonic() + max(0.0, timeout)
        missing_frames = 0
        pointers_released = False
        while not self.stop_event.is_set():
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            if not self._in_encounter(frame, strict=True):
                return "closed"
            if self._is_out_of_balls(frame):
                return "empty"
            if self._ball_ready(frame):
                # The actual throwable ball is the only positive inventory signal. The live
                # empty-bag UI still draws the bottom-right Poké Ball selector, so treating that
                # button as proof of stock caused endless phantom throws at a bare throw point.
                return "ready"
            missing_frames += 1
            selector_present = self._ball_selector_present(frame)
            if selector_present and not pointers_released:
                # A lossy Quick Catch contact can leave a real ball held/rotated away from its
                # resting hub. Release all pointers once and keep waiting for the hub to return;
                # the selector by itself is never accepted as a throwable ball.
                release = getattr(self.device, "release_control_pointers", None)
                if release is not None:
                    release()
                pointers_released = True
            if (time.monotonic() >= deadline
                    and missing_frames >= max(1, cfg.no_balls_missing_frames)):
                # The consequence of a false positive is a ten-minute pause, so pay for one
                # compression-free ADB capture before committing. Several adjacent H.264 frames
                # can share the same smear; a fresh image cannot.
                fresh = self.device.screenshot(fresh=True)
                if not self._in_encounter(fresh, strict=True):
                    return "closed"
                if self._is_out_of_balls(fresh):
                    return "empty"
                return "ready" if self._ball_ready(fresh) else "empty"
        return "closed"

    def _flag_no_balls(self) -> None:
        """Reliably leave the empty encounter, then hand refill work to ``run``."""
        self._no_balls = True
        self.stats.last_event = "no_balls"
        release = getattr(self.device, "release_control_pointers", None)
        if release is not None:
            release()
        # Keep this tap independent from the scrcpy socket that may have retained a throw
        # pointer. Verify the state change instead of assuming a delivered tap was accepted.
        tap = getattr(self.device, "adb_tap", None) or self.device.tap
        tap(*self.config.flee_xy)
        left = self._poll(
            lambda frame: True if not self._in_encounter(frame, strict=True) else None,
            2.0,
        )
        if left is None and not self.stop_event.is_set():
            # Android Back is a safe independent fallback for the encounter screen.
            back = getattr(self.device, "back", None)
            if back is not None:
                back()
                left = self._poll(
                    lambda frame: True if not self._in_encounter(frame, strict=True) else None,
                    2.0,
                )
        self._trace(
            "no_balls",
            ("Không có bóng thật tại điểm ném; đã xác nhận hết Poké Ball và về bản đồ."
             if left is not None else
             "Không có bóng thật tại điểm ném; đã xác nhận hết Poké Ball, đang tiếp tục tìm cách thoát encounter."),
            0.0,
        )

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
        slot = self._effective_nearby_slot() if cfg.force_slot else self._slot_in(frame)
        if slot is None:
            return None
        # The manually calibrated point is already expressed in native screen pixels.
        # Keep its inspection window tight as well: scaling 70x110 once more on a
        # high-resolution phone dilutes a small/dark sprite with adjacent sidebar rows.
        half_width = 70 if cfg.force_slot else cfg.s(70)
        height = 110 if cfg.force_slot else cfg.s(110)

        if slot_has_pokemon(
                frame, slot, half_width=half_width, height=height,
                min_foreground_bright_fraction=cfg.slot_foreground_bright_fraction):
            return slot
        if cfg.force_slot:
            # Step off slots at the measured pitch, stopping above the '@' that ends the bar.
            bottom = self._force_bar_bottom(frame, slot)
            for n in range(1, max(0, cfg.force_slot_count) + 1):
                y = slot[1] + n * cfg.slot_pitch
                if y > bottom or y >= frame.shape[0]:
                    break
                if slot_has_pokemon(
                        frame, (slot[0], y), half_width=half_width, height=height,
                        min_foreground_bright_fraction=cfg.slot_foreground_bright_fraction):
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
            if slot_has_pokemon(
                    frame, (slot[0], y), half_width=half_width, height=height,
                    min_foreground_bright_fraction=cfg.slot_foreground_bright_fraction):
                self._trace("nearby_infer_top",
                            f"Đọc được Pokémon ở slot dưới (y={y}); danh sách không có chỗ "
                            f"trống nên tap slot đầu {slot}.")
                return slot
            y += step
        return None

    def _slot_visual_signature(self, frame, slot: tuple[int, int]) -> np.ndarray | None:
        """Shift-tolerant colour fingerprint of the sprite in one Nearby slot.

        Comparing raw pixels is much too sensitive to H.264 noise and the animated map showing
        through PGSharp's translucent sidebar. A coarse colour histogram of bright foreground
        pixels stays stable while the same sprite bobs, but changes when the list advances to a
        different Pokémon. An identical next species simply takes the conservative timeout.
        """
        if not isinstance(frame, np.ndarray) or frame.ndim != 3:
            return None
        cfg = self.config
        force_slot = bool(getattr(cfg, "force_slot", False))
        half_width = 70 if force_slot else cfg.s(70)
        height = 110 if force_slot else cfg.s(110)
        cx, cy = slot
        # Use the detector's central core, excluding most of the translucent background.
        x_radius = max(8, half_width // 2)
        y_radius = max(8, height // 3)
        y0, y1 = max(0, cy - y_radius), min(frame.shape[0], cy + y_radius)
        x0, x1 = max(0, cx - x_radius), min(frame.shape[1], cx + x_radius)
        patch = frame[y0:y1, x0:x1]
        if patch.size == 0:
            return None
        pixels = patch.reshape(-1, 3)
        bright = pixels[pixels.max(axis=1) >= 175]
        if len(bright) < 12:
            return None
        bins = np.clip(bright.astype(np.int16) // 64, 0, 3)
        indexes = bins[:, 0] * 16 + bins[:, 1] * 4 + bins[:, 2]
        histogram = np.bincount(indexes, minlength=64).astype(np.float32)
        histogram /= histogram.sum()
        return histogram

    @staticmethod
    def _slot_signature_changed(before: np.ndarray, after: np.ndarray) -> bool:
        return bool(np.abs(before - after).sum() >= SLOT_REFRESH_HIST_DISTANCE)

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
        bar = self._ui_nearby_bar(state)
        if bar:
            self._remember_ui_nearby_slot(bar[0])
        # Every dump refreshes the cooldown for free, whatever it was taken for.
        self._note_cooldown(state.cooldown)
        return state

    def _ui_nearby_bar(self, state) -> list[tuple[int, int]] | None:
        """The *Nearby* bar's occupied slots out of a dump, top entry first.

        An empty list and None are different answers: [] is PGSharp stating that the Nearby bar
        holds nothing, which is as authoritative as a hit and lets the caller skip the crisp
        re-capture. None is this method declining to say which column is Nearby at all, where
        the pixels still have to be asked.

        PGSharp builds its Nearby sidebar and its Feeds sidebar from the same list widget, so
        both report `hl_sri_icon` and a dump holds two interleaved bars rather than one list.
        Reading them as one and taking the topmost entry picks whichever bar happens to hang
        higher on screen — the Feed bar as often as not. That is what put a Feed coordinate
        into _remember_ui_nearby_slot, overriding the user's calibration, and left the bot
        double-tapping Feeds every cycle with Pokémon sitting on a full Nearby bar.

        Nothing in the view tree names the bars, so the column does it: the '@' anchor marks
        the Nearby bar and nothing else, with the calibrated point and the column already
        accepted this session as fallbacks. With no reference at all a lone bar is
        unambiguous and is used; two are not, and no answer beats a coin flip that teleports.
        """
        bars = getattr(state, "bars", None) or ([state.nearby] if state.nearby else [])
        if not bars:
            # No sidebar entries anywhere in the tree. Neither bar is holding anything, so
            # Nearby is empty whichever column it occupies.
            return []
        anchor = self._anchor_cache
        ui_slot = getattr(self, "_ui_nearby_slot", None)
        if anchor is not None:
            ref = anchor[0]
        elif ui_slot is not None:
            ref = ui_slot[0]
        elif self.config.force_slot:
            ref = self.config.nearby_slot[0]
        else:
            return list(bars[0]) if len(bars) == 1 else None
        # Generous on purpose: the bars sit at opposite edges, hundreds of px apart, so a wide
        # window cannot confuse them, while a tight one would reject a calibration measured a
        # few px off the widget's own centre.
        bar = min(bars, key=lambda b: abs(b[0][0] - ref))
        if abs(bar[0][0] - ref) > self.config.handle_column_tol * 2:
            # Every bar in the tree sits in some other column, so the Nearby bar is not among
            # them. It is empty (an empty ListView contributes no icons), but say so only as
            # "cannot tell" — the reference itself may be the thing that is stale.
            return None
        if anchor is not None:
            # The '@' ends the Nearby bar, so an entry level with or below it belongs to
            # something else — the other bar, dragged into this same column.
            bar = [slot for slot in bar if slot[1] < anchor[1]]
        return list(bar)

    def _remember_ui_nearby_slot(self, target: tuple[int, int]) -> None:
        """Cache PGSharp's authoritative slot-1 centre over a stale manual calibration."""
        target = (int(target[0]), int(target[1]))
        old = getattr(self, "_ui_nearby_slot", None)
        self._ui_nearby_slot = target
        self._nearby_last_seen_at = time.monotonic()
        if not self.config.force_slot:
            return
        previous = old or self.config.nearby_slot
        if previous == target:
            return
        # Bounds derived from the old slot must not survive a moved/corrected bar.
        self._force_bottom_cache = None
        self._force_bottom_value = None
        self._trace(
            "nearby_ui_realign",
            f"PGSharp xác nhận slot đầu tại {target}; thay điểm căn tay cũ {previous} cho phiên này.",
            0.0,
        )

    def _effective_nearby_slot(self) -> tuple[int, int]:
        """Runtime slot centre, preferring PGSharp's live coordinate over saved calibration."""
        ui_slot = getattr(self, "_ui_nearby_slot", None)
        if self.config.force_slot and ui_slot is not None:
            return ui_slot
        return self.config.nearby_slot

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
        x, y = self._effective_nearby_slot()
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
        self._ui_empty_confirmed = False
        state = self._ui_state()
        if state is None:
            return None
        bar = self._ui_nearby_bar(state)
        if bar is None:
            return None
        if not bar:
            # Measured on this device: the dump costs ~2.8s and the crisp capture another
            # ~2.85s over Wi-Fi. Spending the second one to re-ask a question PGSharp's own
            # view tree just answered is most of a dry cycle thrown away.
            self._ui_empty_confirmed = True
            self._trace("nearby_ui_empty",
                        "PGSharp xác nhận thanh Nearby trống; bỏ qua bước chụp ảnh nét.", 0.0)
            return None
        target = bar[0]
        self._remember_ui_nearby_slot(target)
        self._trace("nearby_ui_hit",
                    f"PGSharp báo {len(bar)} Pokémon trên Nearby; tap slot đầu {target}.",
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
        self._feed_miss = "no_bar"
        if self._rss is None or self._handle is None:
            return None

        def occupied(slot: tuple[int, int]) -> tuple[int, int] | None:
            present = slot_has_pokemon(
                frame, slot, half_width=cfg.s(70), height=cfg.s(110),
                min_foreground_bright_fraction=cfg.slot_foreground_bright_fraction,
            )
            self._feed_presence_streak = self._feed_presence_streak + 1 if present else 0
            if not present:
                self._feed_miss = "empty"
                return None
            if self._feed_presence_streak < 2:
                self._feed_miss = "streak"
                return None
            self._feed_miss = None
            return slot

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
        if (not cfg.use_feed_bar or self._feed_pending or self._teleport_blocked
                or self._rss is None or self._handle is None):
            return False
        frame = self.device.screenshot(next_frame=True)
        # Only jump when the Nearby bar itself is on screen — that is what proves we are on the
        # map looking at an empty bar. Without its '@' in view we are somewhere else entirely
        # (an encounter, a summary, a dialog, a transition), and tapping a remembered feed
        # position there fires a teleport in the middle of a catch.
        if self._slot_in(frame) is None:
            self._trace(
                "feed_skip_map",
                "Bỏ qua Feed vòng này: không thấy mốc '@' của thanh Nearby trên khung hình "
                "(có thể đang ở encounter hoặc màn hình chuyển cảnh).",
                10.0,
            )
            return False
        slot = self._feed_slot_in(frame)
        if slot is None:
            # H.264 smear between keyframes routinely drops the small RSS/handle templates below
            # threshold, and this used to be gated on _feed_seen — which _feed_slot_in only sets
            # after a stream frame has already matched them. On a device where they never do,
            # that is a closed loop: the crisp capture that would prove the bar exists is the one
            # thing the gate forbids. It is now allowed to bootstrap, rate-limited so a user with
            # no feed bar open does not buy a capture every dry cycle.
            now = time.monotonic()
            if self._feed_seen or now - self._feed_fresh_at >= cfg.feed_fresh_cooldown:
                if not self._feed_seen:
                    self._feed_fresh_at = now
                slot = self._feed_slot_in(self.device.screenshot(fresh=True))
        if slot is None:
            self._trace(
                "feed_skip",
                "Bỏ qua Feed vòng này: " + {
                    "no_bar": "không tìm thấy thanh Feed trên màn hình "
                              "(icon RSS hoặc tay cầm không khớp mẫu).",
                    "empty": "thanh Feed đang không có Pokémon nào.",
                    "streak": "thanh Feed vừa hiện Pokémon, chờ thêm một khung hình để chắc.",
                }.get(self._feed_miss, "không đọc được thanh Feed."),
                10.0,
            )
            return False
        self.device.tap(*slot)
        # Lock before waiting. feed_teleport_wait is only a fast-path wait, never permission to
        # consume another Feed item when loading takes longer.
        self._feed_pending = True
        self._feed_pending_at = time.monotonic()
        self._trace(
            "feed_tap",
            f"Nearby trống; đã tap Feed đúng 1 lần tại {slot}. "
            "Khóa Feed tới khi Pokémon xuất hiện và bắt xong.",
            0.0,
        )
        # Teleporting far raises the speed warning; clear it, then remain inside this method
        # until the spawn really lands in Nearby. Returning to run_once after a short timeout
        # used to re-enter the empty-Nearby branch and could consume another Feed item.
        self._interruptible_sleep(min(0.75, cfg.feed_teleport_wait))
        self._cancelled_dialog = False
        self._drain_popups()
        if self._cancelled_dialog:
            # The teleport was refused (Go Plus warning answered with CANCEL), so this jump
            # never happened and the next one wouldn't either. Retrying would just loop
            # tap -> warning -> CANCEL forever, so drop the feed source for the rest of the
            # run and let Nearby + AutoWalk carry the flow.
            self._teleport_blocked = True
            self._feed_pending = False
            self._feed_pending_at = 0.0
            self._cancelled_dialog = False
            self._trace("feed_disabled",
                        "Teleport bị chặn (Go Plus đang kết nối) — tắt nguồn feed, "
                            "chỉ dùng Nearby + AutoWalk.", 0.0)
            return False

        loaded = None
        timed_out = False
        heartbeat_at = time.monotonic()
        deadline = (self._feed_pending_at + cfg.feed_nearby_timeout
                    if cfg.feed_nearby_timeout > 0 else None)
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            frame = self.device.screenshot(next_frame=True)
            if self._drain_popups(frame):
                if self._cancelled_dialog:
                    self._teleport_blocked = True
                    self._feed_pending = False
                    self._feed_pending_at = 0.0
                    self._cancelled_dialog = False
                    self._trace(
                        "feed_disabled",
                        "Teleport bị chặn (Go Plus đang kết nối) — tắt nguồn feed, "
                        "chỉ dùng Nearby + AutoWalk.",
                        0.0,
                    )
                    return False
                continue

            loaded = self._occupied_slot_in(frame)
            now = time.monotonic()
            if loaded is None and now - heartbeat_at >= 10.0:
                # Stream frames may smear a newly arrived sprite. Every heartbeat asks PGSharp
                # directly, then falls back to one crisp ADB frame before continuing to wait.
                loaded = self._occupied_slot_ui()
                if loaded is None and not self._ui_empty_confirmed:
                    loaded = self._occupied_slot_fresh()
                if loaded is None:
                    waited = max(0.0, now - self._feed_pending_at)
                    self._trace(
                        "feed_wait_nearby",
                        f"Đã tap Feed 1 lần; vẫn chờ Pokémon hiện trên Nearby ({waited:.0f}s). "
                        "Không teleport tiếp.",
                        0.0,
                    )
                    heartbeat_at = now
            if loaded is None and deadline is not None and now >= deadline:
                timed_out = True
                break
            if loaded is not None:
                waited = max(0.0, time.monotonic() - self._feed_pending_at)
                self._trace(
                    "feed_nearby_ready",
                    f"Pokémon từ Feed đã hiện trên Nearby tại {loaded} sau {waited:.1f}s; "
                    "chuyển sang bắt.",
                    0.0,
                )
                break
            self._interruptible_sleep(max(0.06, cfg.idle_poll))

        if timed_out:
            waited = max(0.0, time.monotonic() - self._feed_pending_at)
            self._feed_pending = False
            self._feed_pending_at = 0.0
            self._trace(
                "feed_timeout",
                f"Đã tap Feed nhưng Pokémon không hiện trên Nearby sau {waited:.0f}s "
                "(có thể cú tap bị bỏ qua hoặc Pokémon đã biến mất); "
                "bỏ qua con này, quay lại Nearby + AutoWalk.",
                0.0,
            )
            return False
        if loaded is None:
            # User pressed Stop. Keep the pending bit truthful until this routine is discarded;
            # most importantly, never turn a stop into permission for one more Feed tap.
            return False

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

    def _finish_encounter(self, ball_xy: tuple[int, int]) -> bool:
        """Run an encounter and release a pending Feed item only after it was handled."""
        threw = self._run_encounter(ball_xy)
        if threw and self._feed_pending:
            waited = max(0.0, time.monotonic() - self._feed_pending_at)
            self._feed_pending = False
            self._feed_pending_at = 0.0
            self._trace(
                "feed_complete",
                f"Đã xử lý xong Pokémon từ Nearby sau {waited:.1f}s; mở khóa Feed kế tiếp.",
                0.0,
            )
        return threw

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
                     scales=self._popup_scales, grayscale=False,
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

        # Medal/share screens have a real close X at the bottom, but their green SHARE button
        # is visually close enough to the weather warning's "I AM SAFE" pill to score just over
        # the generic 0.70 threshold. Take a high-confidence X before inspecting green action
        # buttons so the safe close always wins over SHARE/SAVE IMAGE.
        if self._ball_in(frame) is None:
            close = find_popup_close(
                frame,
                (self._close_btn, self._close_btn_blue, self._close_btn_white),
                threshold=max(0.82, self.config.popup_threshold),
                scales=self._game_popup_scales,
                fallback_scales=CALIBRATION_SWEEP,
                cache=fast_cache,
            )
            if close is not None:
                self.device.tap(*close.center)
                self.stats.last_event = "popup"
                return True

        # Weather warning "Weather conditions are potentially dangerous" -> tap the green
        # "I AM SAFE" button to dismiss it (it's a full modal that blocks the whole flow).
        if self._popup_weather is not None:
            m = find_fast(frame, self._popup_weather,
                          threshold=max(0.82, self.config.popup_threshold),
                          scales=self._game_popup_scales, cache=fast_cache)
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True

        # Speed warning "You're going too fast" -> tap the green "I'M A PASSENGER" button.
        # Popups render at a fixed size on a given device, so a single scale is enough.
        if self._popup_speed is not None:
            m = find_fast(frame, self._popup_speed, threshold=self.config.popup_threshold,
                          scales=self._game_popup_scales, cache=fast_cache)
            if m:
                x, y = m[0].center
                self.device.tap(x, y)
                self.stats.last_event = "popup"
                return True
        # "WEEKLY CHALLENGE"/invite modal -> tap its white "MAYBE LATER" text to dismiss (never the
        # green "CHOOSE GROUP" above it). Searched by text in a centre box, so the button is missed.
        if self._maybe_later is not None:
            m = find_fast(frame, self._maybe_later, threshold=self.config.popup_threshold,
                          scales=self._game_popup_scales, grayscale=False,
                          region=self.config.maybe_later_region)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # "Stop/Pause AutoWalk?" dialog -> tap CANCEL to dismiss it.
        if self._popup_autowalk is not None:
            m = find_fast(frame, self._popup_autowalk, threshold=self.config.popup_threshold,
                          scales=self._popup_scales, cache=fast_cache)
            if m:
                # Aim at the CANCEL word itself when it can be read: the offset below is only
                # true for the device the dialog was measured on. Searched inside the dialog's
                # own box, so this can't pick up a CANCEL belonging to something else.
                target = None
                if self._cancel_btn is not None:
                    box = (m[0].x - self.config.s(60), m[0].y,
                           m[0].width + self.config.s(500), m[0].height + self.config.s(360))
                    hit = find(frame, self._cancel_btn, threshold=self.config.popup_threshold,
                               scales=self._popup_scales, grayscale=False, region=box,
                               max_matches=1)
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
            # used for calibration (MuMu: claim ~=0.67, menu star ~=0.55) — hence the wide
            # sweep, which _claim_scales keeps for exactly the devices that showed it.
            m = find_fast(frame, self._claim_rewards, threshold=self.config.popup_threshold,
                          scales=self._claim_scales, cache=fast_cache)
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
                            m_close = find_fast(f, btn, threshold=0.7,
                                                scales=self._game_popup_scales,
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
                    m = find_fast(frame, btn, threshold=0.7, scales=self._game_popup_scales,
                                  region=region)
                    if m:
                        close = m[0].center
                        break
            # The screen itself was identified structurally from the blue photo-disc; once that
            # proof exists, the calibrated close point is safer than leaving a user stuck just
            # because this game version changed the X artwork.
            self.device.tap(*(close or (fx, fy)))
            self.stats.last_event = "popup"
            return True
        # "POKÉMON CAUGHT" XP summary (a slipped-through catch) -> tap its green OK pill. It shows
        # first, and its ball-selector bleeds through the dialog so the encounter check reads true;
        # handle it here before anything else touches the screen.
        if self._caught_ok is not None:
            m = find_fast(frame, self._caught_ok, threshold=0.72,
                          scales=self._game_popup_scales,
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
            m = find_fast(frame, self._check_btn, threshold=0.75,
                          scales=self._game_popup_scales,
                          grayscale=False, region=self.config.check_btn_region)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # The high-confidence X search at the start is the only generic close-button path.
        # A second pass at 0.70 used to match animated map art and create unexplained taps.
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

    def _star_in(self, frame) -> tuple[int, int] | None:
        """The PGSharp menu star, searched near where it was last seen before the whole frame.

        Same cache-then-widen shape as _slot_in uses for the '@'. It matters more here: the star
        is matched in colour over the *full* frame at several scales, which measured 0.6-0.9s on
        a 1220x2712 device — and _paused_row_in asks for it on every empty Nearby cycle, so that
        was being paid whenever there was nothing to catch. The menu only moves when the user
        drags it, so the cached box answers almost every call for ~10ms; a miss falls back to the
        full search and re-learns, exactly as before.
        """
        cfg = self.config
        if self._star is None:
            return None
        if self._star_cache is not None:
            cx, cy = self._star_cache
            r = cfg.s(cfg.star_cache_radius)
            m = find(frame, self._star, threshold=cfg.menu_star_threshold, scales=self._scales,
                     grayscale=False, region=(cx - r, cy - r, r * 2, r * 2), max_matches=1)
            if m:
                self._star_cache = m[0].center
                return self._star_cache
        m = find(frame, self._star, threshold=cfg.menu_star_threshold, scales=self._scales,
                 grayscale=False, max_matches=1)
        self._star_cache = m[0].center if m else None
        return self._star_cache

    def _ensure_menu_open(self, frame) -> bool:
        """Expand the PGSharp menu when only its star is showing. True if it was tapped.

        Read from the Settings gear, the menu's last row: the star renders whether the menu is
        open or shut, so it cannot answer this on its own. A gear in view means open, and this
        does nothing — which is the usual case, since the menu is normally left expanded.

        Only reached on an empty-Nearby cycle, where the menu is about to be needed anyway. That
        is also the only place a collapsed menu shows itself: with the rows hidden, AutoWalk,
        Feeds and Teleport are all unreachable and the bot would sit idle in front of an overlay
        that is working fine.
        """
        cfg = self.config
        if self._gear is None or self._star is None:
            return False
        star = self._star_in(frame)
        if star is None:
            return False            # no overlay on screen at all; nothing to open
        sx, sy = star
        # The rows hang below the star, in its column. Taller than _paused_row_in's box: the gear
        # is the last row, not the third (see menu_gear_span).
        region = (sx - cfg.s(150), sy, cfg.s(300), cfg.s(cfg.menu_gear_span))
        if find(frame, self._gear, threshold=cfg.pgsharp_menu_threshold, scales=self._scales,
                grayscale=False, region=region, max_matches=1):
            return False            # already expanded
        self.device.tap(sx, sy)
        self._trace("menu_collapsed",
                    f"Menu PGSharp đang thu gọn; bấm ngôi sao tại {star} để mở.", 0.0)
        return True

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
        star = self._star_in(frame)
        if star is None:
            return None
        sx, sy = star
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
        star = self._star_in(frame)

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

        if paused is False:
            # The visible running-row icon is stronger evidence than the remembered flag. In
            # particular _wait_no_balls intentionally clears that flag after fleeing; tapping a
            # row that is already running would stop AutoWalk instead of starting it.
            self._autowalk_active = True
            self._trace("autowalk_already_running", "AutoWalk đã chạy; không bấm lại.", 0.0)
            return False
        if self._autowalk_active and paused is not True:
            # Already walking, and nothing says the row stalled — leave it alone.
            return False
        self.device.tap(*target)
        return True

    def _try_start_goplus(self) -> bool:
        """Tap Go Plus once, but only while its disconnected button is visibly present."""
        frame = self.device.screenshot(fresh=True)
        if self._in_encounter(frame):
            self._trace("goplus_skip_encounter", "Đang trong encounter; không bấm Go Plus.", 0.0)
            return False
        game_scale = Layout(*self.config.screen, scale=self.config.game_scale).s
        target = find_disconnected_goplus(frame, scale=game_scale)
        if target is None:
            self._trace(
                "goplus_not_disconnected",
                "Không thấy nút Go Plus ở trạng thái tắt; không bấm để tránh ngắt kết nối đang chạy.",
                0.0,
            )
            return False
        self.device.tap(*target)
        self._trace("goplus_start", f"Đã bấm khởi động Go Plus tại {target}.", 0.0)
        return True

    # -- PokéStop spinning -----------------------------------------------------------
    def _spin_recent(self, x: int, y: int) -> bool:
        """True if this spot was tapped recently enough to be worth skipping."""
        cfg = self.config
        now = time.monotonic()
        self._spin_seen = [s for s in self._spin_seen if now - s[0] < cfg.spin_skip_seconds]
        r = cfg.spin_skip_radius
        return any(abs(px - x) <= r and abs(py - y) <= r for _t, px, py in self._spin_seen)

    def find_stops(self, frame):
        """Unspun PokéStops inside the scan circle, nearest to the avatar first."""
        cfg = self.config
        return find_pokestops(
            frame,
            region=cfg.spin_region,
            scale=Layout(*cfg.screen, scale=cfg.game_scale).s,
            min_area=cfg.spin_min_area,
        )

    def spin_once(self, frame=None) -> bool:
        """Tap the nearest unspun PokéStop in the scan circle. True if one was tapped.

        The tap is not the end of it: PGSharp answers *every* touch that reaches the map with
        its "Tap to Walk/Teleport — Stop AutoWalk?" dialog, which is modal and blocks the next
        cycle until it is answered (always CANCEL — OK would teleport and stop the walk). If the
        stop opened its photo-disc screen instead of spinning on the spot, the same sweep closes
        that. Both live in _handle_popups already, so this only has to give them a turn.
        """
        cfg = self.config
        if frame is None:
            frame = self.device.screenshot()
        target = next((m for m in self.find_stops(frame)
                       if not self._spin_recent(*m.center)), None)
        if target is None:
            # Silent: the caller already reports its own empty cycle, and a detector trace
            # saying the same thing in different words reads as two separate problems.
            return False
        x, y = target.center
        self.device.tap(x, y)
        self._spin_seen.append((time.monotonic(), x, y))
        self.stats.spins += 1
        self._trace("spin_tap", f"Bấm PokéStop tại ({x},{y}), ô {target.width}x{target.height}.", 0.0)
        self._interruptible_sleep(cfg.spin_settle)
        self._drain_popups()
        return True

    def _spin_for(self, seconds: float) -> None:
        """Spend `seconds` tapping stops, one every spin_interval."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                return
            frame = self.device.screenshot()
            if not self._drain_popups(frame):
                self.spin_once(frame)
            self._interruptible_sleep(self.config.spin_interval)

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
        goplus_started = not (cfg.start_goplus_on_no_balls and not cfg.quick_catch)
        while time.monotonic() < deadline and not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                return
            self._drain_popups()
            if self._try_autowalk():
                self._autowalk_active = True
            # Try until the disconnected button is actually found and tapped. The detector never
            # returns a connected green button, so retries cannot disconnect an active Go Plus;
            # they only recover from the menu/button not being ready on the first frame.
            if self._autowalk_active and not goplus_started:
                self._interruptible_sleep(cfg.goplus_after_autowalk_wait)
                started = self._try_start_goplus()
                goplus_started = started
                if started and on_event:
                    self.stats.last_event = "goplus_started"
                    on_event(self.stats, False)
            remaining = max(0.0, deadline - time.monotonic())
            refill_mode = "AutoWalk + Go Plus" if cfg.start_goplus_on_no_balls else "AutoWalk"
            if cfg.spin_on_no_balls:
                refill_mode += " + quay stop trên màn"
            self._trace(
                "no_balls_refill",
                f"Đang nạp bóng bằng {refill_mode}; còn tối đa {remaining / 60:.1f} phút trước khi thử bắt lại.",
                60.0,
            )
            # Spinning stops is what actually refills the bag, so spend the interval doing it
            # rather than standing still. Works with or without a PGSharp key, unlike Go Plus.
            if cfg.spin_on_no_balls:
                self._spin_for(cfg.no_balls_walk_interval)
            else:
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

    def _engage_nearby(self, slot: tuple[int, int]) -> None:
        """Prime a Nearby row, then send the double-tap that opens its encounter."""
        cfg = self.config
        self._engaged_slot_signature = None
        screenshot = getattr(self.device, "screenshot", None)
        if screenshot is not None:
            self._engaged_slot_signature = self._slot_visual_signature(screenshot(), slot)
        self.device.tap(*self._jitter(*slot))
        delay = max(cfg.pre_tap_min_delay, cfg.pre_tap_delay)
        self._trace("nearby_pre_tap",
                    f"Tap mở đầu tại {slot}; chờ {delay:.2f}s rồi double-tap.", 0.0)
        self._interruptible_sleep(delay)
        if not self.stop_event.is_set():
            self._double_tap(*slot)

    def _wait_for_engaged_encounter(self) -> tuple[int, int] | None:
        """Poll the cheap video stream until the just-tapped encounter is actually ready.

        A UI hierarchy dump made the common path 2-3 seconds slower than the game itself.  The
        Berry detector already supplies the exact state needed here, and this poll returns on its
        first positive frame; the combined timeout is only a ceiling for genuinely slow opens.
        """
        cfg = self.config
        timeout = max(0.0, cfg.encounter_timeout) + max(0.0, cfg.encounter_transition_grace)
        started = time.monotonic()
        deadline = started + timeout
        self._engage_still_nearby = False
        while not self.stop_event.is_set():
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            ball = self._ball_in(frame)
            if ball is not None:
                return ball

            now = time.monotonic()
            if now >= deadline:
                # Do not retry from an early Nearby frame. On the live phone the game can accept
                # the touch immediately yet leave the row rendered for another 2-3 seconds; a
                # second gesture then lands on the map/transition and raises a PGSharp dialog.
                # Consume the entire configured encounter budget first, then take exactly one
                # direct screencap outside the H.264 queue as the final verdict.
                fresh = self.device.screenshot(fresh=True)
                ball = self._ball_in(fresh)
                if ball is not None:
                    return ball
                self._engage_still_nearby = (
                    self._bar_visible(fresh) and self._scan_slots(fresh) is not None
                )
                return None
        return None

    def _settle_after_encounter(self) -> None:
        """Wait only until PGSharp visibly replaces the consumed Nearby row.

        A blind zero-delay retry targeted the stale row and lost roughly six seconds, while a
        fixed 1.2-second sleep made every healthy catch unnecessarily slow. Keep a 250ms
        transition floor, then accept two fresh frames showing either an empty bar or a sprite
        fingerprint different from the one just engaged. Unreadable/identical rows use the
        configured value as a conservative maximum.
        """
        cfg = self.config
        self._nearby_last_seen_at = None
        started = time.monotonic()
        timeout = max(MIN_POST_CATCH_REFRESH, cfg.settle_after_catch)
        deadline = started + timeout
        if self.stop_event.is_set():
            return
        self._interruptible_sleep(MIN_POST_CATCH_REFRESH)
        previous = getattr(self, "_engaged_slot_signature", None)
        refreshed_frames = 0
        refreshed = False
        while previous is not None and not self.stop_event.is_set() and time.monotonic() < deadline:
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            changed = False
            if self._bar_visible(frame):
                slot = self._scan_slots(frame)
                if slot is None:
                    changed = True
                else:
                    current = self._slot_visual_signature(frame, slot)
                    changed = current is not None and self._slot_signature_changed(previous, current)
            refreshed_frames = refreshed_frames + 1 if changed else 0
            if refreshed_frames >= 2:
                refreshed = True
                break
        if previous is None and not self.stop_event.is_set():
            # A UI-dump-only engagement may not have yielded a pixel fingerprint. Preserve the
            # safe fallback without penalising the normal image-detected path.
            remaining = deadline - time.monotonic()
            if remaining > 0:
                self._interruptible_sleep(remaining)
        elapsed = max(0.0, time.monotonic() - started)
        self._engaged_slot_signature = None
        self._trace(
            "settle_refresh",
            (f"Nearby đã đổi slot sau {elapsed:.2f}s; bắt con kế tiếp ngay."
             if refreshed else
             f"Chờ Nearby tối đa {elapsed:.2f}s; vòng kế tiếp xác nhận lại trên 2 frame mới."),
            5.0,
        )

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
            ball_ready = self._ball_ready(frame)
            if not ball_ready:
                ball_left = True
            elif ball_left:
                # The same tested hub that gates the initial throw has returned after being
                # absent, which is the breakout cue. The selector is deliberately irrelevant:
                # the current empty-bag UI leaves that button visible too.
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
            # Wait for the actual ball on every attempt. The old code only waited before the
            # first throw and then threw at the fallback coordinate even when the last ball had
            # just disappeared. _wait_for_ball_state also supports the new no-selector empty-bag
            # UI, while returning immediately as soon as a normal ball is visible.
            ready_wait = max(
                cfg.encounter_touch_delay_ms / 1000.0,
                cfg.no_balls_missing_timeout,
            )
            ball_state = self._wait_for_ball_state(ready_wait)
            if ball_state == "empty":
                self._flag_no_balls()
                return threw
            if ball_state == "closed":
                closed = True
                return threw
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
        # A one-throw limit can spend the final ball and time out before there is another loop
        # iteration to observe the missing selector. Confirm once before the ordinary give-up
        # flee so that configuration still reports and pauses on an empty bag.
        if not closed and threw and not self.stop_event.is_set():
            ball_state = self._wait_for_ball_state(cfg.no_balls_missing_timeout)
            if ball_state == "empty":
                self._flag_no_balls()
                return threw
            if ball_state == "closed":
                closed = True
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
            # Keep the low-latency control channel warm for the next Pokemon. Rebuilding the
            # scrcpy server over Wi-Fi before every tap cost 1-5 seconds. Duplicate pointer-UPs
            # clear the stale-touch failure that the old full teardown protected against; the
            # device method still closes the channel if that reset itself fails.
            release_pointers = getattr(self.device, "release_control_pointers", None)
            if release_pointers is not None:
                release_pointers()
        self._settle_after_encounter()
        return threw

    # Derived, not chosen: the measurement is a point on a grid of CAL_REFINE_STEP, so a gap
    # smaller than the grid is rounding and nothing else. Two grid steps is the smallest gap
    # that cannot be rounding on either side. Writing it as a multiple keeps the rule true when
    # the grid changes — a hand-typed number silently stopped being true when _refine_scale
    # narrowed the grid from 0.05 to 0.01, which is exactly the failure this avoids.
    #
    # Absolute rather than proportional, because the grid is absolute: as a percentage one step
    # is 0.9% at s≈1.1 but 1.8% at s≈0.55, so any fixed percentage sits above the grid at one
    # scale and below it at the other, and chases quantisation noise there.
    #
    # Measured, all correctly left alone:
    #   810x1440@270 MuMu     guess 0.5625   refined 0.57  (anchor, star and gear agreed)
    #   1220x2712@480         guess 1.0000   measured 1.00
    #   1280x2772@520 phone   guess 1.0833   coarse   1.10
    # Against the case this exists for — 1080x2400 reporting 480dpi — the gap is 0.115, and a
    # Nearby slot lands most of a slot away.
    CAL_REFINE_STEP = 0.01          # spacing of the fine pass; see _refine_scale
    RESCALE_MIN_STEP = 2 * CAL_REFINE_STEP

    def _adopt_measured_scale(self, scale: float) -> None:
        """Re-derive the config's coordinates at the render scale just measured.

        Until now this measurement only resized the *templates*, so detection self-corrected on
        a device the density guess got wrong while every fixed coordinate stayed where the guess
        put it — search regions, the first Nearby slot, the flee button. That is the failure that
        never shows up on the machine the coordinates were authored on, because there the guess
        and the measurement are both 1.0 and there is nothing to disagree about.

        Manual alignment still wins: `_on_rescale` hands the fresh config back to whoever applied
        the hand-aligned device pixels, so a user who has already corrected a point by hand does
        not have it overwritten by a measurement.
        """
        current = self.config.layout.s
        if not current or abs(scale - current) < self.RESCALE_MIN_STEP:
            return
        try:
            rescaled = self.config.rescale(scale)
        except Exception:  # noqa: BLE001 - a bad re-derive must not end the run
            return
        hook = getattr(self, "_on_rescale", None)
        if hook is not None:
            try:
                rescaled = hook(rescaled) or rescaled
            except Exception:  # noqa: BLE001
                pass
        self.config = rescaled
        self._trace("scale_fixed",
                    f"Đo được scale màn hình {scale:.2f} (đoán ban đầu {current:.2f}); "
                    f"đã căn lại toạ độ theo máy này.", 0.0)

    def _ensure_calibrated(self) -> None:
        """Measure how big the UI actually renders on this device (once), from the always-on
        PGSharp menu star, and centre the match-scale sweep on it. This sidesteps guessing the
        scale from resolution/density — which is unreliable because the game doesn't re-layout
        cleanly. Until it locks, the wide bracket set in __init__ stays in effect, so detection
        keeps working; a hidden/covered star just leaves it to retry next cycle.

        The retries are capped, because the sweep is by far the most expensive thing in the whole
        routine: 17 scales of a colour template match over the full frame, measured at 2.7s on a
        1220x2712 device. The docstring above always promised "once", but nothing enforced it —
        so a star that never reaches CALIBRATION_MIN_SCORE (menu collapsed, covered, or simply drawn differently by
        this PGSharp build) charged that 2.7s to *every cycle, forever*, which is the single
        largest slowdown there is and one that no setting could switch off.

        Giving up is safe precisely because the failure is already handled: not locking just
        leaves the wide bracket in place, which is the documented fallback. So after a few
        attempts, stop paying for an answer this device is not going to give."""
        if self._cal_scale is not None:
            return
        if self._cal_attempts >= self.config.cal_max_attempts:
            return
        self._cal_attempts += 1
        s, score, source, agreed = self._measure_render_scale()
        if s is not None and score >= CALIBRATION_MIN_SCORE:
            self._cal_scale = s
            self._scales = scales_around(s)
            self._popup_scales = (
                (1.0,) if abs(s - 1.0) < 1e-3 else scales_around(s)
            )
            # Centring the template sweep is worth doing on any measurement; moving every
            # coordinate is only worth doing on one the sources back each other up on.
            if agreed:
                self._adopt_measured_scale(s)
        elif self._cal_attempts >= self.config.cal_max_attempts:
            self._trace("calib_giveup",
                        f"Không đo được scale sau {self._cal_attempts} lần "
                        f"(điểm cao nhất {score:.2f} < {CALIBRATION_MIN_SCORE} ở '{source}'); "
                        f"dùng dải scale rộng mặc định — toạ độ vẫn theo dpi ước lượng.",
                        0.0)

    # Icons to measure the render scale from, best first. All three are drawn by PGSharp as
    # native Android views, so they share one scale; the list exists because any single one can
    # be absent or drawn differently by another PGSharp build, and giving up then left every
    # coordinate on the density guess for the whole run.
    #
    # Order is by measured reliability on the authoring device across five real frames: the
    # Nearby '@' anchor locked at 1.00 every time (score 0.91-0.94 at the reduction used here)
    # while the menu star, the only source this used to have, wandered to 1.05 on one of them.
    CAL_SOURCES: tuple[str, ...] = ("_anchor", "_star", "_gear")
    # Both scene and template are halved for the sweep. Measured: 3.7s -> 0.93s per source with
    # the answer unchanged, which is what makes trying three sources cheaper than one used to be.
    CAL_REDUCTION = 0.5

    def _measure_render_scale(self) -> tuple[float | None, float, str, bool]:
        """Measure the UI render scale from every known icon on screen, and say whether they agree.

        Returns (scale, score, source, trustworthy). Taking the first source that cleared the
        threshold was wrong, and a real phone showed why: on a 1280x2772@520 screen the three
        sources peaked at 1.10, 1.04 and 1.07 with score curves flat to within 0.04 across that
        whole span — so whichever was asked first became the answer, and the spread between them
        was 6%. The density estimate (1.0833) sits in the middle of that scatter, which is the
        honest reading: this device cannot be measured more precisely than it was guessed.

        On MuMu the same three sources all returned 0.57. Nothing in a single reading tells those
        two situations apart, which is the whole problem — so the sources are cross-checked, and
        `trustworthy` is False when they disagree by more than the grid can explain.

        A disagreeing measurement still centres the template sweep (better than the wide
        bracket), it just may not move any coordinate.
        """
        frame = self.device.screenshot()
        best: tuple[float | None, float, str] = (None, 0.0, "khong co")
        readings: list[tuple[float, float, str]] = []
        for name in self.CAL_SOURCES:
            template = getattr(self, name, None)
            if template is None:
                continue
            s, score = best_matching_scale(frame, template, CALIBRATION_SWEEP,
                                           grayscale=False, reduction=self.CAL_REDUCTION)
            if s is not None and score >= CALIBRATION_MIN_SCORE:
                s, score = self._refine_scale(frame, template, s, score)
                readings.append((s, score, name.lstrip("_")))
            elif score > best[1]:
                best = (s, score, name.lstrip("_"))
        if not readings:
            return (*best, False)
        # The median, not the best-scoring one: on the flat curves this exists for, the highest
        # score is decided by noise while the middle of the three is decided by all of them.
        readings.sort(key=lambda r: r[0])
        scale, score, source = readings[len(readings) // 2]
        spread = readings[-1][0] - readings[0][0]
        agreed = len(readings) < 2 or spread <= self.RESCALE_MIN_STEP
        if not agreed:
            self._trace("calib_disagree",
                        f"Các mốc đo lệch nhau {spread:.2f} "
                        f"({', '.join(f'{n}={v:.2f}' for v, _s, n in readings)}); "
                        f"không đủ tin để căn lại toạ độ, giữ ước lượng theo dpi.", 0.0)
        return (scale, score, source, agreed)

    def _refine_scale(self, frame, template, coarse: float,
                      coarse_score: float) -> tuple[float, float]:
        """Re-search one coarse step either side of `coarse` at CAL_REFINE_STEP spacing.

        CALIBRATION_SWEEP steps by 0.05, so its answer carries up to ±0.025 of pure rounding —
        on MuMu the coarse pass said 0.55 where three sources at 0.01 spacing agree the truth is
        0.57, and the finer answer also scored better (0.96 against 0.85). Without this the
        measurement cannot be trusted below the coarse grid, which forces the adopt threshold up
        to a whole step and lets a real but modest divergence hide inside it.
        """
        span = CALIBRATION_SWEEP[1] - CALIBRATION_SWEEP[0]
        steps = int(round(span / self.CAL_REFINE_STEP))
        fine = tuple(round(coarse - span + self.CAL_REFINE_STEP * i, 4)
                     for i in range(2 * steps + 1))
        fine = tuple(s for s in fine if s > 0)
        s, score = best_matching_scale(frame, template, fine, grayscale=False,
                                       reduction=self.CAL_REDUCTION)
        # Only take the refinement when it is at least as convincing as what it replaces.
        return (s, score) if s is not None and score >= coarse_score else (coarse, coarse_score)

    def run_once(self) -> bool:
        """One catch cycle. Returns True if a ball was thrown."""
        cfg = self.config
        self._cycle_result = "idle"
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
        # anything to engage.
        #
        # The wait happens here rather than by ending the cycle. Bailing out meant the floor was
        # served one second at a time, and each of those seconds re-entered run_once and re-paid
        # the whole preamble — screenshot, popup sweep, cooldown check — so a 3s floor cost three
        # full preambles to stand still. Holding in place costs one.
        #
        # The screen still gets tended to: popups are drained between slices, which is the only
        # reason the bail-out existed. Anything that lands during the hold is cleared by the time
        # the floor is up, instead of being noticed a cycle later.
        if cfg.min_catch_interval > 0 and self._last_engage_at:
            deadline = self._last_engage_at + cfg.min_catch_interval
            wait = deadline - time.monotonic()
            if wait > 0:
                self._trace("pacing",
                            f"Giữ nhịp: còn {wait:.1f}s nữa mới bắt con tiếp theo.", 5.0)
                while not self.stop_event.is_set():
                    left_now = deadline - time.monotonic()
                    if left_now <= 0:
                        break
                    self._wait_if_paused()
                    self._interruptible_sleep(min(left_now, 1.0))
                    if self.stop_event.is_set() or time.monotonic() >= deadline:
                        break
                    self._drain_popups(self.device.screenshot())
                if self.stop_event.is_set():
                    return False
                # The frame this cycle opened with predates the hold by seconds, and every step
                # below reads it — the out-of-balls badge, the encounter check, the Nearby scan.
                # Acting on it would be acting on a screen that is gone.
                frame = self.device.screenshot()
            self._mark("giu-nhip")

        # Step 0.5: already inside an encounter? A break-out from the previous throw, an
        # encounter that opened a beat after the last cycle gave up, or a stray tap all land
        # here. The encounter screen hides the Nearby bar, so scanning for it is hopeless —
        # this check is what stops the bot from sitting in an encounter it can't see out of.
        # Check the comparatively expensive x0 colour template only after the cheap independent
        # Berry detector proves an encounter is open. It can never be meaningful on the map, and
        # skipping it there removes ~33ms from every ordinary Nearby scan on the target phone.
        ball_xy = self._ball_in(frame, strict=True)
        self._mark("check-enc")
        if ball_xy is not None:
            if self._is_out_of_balls(frame):
                self._mark("het-bong")
                self._flag_no_balls()
                return False
            self._mark("het-bong")
            self._flush_phases("dang-trong-encounter")
            self._trace("encounter_open", "Đang ở trong encounter; ném luôn.", 0.0)
            return self._finish_encounter(ball_xy)
        self._mark("het-bong")

        # Step 1: wait for the nearby bar (its '@' anchor). Polling here rides out the post-catch
        # transition/summary screen instead of wasting a whole cycle on it.
        slot = None
        # Validate a manual slot from PGSharp once before trusting it. The cooldown check above
        # normally obtained this same UI state for free; this covers runs where cooldown
        # protection is disabled or its dump happened before Nearby populated.
        if (cfg.force_slot and cfg.use_ui_dump
                and getattr(self, "_ui_nearby_slot", None) is None):
            slot = self._occupied_slot_ui()
        if slot is None:
            slot = self._occupied_slot_in(frame)
        self._mark("quet-nearby")
        if slot is None:
            slot = self._poll(self._occupied_slot_in, cfg.anchor_timeout)
            self._mark("poll-nearby")
        if slot is None:
            # The stream said empty. Ask PGSharp itself before believing it — its view tree is
            # definitive where the pixels are only suggestive — and fall back to a crisp capture
            # only when the dump could *not* be read. A dump that read fine and reported an
            # empty bar has already answered; re-asking it in pixels costs ~2.85s over Wi-Fi
            # and cannot overrule the view tree anyway.
            slot = self._occupied_slot_ui()
            if slot is None and not self._ui_empty_confirmed:
                slot = self._occupied_slot_fresh()
            self._mark("ui+anh-net")
        if slot is None:
            if self._feed_pending:
                waited = max(0.0, time.monotonic() - self._feed_pending_at)
                self._idle_streak = self._dry_streak = 0
                self._trace(
                    "feed_wait_nearby",
                    f"Đã tap Feed 1 lần; đang chờ Pokémon hiện trên Nearby ({waited:.0f}s), "
                    "không tap Feed kế tiếp.",
                    10.0,
                )
                self._mark("cho-feed-nearby"); self._flush_phases("CHO-FEED-LOAD")
                self._interruptible_sleep(cfg.idle_poll)
                return False
            # Both rows below only exist while the menu is expanded. Open it first, then let
            # the next cycle read the menu it just asked for rather than a half-drawn one.
            if self._ensure_menu_open(frame):
                self._mark("mo-menu"); self._flush_phases("mo-menu")
                self._interruptible_sleep(cfg.menu_open_wait)
                return False
            # Nothing on Nearby. The feed gets first refusal whenever the user turned it on: it
            # puts a named spawn on the bar, where restarting a stalled walk only hopes one
            # wanders into range. Behind AutoWalk it never got a turn at all — a paused row is
            # tapped on very nearly every dry cycle and that branch returns before the feed is
            # so much as read, which is exactly what "bật Feed mà nó vẫn chỉ bấm AutoWalk" was.
            # Still not on the first empty read: one of those is usually the sprite test
            # dropping a frame rather than an empty bar, and teleporting on it abandons Pokémon
            # sitting right there. With the feed off, _tap_feed_spawn returns at its own guard
            # and the order here is exactly what it has always been.
            self._mark("feed")
            if self._dry_streak >= cfg.feed_after_idle and self._tap_feed_spawn():
                self._flush_phases("feed-teleport")
                self._idle_streak = self._dry_streak = 0
                return False
            # The feed had nothing to give — empty, locked behind a jump already made, or
            # blocked by Go Plus — so fall back to the cheaper nudge and restart a walk that has
            # stalled. Only a row showing '⊘' is tapped, so a walk that is already running falls
            # straight through to the idle report below.
            if self._tap_autowalk_paused():
                self._mark("autowalk"); self._flush_phases("autowalk")
                self.stats.autowalks += 1
                self._idle_streak = 0
                self._interruptible_sleep(cfg.autowalk_wait)
                return False
            self._mark("autowalk"); self._flush_phases("NEARBY-TRONG")
            # Naming the feed here is only honest while the feed is actually being read. Once
            # a Go Plus warning has blocked a teleport the source is off and _tap_feed_spawn
            # returns at its guard without ever looking at the bar — reporting that as "nothing
            # on the feed either" reads as a broken detector and sends the user hunting for one.
            if not cfg.use_feed_bar:
                empty = "Không thấy Pokémon trên thanh Nearby (nguồn Feed đang tắt)."
            elif self._teleport_blocked:
                empty = ("Không thấy Pokémon trên thanh Nearby; nguồn Feed đã tắt vì teleport "
                         "bị chặn (Go Plus đang kết nối) — ngắt Go Plus rồi chạy lại để dùng Feed.")
            else:
                empty = "Không thấy Pokémon trên thanh Nearby lẫn thanh feed."
            self._trace("nearby_empty", empty)
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

        # Step 2: prime the row, then engage it.  Even the GUI's zero-delay setting keeps a tiny
        # 120ms floor: without that primer this PGSharp build accepted only every other gesture,
        # which cost several seconds per miss instead of saving a fraction of one.
        self._cycle_result = "encounter_wait"
        self._engage_nearby(slot)
        if self.stop_event.is_set():
            return False
        self._mark("tap-don")
        self._last_engage_at = time.monotonic()
        tapped_at = time.monotonic()
        self._trace(
            "nearby_tap",
            f"Đã xác nhận Pokémon tại {slot} và bấm mở encounter.",
            0.0,
        )
        # Start the gesture on the first stream frame where the throwable ball is ready.  A slow
        # white transition is kept inside this cycle instead of being misreported as a failed
        # encounter and rediscovered by the next one.
        ball_xy = self._wait_for_engaged_encounter()
        self._mark("cho-encounter")
        if self.stop_event.is_set():
            return False
        if ball_xy is None:
            # No encounter opened (empty nearby slot / Pokémon fled). Never throw blind here:
            # a fallback swipe on the map just drags the camera and burns the cycle. If it was
            # merely slow to open, step 0.75 of the next cycle picks it up within idle_poll.
            if self._engage_still_nearby:
                self._cycle_result = "engage_retry"
                self._trace(
                    "encounter_tap_rejected",
                    "Nearby vẫn còn nguyên sau cú tap; click chưa ăn, thử lại ngay.",
                    0.0,
                )
            else:
                self._cycle_result = "encounter_wait"
                self._trace(
                    "encounter_initial_miss",
                    f"Chưa thấy bóng sau {time.monotonic() - tapped_at:.2f}s; quét lại ở vòng sau.",
                    0.0,
                )
            self._mark("thu-lai"); self._flush_phases("KHONG-MO-DUOC")
            if not self._engage_still_nearby:
                self._interruptible_sleep(cfg.idle_poll)
            return False
        threw = self._finish_encounter(ball_xy)
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
                if on_event and not self._no_balls_alerted:
                    on_event(self.stats, False)
                self._no_balls_alerted = True
                self._wait_no_balls(on_event)
                self._idle_streak = 0
                continue

            cycle_result = getattr(self, "_cycle_result", "idle")
            self.stats.last_event = "throw" if threw else cycle_result
            if threw:
                self._no_balls_alerted = False
            if on_event:
                on_event(self.stats, threw)

            # Dry spell handling: after several empty cycles, tap AutoWalk to go find new spawns.
            if self._feed_pending:
                # Waiting for the one Feed teleport already sent is active work, not an empty
                # cycle. Never let the dry-spell AutoWalk path interfere or unlock another tap.
                self._idle_streak = self._dry_streak = 0
            elif threw:
                self._idle_streak = self._dry_streak = 0
            elif cycle_result in ("engage_retry", "encounter_wait"):
                # A Pokémon was confirmed and touched. Whether the tap needs a retry or the game
                # is still drawing its encounter, this is not a dry map: do not let the second
                # such frame start AutoWalk or fire the user's empty-cycle Discord warning.
                self._idle_streak = self._dry_streak = 0
            else:
                self._idle_streak += 1
                # Deliberately not reset by the AutoWalk branch below: restarting a stalled walk
                # says nothing about whether Pokémon have started appearing again.
                self._dry_streak += 1
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
        in_enc = self._in_encounter(frame)
        if self._enc_berry_at is not None:
            berry_x, berry_y = self._enc_berry_at
            cv2.circle(img, (berry_x, berry_y), cfg.enc_berry_radius, (0, 255, 0), 4)
            cv2.putText(img, "BERRY", (berry_x - cfg.s(70),
                                       berry_y - cfg.enc_berry_radius - cfg.s(12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        box(cfg.out_of_balls_region, (0, 140, 255), "x0")

        # Throw: start point and where the flick ends.
        bx, by = cfg.ball_fallback
        ready = self._ball_ready(frame)
        cv2.circle(img, (bx, by), max(10, cfg.s(34)), (0, 255, 0) if ready else (0, 160, 0), 4)
        # The window "còn bóng?" is actually read in — the ball's centre button, not its dome.
        cv2.circle(img, cfg.ball_hub, cfg.ball_hub_radius,
                   (0, 255, 0) if ready else (0, 160, 0), 3)
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
