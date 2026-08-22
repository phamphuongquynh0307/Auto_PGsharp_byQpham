"""Shiny checking routine with user-selected attack / defence / stamina IV targets.

Separate from the catch routine. Relies on PGSharp's own shiny check being enabled:
attempting to encounter a non-shiny is blocked by PGSharp (a 1-second
"blocked(non-shiny) IV:xx" toast), so an encounter that actually opens IS a shiny.

Per cycle:
  1. Tap the first slot of the PGSharp *feed* sidebar (the bar with the RSS icon at its
     bottom). PGSharp teleports to that spawn.
  2. Wait for the spawn to load (it shows up in the nearby '@' bar), then double-tap the
     bar's first slot — the same gesture the catch routine uses — to request the encounter.
  3. If PGSharp's "blocked(non-shiny)" toast answers (or nothing opens), move on.
  4. If an encounter opens, the Pokémon is shiny — report it over Discord and pause for
     the user either way. Reading PGSharp's info pill ("▼ L3 IV40 0/6/12 ✨ ⚡") for the
     IV value decides whether it matches the user's configured target.

The sub-IVs are read by template-matching the glyphs '1', '5' and '/' inside the pill
region and checking for the exact ordered sequence 1 5 / 1 5 / 1 5 with sane gaps.
The '5' glyph was cropped from the pill's larger IV-percent font, so it is matched at
~0.84 scale to fit the smaller sub-IV font.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field, replace

from .catch import _load_optional, _resolve
from .device import Device
from . import uidump
from .layout import (
    BASE_DENSITY, BASE_RESOLUTION, CALIBRATION_MIN_SCORE, CALIBRATION_SWEEP, Layout,
    bracket_scales, scales_around,
)
from .vision import (
    best_matching_scale, find, find_berry_button, find_enc_ball, find_fast, find_popup_close,
    find_dialog_buttons, load_template, slot_has_pokemon,
)


@dataclass
class ShundoConfig:
    # Exact attack / defence / stamina columns to keep. Shared by both source modes.
    target_ivs: tuple[int, int, int] = (15, 15, 15)

    # Feed mode checks a spawn already present at startup before consuming its first feed item.
    # Alternative coordinate sources disable this so every answer belongs to an explicit item.
    check_initial_nearby: bool = True

    # Feed sidebar (teleport source). The RSS icon at the bar's bottom is the unique
    # locator; the '≡' drag handle marks the bar's top and the first slot sits a fixed
    # distance below it. Both bars share the same handle art, so the handle is only
    # accepted when it sits in the same column as the RSS icon.
    feed_rss_template: str = "templates/feed_rss.png"
    bar_handle_template: str = "templates/bar_handle.png"
    feed_threshold: float = 0.7
    feed_slot_dy: int = 100         # handle center -> first feed slot center
    handle_column_tol: int = 60     # max |x_handle - x_rss| to count as the same bar

    # Nearby '@' bar: after the teleport we wait until its first slot actually shows a
    # Pokémon icon — that's the "game finished loading the spawn" signal. The slot sits
    # a fixed distance above the '@' anchor; an empty slot is flat translucent bar
    # (gray std ~15) while a Pokémon sprite is busy (std ~45+).
    anchor_template: str = "templates/nearby_anchor.png"
    anchor_threshold: float = 0.7
    anchor_region: tuple[int, int, int, int] = (760, 200, 460, 1800)
    slot_offset_y: int = 770        # '@' anchor -> first (top) slot center; the double-tap target
    slot_patch: int = 110           # square patch height inspected per band
    # "Spawn loaded" is decided by scanning the whole nearby-bar column (not one fixed
    # slot): a Pokémon icon anywhere in it makes some band's gray-std jump. Measured:
    # empty bar ≈ 26-32, occupied ≈ 49-52, so 40 cleanly separates them and tolerates the
    # spawn sitting at any height / the bar holding a variable number of Pokémon.
    bar_half_w: int = 70            # half-width of the bar column around the '@' x
    bar_scan_top: int = 820        # scan from ('@' y - this) ...
    bar_scan_bottom: int = 150     # ... up to ('@' y - this), excluding the '@' icon itself
    bar_scan_step: int = 55
    slot_busy_std: float = 40.0
    slot_foreground_bright_fraction: float = 0.008
    nearby_presence_frames: int = 2
    # A far teleport makes the game reload spawns, which clears the nearby bar first.
    # Waiting for that clear keeps a stale entry from the previous location from being
    # mistaken for the new spawn (the icons all look alike on event days).
    bar_clear_timeout: float = 5.0
    # Loading can be slow (hot phone, teleport cooldown), so stay put and keep waiting
    # for the spawn instead of teleporting away to another feed entry. 0 = wait until it
    # loads or the user stops. The instant it shows in the bar the double-tap goes out.
    # Zero means this is state-driven rather than time-driven: never skip a feed entry
    # merely because loading is slow.
    spawn_timeout: float = 0.0
    spawn_wait_log: float = 20.0    # log a "still waiting" heartbeat this often (s)

    # The encounter is requested by ONE double-tap of the bar's first slot (same gesture
    # as the catch routine). PGSharp only opens the encounter for a shiny, so "encounter
    # opened" IS the shiny signal; we wait up to encounter_open_wait for it and never re-tap
    # (a second double-tap would land on the opening encounter screen). No encounter in that
    # window ⇒ the Pokémon is non-shiny and we move on.
    encounter_open_wait: float = 3.0
    # Some PGSharp builds silently block a non-shiny without rendering the toast. One
    # confirmed double-tap with no encounter is therefore the final non-shiny answer;
    # never double-tap the same Pokemon a second time.
    encounter_no_answer_attempts: int = 1
    # Strict source modes can require visible proof after every double-tap. In that mode a
    # crisp post-tap frame must show either the encounter or PGSharp's blocked toast; an
    # ambiguous map frame keeps the same Nearby entry pending and never advances the source.
    require_confirmed_check: bool = False

    # A queued Nearby entry is confirmed on a crisp ADB capture before it is double-tapped,
    # and the two capture paths do disagree: the stream can show the bar occupied while the
    # one-shot reads the slot empty. Re-looking is right — the entry usually returns and no
    # QuickSniper item is spent — but it needs an end. Without one, an entry that genuinely
    # despawned parks the run on that slot for good, re-taking a full ADB capture as fast as
    # ADB can serve them. After this many looks the entry is written off and the feed moves on.
    #
    # The budget is set from the one disagreement measured live: twelve looks over fifteen
    # seconds, and then the bar read occupied again. A budget under that would have thrown away
    # an entry that was about to work, so it sits above it — roughly 20s of looking, which is
    # inside the range a normal cycle already spends waiting for a spawn to load.
    nearby_recheck_attempts: int = 15
    nearby_recheck_gap: float = 0.5     # pause between those looks, so they don't spin on ADB

    # Encounter confirmation: the raspberry glyph inside the bottom-left Berry button.
    # Camera and Poke Ball checks are deliberately excluded because their stale/animated pixels
    # can remain over map frames and falsely report a shiny.
    enc_berry_radius: int = 95
    enc_berry_min_fill: float = 0.06

    # PGSharp info pill glyphs retained as a fast 100-IV fallback when UI dump fails.
    glyph_1_template: str = "templates/glyph_1.png"
    glyph_5_template: str = "templates/glyph_5.png"
    glyph_slash_template: str = "templates/glyph_slash.png"
    pill_region: tuple[int, int, int, int] = (250, 500, 720, 170)
    glyph_threshold: float = 0.72
    glyph_max_gap: int = 45         # max px between consecutive glyph centers
    iv_read_tries: int = 3          # re-read the pill a few times before deciding

    # PGSharp's "blocked(non-shiny) IV:xx" toast: a light rounded pill at the bottom
    # centre, up for ~1s. The text frame is too fleeting to rely on (we usually catch the
    # blank-pill frame), so detection keys on the PILL SHAPE — a wide, solid, light,
    # horizontally-centred blob. The encounter screen's big white ball also lands in this
    # region, so the caller must confirm we're NOT in/opening an encounter first (ball-selector
    # absent AND the '@' bar still visible) before trusting a toast here.
    toast_region: tuple[int, int, int, int] = (150, 2260, 920, 300)   # x, y, w, h
    toast_pill_w: tuple[int, int] = (380, 860)
    toast_pill_h: tuple[int, int] = (85, 210)
    toast_fill: float = 0.7          # min filled fraction of the pill's bounding box
    toast_center_tol: int = 320      # max |pill center x - screen center x|

    menu_star_template: str = "templates/menu_star.png"
    # PGSharp's Go Plus teleport warning. Shundo teleports on every cycle, so this decides
    # whether the mode can run at all. Same tight box as the catch routine's: it stops short
    # of the OK button so a stray match can never confirm the teleport.
    cancel_btn_template: str = "templates/cancel_btn.png"
    dialog_region: tuple[int, int, int, int] = (150, 1150, 950, 500)
    cancel_btn_region: tuple[int, int, int, int] = (620, 1480, 310, 220)

    # Popups. Teleporting long distances reliably triggers the speed warning.
    popup_speed_template: str = "templates/popup_speed.png"
    popup_weather_template: str = "templates/popup_weather.png"     # "I AM SAFE" green button (weather warning)
    claim_rewards_template: str = "templates/claim_rewards.png"
    close_btn_template: str = "templates/close_btn.png"
    close_btn_blue_template: str = "templates/close_btn_blue.png"
    close_btn_white_template: str = "templates/close_btn_white.png"
    popup_threshold: float = 0.7
    popup_debounce: float = 0.75  # ignore stale stream frames after one popup tap

    # Timing (seconds).
    teleport_wait: float = 4.0      # after the feed tap, let spawns + nearby bar load
    poll_interval: float = 0.08
    idle_poll: float = 1.5          # pause between cycles when the feed bar is missing

    # What to do when a shundo is found: "pause" (default) or "stop".
    shundo_action: str = "pause"
    # What to do on a shiny whose three IV columns do not equal target_ivs:
    #   "skip"  -> flee the encounter and keep hunting the next spawn (default)
    #   "pause" -> stop on it like a shundo (obeys shundo_action's pause/stop)
    shiny_action: str = "skip"
    # Encounter flee button (running-man, top-left) — used to leave a skipped shiny.
    flee_xy: tuple[int, int] = (120, 170)
    # MuMu can silently drop a tap sent through the persistent scrcpy control socket.
    # Use independent ADB taps and do not consume another QuickSniper entry until the
    # Nearby '@' anchor proves that the map has actually returned.
    flee_taps: int = 3
    flee_gap_ms: int = 300
    flee_map_wait: float = 5.0

    # Actual device resolution; see CatchConfig.screen. Coordinate FIELDS above are stored
    # already re-anchored to this resolution; raw pixel literals in the routine use s()/rect().
    screen: tuple[int, int] = BASE_RESOLUTION
    # Device density (dpi). Drives dp-correct scaling; None falls back to width-ratio.
    density: int | None = None
    # Measured render scale and the BASE_RESOLUTION original to re-derive from; see CatchConfig,
    # where the reason these exist is written out in full.
    render_scale: float | None = None
    base_config: "ShundoConfig | None" = field(default=None, repr=False, compare=False)

    @property
    def layout(self) -> Layout:
        return Layout(*self.screen, density=self.density, scale=self.render_scale)

    def s(self, v: float) -> int:
        return self.layout.scale(v)

    def pt(self, p: tuple[int, int], anchor: str) -> tuple[int, int]:
        return self.layout.point(p, anchor)

    def rect(self, r: tuple[int, int, int, int], anchor: str) -> tuple[int, int, int, int]:
        return self.layout.region(r, anchor)

    def rescale(self, scale: float) -> "ShundoConfig":
        """Re-derive every coordinate at a measured render scale; see CatchConfig.rescale."""
        base = self.base_config or self
        return base.scale_to(*self.screen, self.density, scale=scale)

    def scale_to(self, width: int, height: int, density: int | None = None,
                 *, scale: float | None = None) -> "ShundoConfig":
        """Return a copy with every pixel coordinate re-anchored from BASE_RESOLUTION onto
        (width, height) at `density` dpi. Each field is tagged with the edge/corner it hugs
        (see avc/layout.py). No-op (returns self) at the base resolution+density.

        `scale` overrides the density estimate with a measured render scale; see `rescale`.
        `L` is the native-view layer (PGSharp overlay, system dialogs) a measurement applies to;
        `G` is Pokémon GO's own UI, which stays on the density estimate. See CatchConfig.scale_to.
        """
        L = Layout(width, height, density=density, scale=scale)
        # No density: the game layer follows the screen, not the dp density — verified on two
        # devices via the berry↔ball span (see CatchConfig.scale_to).
        G = Layout(width, height)
        if (width, height) == BASE_RESOLUTION and abs(L.s - 1.0) < 1e-9:
            return self
        return replace(
            self,
            screen=(width, height),
            density=density,
            render_scale=scale,
            base_config=self.base_config or self,
            anchor_region=L.region(self.anchor_region, "TR"),
            # anchored regions/positions
            pill_region=L.region(self.pill_region, "TC"),       # PGSharp IV pill, upper-centre
            toast_region=L.region(self.toast_region, "BC"),     # blocked toast, bottom-centre
            dialog_region=L.region(self.dialog_region, "MC"),  # centred Android AlertDialog
            cancel_btn_region=L.region(self.cancel_btn_region, "MC"),  # centred system dialog
            flee_xy=G.point(self.flee_xy, "TL"),   # game-drawn flee button, top-left
            # pure distances/sizes/offsets
            feed_slot_dy=L.scale(self.feed_slot_dy),
            handle_column_tol=L.scale(self.handle_column_tol),
            slot_offset_y=L.scale(self.slot_offset_y),
            slot_patch=L.scale(self.slot_patch),
            bar_half_w=L.scale(self.bar_half_w),
            bar_scan_top=L.scale(self.bar_scan_top),
            bar_scan_bottom=L.scale(self.bar_scan_bottom),
            bar_scan_step=max(1, L.scale(self.bar_scan_step)),
            glyph_max_gap=L.scale(self.glyph_max_gap),
            toast_pill_w=(L.scale(self.toast_pill_w[0]), L.scale(self.toast_pill_w[1])),
            toast_pill_h=(L.scale(self.toast_pill_h[0]), L.scale(self.toast_pill_h[1])),
            toast_center_tol=L.scale(self.toast_center_tol),
            enc_berry_radius=max(8, G.scale(self.enc_berry_radius)),
        )


@dataclass
class ShundoStats:
    cycles: int = 0
    checked: int = 0    # encounter attempts (double-taps that got an answer)
    shinies: int = 0    # encounters that actually opened
    shundos: int = 0
    last_ivs: tuple[int, int, int] | None = None
    last_event: str = ""  # "blocked" | "shiny" | "shundo" | "iv_unknown" | "miss" | "recheck" | "lost"
                          # | "nospawn" | "idle" | "popup"


# Outcomes that leave the queued Nearby entry in place for another look, instead of finishing
# with it. Everything else — an answer, or giving the entry up — releases it.
KEEP_PENDING = ("miss", "recheck")


class ShundoRoutine:
    def __init__(self, device: Device, config: ShundoConfig | None = None) -> None:
        self.device = device
        self.config = config or ShundoConfig()
        # Templates are authored at BASE_RESOLUTION. The game's UI may or may not scale with the
        # device (unreliable under a resolution override), so keep templates at base size and let
        # find() sweep a bracket of scales (bracket_scales). On the base device this is a no-op.
        # The IV-pill glyph matcher below keeps its own finely-tuned per-glyph scales.
        self._tpl_s = self.config.layout.s
        self._scales = bracket_scales(self._tpl_s)
        # Popup buttons belong to Pokemon GO's game layer, which follows screen size rather than
        # PGSharp's density-scaled overlay. MuMu measures ~0.66 for the game and ~0.57 for the
        # overlay, enough for a tight template sweep to miss every warning button.
        game_s = Layout(*self.config.screen).s
        self._popup_scales = bracket_scales(game_s)
        self._cal_scale: float | None = None   # measured render scale; None until calibrated
        self._anchor_cache: tuple[int, int] | None = None
        self._feed_cache: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None = None
        self._nearby_presence_streak = 0
        self._nearby_last_y: int | None = None
        self._feed_presence_streak = 0
        self._enc_berry_at: tuple[int, int] | None = None
        # A teleported Nearby entry stays pending until PGSharp gives a real answer, or
        # until a bounded number of confirmed map double-taps produce no encounter. The
        # latter covers builds that silently block non-shiny Pokémon without a toast.
        self._pending_nearby: tuple[int, int] | None = None
        self._pending_no_answers = 0
        # Looks spent trying to see the pending entry again on a crisp capture.
        self._pending_no_target = 0
        # Set once the Go Plus warning has been answered CANCEL. Shundo has no path that
        # avoids teleporting, so the run cannot continue.
        self._teleport_blocked = False

        def load(path):
            return load_template(_resolve(path))

        def load_opt(path):
            return _load_optional(path)

        self._rss = load(self.config.feed_rss_template)
        self._handle = load(self.config.bar_handle_template)
        self._anchor = load(self.config.anchor_template)
        self._g1 = load(self.config.glyph_1_template)
        self._g5 = load(self.config.glyph_5_template)
        self._gs = load(self.config.glyph_slash_template)
        self._menu_star = load_opt(self.config.menu_star_template)
        self._cancel_btn = load_opt(self.config.cancel_btn_template)
        self._popup_speed = load_opt(self.config.popup_speed_template)
        self._popup_weather = load_opt(self.config.popup_weather_template)
        self._claim_rewards = load_opt(self.config.claim_rewards_template)
        self._close_btns = [
            b for b in (
                load_opt(self.config.close_btn_template),
                load_opt(self.config.close_btn_blue_template),
                load_opt(self.config.close_btn_white_template),
            ) if b is not None
        ]
        self.stats = ShundoStats()
        self._popup_block_until = 0.0
        # Optional callback(seconds_waited) so the GUI can log a "still waiting for spawn"
        # heartbeat during a long load without the routine knowing about the UI.
        self._on_waiting = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

    # -- shared control plumbing (same contract as CatchRoutine) ----------------
    def _interruptible_sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return
            time.sleep(min(0.05, deadline - time.monotonic()))

    def _wait_if_paused(self) -> None:
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.1)

    def _poll(self, predicate, timeout: float):
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

    # -- element lookups ---------------------------------------------------------
    def _anchor_in(self, frame) -> tuple[int, int] | None:
        cfg = self.config
        region = cfg.anchor_region
        if self._anchor_cache is not None:
            ax, ay = self._anchor_cache
            radius = cfg.s(110)
            region = (ax - radius, ay - radius, radius * 2, radius * 2)
        m = find(frame, self._anchor, threshold=cfg.anchor_threshold,
                 scales=self._scales, region=region, max_matches=1)
        if not m and self._anchor_cache is not None:
            self._anchor_cache = None
            m = find(frame, self._anchor, threshold=cfg.anchor_threshold,
                     scales=self._scales, region=cfg.anchor_region, max_matches=1)
        if not m:
            return None
        self._anchor_cache = m[0].center
        return self._anchor_cache

    def _nearby_slot(self, frame, anchor: tuple[int, int]) -> tuple[int, int]:
        """First slot of the nearby bar, measured from its '≡' drag handle.

        `slot_offset_y` above the '@' only lands right on a *full* bar: the '@' marks the
        bar's bottom, so a shorter list pulls it up and the fixed offset walks off the top of
        the bar entirely (negative y on a short list). The handle marks the top, and the list
        grows down from it, so handle + dy holds for any length. Kept as the fallback for when
        the handle can't be matched. Same construction as CatchRoutine._bar_slot."""
        cfg = self.config
        ax, ay = anchor
        if self._handle is not None:
            column = (ax - cfg.handle_column_tol * 2, 0, cfg.handle_column_tol * 4, ay)
            for h in find(frame, self._handle, threshold=cfg.feed_threshold,
                          scales=self._scales, region=column, max_matches=4):
                hx, hy = h.center
                # The feed bar shares this handle art, so only one in the '@' column counts.
                if abs(hx - ax) <= cfg.handle_column_tol and hy < ay:
                    return (ax, hy + cfg.feed_slot_dy)
        return (ax, ay - cfg.slot_offset_y)

    def _occupied_in_column(self, frame, x: int, top: int, bottom: int):
        """First y between `top` and `bottom` whose slot window holds a Pokémon sprite.

        Both sidebars are translucent, so a busy map bleeding through can put more edges
        around a sprite than in it and make its slot fail the texture test while the bar is
        plainly full. Checking only the first slot then reports an empty bar and the routine
        idles (or declares 'no spawn') with Pokémon sitting right there, so scan the column."""
        cfg = self.config
        step = max(12, cfg.s(40))
        y = top
        while y <= bottom:
            if slot_has_pokemon(frame, (x, y), half_width=cfg.bar_half_w,
                                height=cfg.slot_patch,
                                min_foreground_bright_fraction=getattr(
                                    cfg, "slot_foreground_bright_fraction", 0.0
                                )):
                return y
            y += step
        return None

    def _raw_target_in_bar(self, frame):
        """The occupied Nearby slot in one frame, without temporal confirmation."""
        cfg = self.config
        anchor = self._anchor_in(frame)
        if anchor is None:
            return None
        slot = self._nearby_slot(frame, anchor)
        evidence_y = self._occupied_in_column(frame, slot[0], slot[1], anchor[1] - cfg.s(80))
        # Nearby fills from the top with no gaps. A lower match is evidence that slot 1 is
        # occupied, not a reason to tap between rows at the scanner's sampling coordinate.
        return slot if evidence_y is not None else None

    def _target_in_bar(self, frame):
        """The nearby slot to engage, or None. Needs two fresh frames in a row so a single
        noisy read cannot trigger a tap."""
        cfg = self.config
        target = self._raw_target_in_bar(frame)
        y = target[1] if target else None
        # The column scanner samples in ~40 px rows; the same sprite can legitimately be
        # attributed to either neighbouring row on consecutive compressed frames.
        tolerance = max(12, cfg.s(65))
        stable = y is not None and (
            self._nearby_last_y is None or abs(y - self._nearby_last_y) <= tolerance
        )
        self._nearby_presence_streak = self._nearby_presence_streak + 1 if stable else (1 if y else 0)
        self._nearby_last_y = y
        required = max(2, int(getattr(cfg, "nearby_presence_frames", 2)))
        return target if target is not None and self._nearby_presence_streak >= required else None

    def _feed_slot_in(self, frame) -> tuple[int, int] | None:
        """The feed entry to teleport to, or None when the feed really is empty.

        The feed is a QUEUE: tapping an entry teleports to it and removes it. Slot 1 is the
        natural target, but its sprite test is marginal against a translucent bar over a busy
        map — trusting it alone reported an empty feed while entries were listed right below.
        So the column is scanned and the topmost readable entry is used; any of them is a
        spawn worth checking. Located from the '≡' handle in the RSS icon's column."""
        cfg = self.config

        def occupied(rx, ry, slot):
            y = self._occupied_in_column(frame, rx, slot[1], ry - cfg.s(60))
            self._feed_presence_streak = self._feed_presence_streak + 1 if y else 0
            return (rx, y) if y and self._feed_presence_streak >= 2 else None

        if self._feed_cache is not None:
            (rx, ry), (hx, hy), slot = self._feed_cache
            radius = cfg.s(100)
            rss_region = (rx - radius, ry - radius, radius * 2, radius * 2)
            handle_region = (hx - radius, hy - radius, radius * 2, radius * 2)
            rss = find(frame, self._rss, threshold=cfg.feed_threshold, scales=self._scales,
                       region=rss_region, max_matches=1)
            handle = find(frame, self._handle, threshold=cfg.feed_threshold, scales=self._scales,
                          region=handle_region, max_matches=1)
            if rss and handle:
                return occupied(rx, ry, slot)
            self._feed_cache = None
            self._feed_presence_streak = 0
        rss = find(frame, self._rss, threshold=cfg.feed_threshold, scales=self._scales)
        if not rss:
            return None
        rx, ry = rss[0].center
        column = (rx - cfg.handle_column_tol * 2, 0, cfg.handle_column_tol * 4, frame.shape[0])
        handles = find(frame, self._handle, threshold=cfg.feed_threshold, scales=self._scales,
                       region=column)
        for h in handles:
            hx, hy = h.center
            if abs(hx - rx) <= cfg.handle_column_tol and hy < ry:
                slot = (rx, hy + cfg.feed_slot_dy)
                self._feed_cache = ((rx, ry), (hx, hy), slot)
                return occupied(rx, ry, slot)
        self._feed_presence_streak = 0
        return None

    def _encounter_visible(self, frame) -> bool:
        """True when an encounter is open, which for Shundo means the Pokémon is shiny.

        Require both independent corner controls from the same frame: the bottom-left Berry
        button and the bottom-right ball selector. A live false alert proved that the map's
        trainer/buddy circle can occasionally satisfy the Berry geometry by itself. The ball
        selector is absent on the map, so the pair rejects that look-alike without relying on
        the bright camera/AR icon, which disappears against a white encounter sky.
        """
        cfg = self.config
        self._enc_berry_at = find_berry_button(
            frame,
            scale=cfg.layout.s,
            radius=cfg.enc_berry_radius,
            min_berry_fill=cfg.enc_berry_min_fill,
        )
        if self._enc_berry_at is None:
            return False
        return find_enc_ball(frame, scale=cfg.layout.s) is not None

    def _blocked_toast_in(self, frame) -> bool:
        """A light rounded toast pill sits in the bottom-centre region. Shape only — see
        toast_region notes. Callers must first rule out an (opening) encounter."""
        import cv2
        cfg = self.config
        x, y, w, h = cfg.toast_region
        gray = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 165, 255, cv2.THRESH_BINARY)
        n, _labels, stats, _cents = cv2.connectedComponentsWithStats(bw, 8)
        screen_cx = frame.shape[1] / 2
        for i in range(1, n):
            cx, cy, cw, ch, area = stats[i]
            if not (cfg.toast_pill_w[0] <= cw <= cfg.toast_pill_w[1]
                    and cfg.toast_pill_h[0] <= ch <= cfg.toast_pill_h[1]):
                continue
            if area < cw * ch * cfg.toast_fill:       # solid rounded pill
                continue
            if abs((x + cx + cw / 2) - screen_cx) > cfg.toast_center_tol:
                continue
            return True
        return False

    def _handle_popups(self, frame=None) -> bool:
        if time.monotonic() < self._popup_block_until:
            return False
        if frame is None:
            frame = self.device.screenshot()
        fast_cache = {}
        # PGSharp "Go Plus is connected, teleport may trigger a softban. Continue?" -> CANCEL.
        # First, because it is a modal that eats every other tap, and the answer is never OK:
        # confirming risks the account. Shundo teleports every cycle, so the run is over —
        # see the _teleport_blocked check in run_once.
        if self._cancel_btn is not None:
            m = find(frame, self._cancel_btn, threshold=self.config.popup_threshold,
                     scales=self._scales, grayscale=False,
                     region=self.config.cancel_btn_region, max_matches=1)
            if m:
                self.device.tap(*m[0].center)
                self._teleport_blocked = True
                self.stats.last_event = "popup"
                return True
        # Some Android skins alter the CANCEL font/background enough that the template misses.
        # The warning is still a stock two-button AlertDialog, so recognise its two aligned
        # buttons and choose the left one. In Shundo this is the only native two-button modal
        # raised by the teleport path, therefore it has the same terminal meaning as the
        # template-backed Go Plus warning above.
        buttons = find_dialog_buttons(frame, self.config.dialog_region)
        if len(buttons) >= 2:
            target = min(buttons, key=lambda b: b[0])
            self.device.tap(*target)
            self._teleport_blocked = True
            self.stats.last_event = "popup"
            return True
        # NOTE: there used to be a "PGSharp menu accidentally left open -> tap the star to close
        # it" handler here. The menu's expanded row list is the normal, permanent state of this
        # UI, so its Settings gear matches on every ordinary map frame — the handler fired every
        # cycle and tapped the star, fighting the user's own layout. The expanded menu overlaps
        # neither sidebar nor any tap target, so nothing needs closing.
        # Medal/share screens expose a high-confidence bottom X. Handle it before green warning
        # buttons: the SHARE pill can otherwise resemble the weather warning at low resolution.
        if not self._encounter_visible(frame):
            close = find_popup_close(
                frame,
                self._close_btns,
                threshold=max(0.82, self.config.popup_threshold),
                scales=self._popup_scales,
                fallback_scales=CALIBRATION_SWEEP,
                cache=fast_cache,
            )
            if close is not None:
                self.device.tap(*close.center)
                self.stats.last_event = "popup"
                return True

        # Weather warning -> tap the green "I AM SAFE" button (a full modal blocking the flow).
        if self._popup_weather is not None:
            m = find_fast(frame, self._popup_weather,
                          threshold=max(0.82, self.config.popup_threshold),
                          scales=self._popup_scales, cache=fast_cache)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        if self._popup_speed is not None:
            m = find_fast(frame, self._popup_speed, threshold=self.config.popup_threshold,
                          scales=self._popup_scales, cache=fast_cache)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        if self._claim_rewards is not None:
            m = find_fast(frame, self._claim_rewards, threshold=self.config.popup_threshold,
                          scales=CALIBRATION_SWEEP, cache=fast_cache)
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                # Advance through the reward cards until the nearby bar returns.
                cx, cy = self.config.pt((610, 1000), "TC")
                deadline = time.monotonic() + 15.0
                while time.monotonic() < deadline and not self.stop_event.is_set():
                    self._interruptible_sleep(0.5)
                    f = self.device.screenshot()
                    if self._anchor_in(f) is not None:
                        break
                    self.device.tap(cx, cy)
                return True
        # Do not run a second, lower-confidence X search here. The high-confidence search
        # above already handles real close buttons. Repeating it at the generic 0.70 popup
        # threshold occasionally matched moving map art while waiting for a spawn and tapped
        # a screen that had no popup at all.
        return False

    def _drain_popups(self, frame=None) -> bool:
        """Tap once, then debounce stale stream frames so the same control cannot toggle."""
        if not self._handle_popups(frame):
            return False
        self._popup_block_until = time.monotonic() + self.config.popup_debounce
        self._interruptible_sleep(max(0.06, self.config.poll_interval))
        return True

    # -- IV reading ---------------------------------------------------------------
    def _read_pill_glyphs(self, frame) -> list[tuple[float, str]]:
        cfg = self.config
        raw: list[tuple[float, str, float]] = []
        for label, tpl, scales in (("1", self._g1, (0.95, 1.0, 1.05)),
                                   ("5", self._g5, (0.80, 0.84, 0.88)),
                                   ("/", self._gs, (0.95, 1.0, 1.05))):
            for m in find(frame, tpl, threshold=cfg.glyph_threshold, scales=scales,
                          max_matches=8, region=cfg.pill_region):
                raw.append((m.x + m.width / 2, label, m.score))
        # The same glyph can match twice at neighbouring scales, ~10-15px apart, which
        # would inject a phantom character into the sequence. Real same-label neighbours
        # in the pill are ≥50px apart, so collapse same-label hits within 20px, keeping
        # the stronger one.
        raw.sort(key=lambda g: -g[2])
        kept: list[tuple[float, str, float]] = []
        for x, label, score in raw:
            if any(k_label == label and abs(k_x - x) < 20 for k_x, k_label, _s in kept):
                continue
            kept.append((x, label, score))
        out = [(x, label) for x, label, _s in kept]
        out.sort()
        return out

    def _is_hundo(self, frame) -> bool:
        cfg = self.config
        seq = self._read_pill_glyphs(frame)
        labels = [s[1] for s in seq]
        xs = [s[0] for s in seq]
        target = list("15/15/15")
        n = len(target)
        for i in range(len(labels) - n + 1):
            if labels[i:i + n] == target:
                gaps = [xs[i + j + 1] - xs[i + j] for j in range(n - 1)]
                if all(5 < g < cfg.glyph_max_gap for g in gaps):
                    return True
        return False

    def _read_iv_stats(self, frame) -> tuple[int, int, int] | None:
        """Read PGSharp's exact three IV columns, with the old hundo vision fallback.

        A UI dump is paid for only after a shiny encounter is already open. It is slower
        than vision but exposes the exact number needed for arbitrary user targets.
        """
        state = uidump.parse(self.device.ui_dump() or "")
        if state is not None and state.iv_stats is not None:
            return state.iv_stats
        if tuple(self.config.target_ivs) == (15, 15, 15) and self._is_hundo(frame):
            return 15, 15, 15
        return None

    # -- pending Nearby entry ---------------------------------------------------------
    def _queue_pending(self, target: tuple[int, int]) -> None:
        """Take `target` as the entry to work on, with both retry budgets full."""
        self._pending_nearby = target
        self._pending_no_answers = 0
        self._pending_no_target = 0

    def _release_pending(self) -> None:
        self._pending_nearby = None
        self._pending_no_answers = 0
        self._pending_no_target = 0

    # -- main loop --------------------------------------------------------------------
    def _attempt_nearby(self, target: tuple[int, int]) -> str:
        """Try one Nearby entry and return blocked/shiny/shundo/miss/recheck/lost.

        The map and occupied Nearby slot are freshly confirmed before one double-tap. If
        PGSharp keeps the screen on the map without rendering its blocked toast, that single
        no-encounter answer is treated as non-shiny and the feed advances.
        """
        cfg = self.config
        frame = self.device.screenshot(fresh=True)
        if self._encounter_visible(frame):
            return self._grade_encounter(confirmed_frame=frame)

        # Never tap a coordinate remembered from an earlier map frame. The sidebar can
        # move or collapse while loading; confirm the occupied slot again on this frame.
        current = self._raw_target_in_bar(frame)
        if current is None:
            # Not an answer about this Pokémon — we simply cannot see it — so look again
            # rather than spending the next QuickSniper item. Bounded, because an entry that
            # despawned never comes back and the run has to move on. See nearby_recheck_*.
            self._pending_no_target += 1
            if getattr(cfg, "require_confirmed_check", False):
                self._interruptible_sleep(cfg.nearby_recheck_gap)
                self.stats.last_event = "recheck"
                return "recheck"
            if self._pending_no_target >= max(1, cfg.nearby_recheck_attempts):
                self.stats.last_event = "lost"
                return "lost"
            self._interruptible_sleep(cfg.nearby_recheck_gap)
            self.stats.last_event = "recheck"
            return "recheck"
        self._pending_no_target = 0
        self.device.double_tap(*current)

        def encounter_answer(f):
            if self._encounter_visible(f):
                return "shiny"
            # The toast is only meaningful while the Nearby anchor still proves that
            # this is the map, not a bright transition frame inside an encounter.
            if self._anchor_in(f) is not None and self._blocked_toast_in(f):
                return "blocked"
            return None

        answer = self._poll(encounter_answer, cfg.encounter_open_wait)
        confirmed_answer_frame = None
        if getattr(cfg, "require_confirmed_check", False):
            if self.stop_event.is_set():
                self.stats.last_event = "miss"
                return "miss"
            # A stream answer is only a hint: stale frames after teleport/popups can resemble
            # a blocked toast. Strict modes always take a new ADB image and decide from it.
            confirmed_answer_frame = self.device.screenshot(fresh=True)
            answer = encounter_answer(confirmed_answer_frame)
            if answer is None:
                self._pending_no_answers += 1
                if self._pending_no_answers >= max(1, cfg.encounter_no_answer_attempts):
                    # Some PGSharp builds silently reject a non-shiny without drawing the
                    # blocked toast. We still have strong proof of a real check: stable spawn,
                    # crisp pre-tap slot, physical double-tap, then a fresh map image with no
                    # encounter. After the bounded retry, accept that as non-shiny.
                    self.stats.checked += 1
                    self.stats.last_event = "blocked"
                    return "blocked"
                self.stats.last_event = "miss"
                return "miss"
        elif answer is None:
            if self.stop_event.is_set():
                self.stats.last_event = "miss"
                return "miss"
            self._pending_no_answers += 1
            if answer is None and self._pending_no_answers >= max(1, cfg.encounter_no_answer_attempts):
                # The slot and map were freshly confirmed before every double-tap. PGSharp
                # builds that suppress the blocked toast answer only by keeping us on the
                # map; after the bounded retry that is a valid non-shiny result.
                self.stats.checked += 1
                self.stats.last_event = "blocked"
                return "blocked"
            if answer is None:
                self.stats.last_event = "miss"
                return "miss"

        self._pending_no_answers = 0
        if answer == "blocked":
            self.stats.checked += 1
            self.stats.last_event = "blocked"
            return "blocked"
        # A streamed H.264 frame is only a candidate. Compression smear or a delayed
        # decoder frame can briefly resemble the Berry button while the live screen is
        # already back on the map. _grade_encounter takes a crisp one-shot frame and
        # refuses to count/report the shiny unless that independent frame confirms it.
        return self._grade_encounter(confirmed_frame=confirmed_answer_frame)

    def _teleport_next(self, frame) -> str | None:
        """Consume the next Feed entry and teleport.

        ``None`` means a teleport was dispatched and the common clear/load/encounter phases may
        continue. A string is a completed cycle outcome. Coordinate-backed Shundo overrides only
        this source step; shiny detection and safety handling remain shared.
        """
        cfg = self.config
        slot = self._feed_slot_in(frame)
        if slot is None:
            slot = self._feed_slot_in(self.device.screenshot(fresh=True))
        if slot is None:
            self._interruptible_sleep(cfg.idle_poll)
            self.stats.last_event = "idle"
            return "idle"
        self.device.tap(*slot)
        self._interruptible_sleep(min(0.75, cfg.teleport_wait))
        if self.stop_event.is_set():
            return "idle"
        return None

    def _flee_to_map(self) -> bool | None:
        """Leave a skipped shiny and prove that the encounter UI is gone.

        Returns ``None`` only when the user stopped the run. The encounter was freshly confirmed
        immediately before this call, so send the low-latency scrcpy Flee tap first instead of
        spending a ~1s ADB screenshot proving the same state again. A fresh frame showing the
        Nearby anchor confirms the map in one look; two encounter-free frames remain the fallback
        when that translucent anchor is temporarily hard to match.
        """
        cfg = self.config
        max_actions = max(6, max(1, int(cfg.flee_taps)) * 3)
        max_checks = max_actions + 4
        deadline = time.monotonic() + max(10.0, cfg.flee_map_wait)
        outside_streak = 0
        # The persistent control socket is already warm from opening the encounter. This tap is
        # tens of milliseconds; the old close-control + standalone ADB tap cost about a second.
        self.device.tap(*cfg.flee_xy)
        actions = 1
        checks = 0
        while checks < max_checks and time.monotonic() < deadline:
            if self.stop_event.is_set():
                return None
            # Never validate Flee from the H.264 stream. The cached detection layer and
            # decoder can trail the phone by several frames, which reported ENCOUNTER on a
            # map that was already visible. A skipped shiny is rare, so two crisp one-shot
            # ADB frames are worth the cost here.
            frame = self.device.screenshot(fresh=True)
            checks += 1
            in_encounter = self._encounter_visible(frame)
            if not in_encounter:
                outside_streak += 1
                if self._anchor_in(frame) is not None or outside_streak >= 2:
                    return True
                # Do not send another exit command between the two confirmation frames.
                self._interruptible_sleep(max(0.06, cfg.poll_interval))
                continue

            outside_streak = 0
            if actions >= max_actions:
                continue
            if actions % 2 == 1:
                # Fallback: Android Back exits a Pokemon encounter without depending on any
                # screen coordinate. This handles shifted layouts and taps silently dropped by
                # MuMu while keeping the next action state-gated by a fresh Berry detection.
                self.device.back()
            else:
                # Retry the visible button through the still-warm low-latency control socket.
                self.device.tap(*cfg.flee_xy)
            actions += 1
            # A fresh screencap itself costs long enough for the transition to advance. Keep only
            # a tiny yield here instead of the old forced 450ms after every action.
            self._interruptible_sleep(max(0.06, min(0.15, cfg.flee_gap_ms / 1000.0)))
        return False

    def _ensure_calibrated(self) -> None:
        """Measure the device's real UI render scale once (from the always-on PGSharp menu star)
        and centre the match-scale sweep on it, instead of guessing from resolution/density.
        Until it locks, the wide bracket from __init__ stays in effect; a missing/hidden star
        just leaves it to retry next cycle."""
        if self._cal_scale is not None:
            return
        s, score, agreed = self._measure_render_scale()
        if s is not None and score >= CALIBRATION_MIN_SCORE:
            self._cal_scale = s
            self._scales = scales_around(s)
            if agreed:
                self._adopt_measured_scale(s)

    # See CatchRoutine.CAL_SOURCES — same PGSharp-drawn icons, same ordering by reliability.
    CAL_SOURCES: tuple[str, ...] = ("_anchor", "_menu_star", "_rss")
    CAL_REDUCTION = 0.5

    def _measure_render_scale(self) -> tuple[float | None, float, bool]:
        """Measure the render scale from every known PGSharp icon on screen, and say whether
        they agree. See CatchRoutine._measure_render_scale — a real phone had its three sources
        peak at 1.10, 1.04 and 1.07 on curves flat enough that whichever was asked first won."""
        frame = self.device.screenshot()
        best: tuple[float | None, float] = (None, 0.0)
        readings: list[float] = []
        for name in self.CAL_SOURCES:
            template = getattr(self, name, None)
            if template is None:
                continue
            s, score = best_matching_scale(frame, template, CALIBRATION_SWEEP,
                                           grayscale=False, reduction=self.CAL_REDUCTION)
            if s is not None and score >= CALIBRATION_MIN_SCORE:
                readings.append(s)
                if score > best[1]:
                    best = (s, score)
            elif score > best[1]:
                best = (s, score)
        if not readings:
            return (*best, False)
        readings.sort()
        agreed = len(readings) < 2 or (readings[-1] - readings[0]) <= self.RESCALE_MIN_STEP
        return (readings[len(readings) // 2], best[1], agreed)

    # See CatchRoutine — the gap must clear one absolute 0.05 step of CALIBRATION_SWEEP, or it
    # fires on the sweep's own rounding rather than on a real disagreement.
    RESCALE_MIN_STEP = 0.05

    def _adopt_measured_scale(self, scale: float) -> None:
        """Re-derive the config's coordinates at the render scale just measured, so a device the
        density guess got wrong stops reading fixed points in the wrong place."""
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

    def run_once(self) -> str:
        """One check cycle. Returns the outcome:
        blocked | shiny | shundo | miss | recheck | lost | nospawn | idle | popup | goplus."""
        cfg = self.config
        if self._teleport_blocked:
            return "goplus"
        self.stats.cycles += 1
        self._ensure_calibrated()

        frame = self.device.screenshot()
        if self._drain_popups(frame):
            return "popup"

        # An encounter already open at cycle start is a shiny whose answer we missed
        # (it can open a beat after the per-tap wait gave up — PGSharp hides both bars
        # while it's up, so this must be checked before looking for the feed). Grade it
        # now instead of idling forever.
        if self._encounter_visible(frame):
            outcome = self._grade_encounter()
            if outcome not in KEEP_PENDING:
                self._release_pending()
            return outcome

        # A previous double-tap got no visible answer, or the entry could not be seen to tap
        # at all. Retry that same Nearby entry; never consume another QuickSniper item merely
        # because the answer timed out.
        if self._pending_nearby is not None:
            outcome = self._attempt_nearby(self._pending_nearby)
            if outcome not in KEEP_PENDING:
                self._release_pending()
            return outcome

        # The first cycle must check a Pokémon already present in Nearby before consuming
        # a feed entry. Otherwise pressing Run immediately teleports away from an unchecked
        # spawn at the current location. Confirm it on two frames, matching _target_in_bar's
        # anti-noise rule; later cycles keep using the feed so the last checked spawn is not
        # opened repeatedly.
        if getattr(cfg, "check_initial_nearby", True) and self.stats.checked == 0:
            self._target_in_bar(frame)
            fresh = self.device.screenshot(fresh=True)
            initial_target = self._target_in_bar(fresh)
            if initial_target is not None:
                self._queue_pending(initial_target)
                outcome = self._attempt_nearby(initial_target)
                if outcome not in KEEP_PENDING:
                    self._release_pending()
                return outcome

        # The feed may remain visible during a transition, but it is unsafe to touch
        # until the Nearby '@' anchor confirms that the map itself is ready.
        if self._anchor_in(frame) is None:
            frame = self.device.screenshot(fresh=True)
            if self._anchor_in(frame) is None:
                self._interruptible_sleep(cfg.poll_interval)
                self.stats.last_event = "miss"
                return "miss"

        # Step 1: teleport to the next feed candidate. A miss on the stream frame is
        # retried on a crisp one-shot capture first — H.264 smear between keyframes
        # periodically drops the small RSS/handle templates below threshold.
        source_outcome = self._teleport_next(frame)
        if source_outcome is not None:
            return source_outcome

        # Teleporting far reliably raises the speed warning — clear it before tapping on.
        self._drain_popups()

        # Step 2a: the far teleport reloads spawns and empties the nearby '@' bar.
        # Wait for that clear first, so an entry left over from the previous location
        # can't be mistaken for the new spawn. A short hop (or a very fast reload) can
        # replace one occupied list with another without ever exposing an empty frame;
        # cap this phase so a successful shiny Flee cannot leave the run stuck here.
        empty_streak = 0
        clear_deadline = time.monotonic() + max(0.5, cfg.bar_clear_timeout)
        while not self.stop_event.is_set():
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            if self._raw_target_in_bar(frame):
                empty_streak = 0
            else:
                empty_streak += 1
            # One smeared/mid-transition frame is not enough: require the old Nearby
            # entry to be absent twice consecutively before accepting a future entry as
            # the newly teleported spawn.
            if empty_streak >= 2:
                break
            if self._drain_popups(frame):
                empty_streak = 0
                # A modal prevented us from observing the teleport transition; give the
                # clear detector a fresh full window after dismissing it.
                clear_deadline = time.monotonic() + max(0.5, cfg.bar_clear_timeout)
                continue
            # A fast/short teleport can replace the old occupied slot directly with the
            # new one, without ever rendering an empty Nearby frame. Do not wait forever;
            # the following phase still requires a stable multi-frame Pokémon presence,
            # and strict modes require a fresh-image answer before advancing the coord.
            if time.monotonic() >= clear_deadline:
                break
        if self.stop_event.is_set():
            return "idle"
        # Step 2b must establish its own two-frame presence streak. In particular, when
        # the clear phase timed out on a continuously occupied bar, no presence evidence
        # from the previous location may leak into the "new spawn loaded" decision.
        self._nearby_presence_streak = 0
        self._nearby_last_y = None

        # Step 2b: wait until the game actually loads the spawn — the Pokémon shows up
        # in the bar's first slot. Stays put and waits (spawns can load slowly); it does
        # NOT teleport away. With spawn_timeout == 0 it waits until the spawn loads or the
        # user stops; a positive value caps the wait and then moves to the next entry.
        # Popups that appear meanwhile (speed warning after the teleport) are cleared.
        start = time.monotonic()
        next_log = start + cfg.spawn_wait_log
        loaded = None
        while not self.stop_event.is_set():
            self._wait_if_paused()
            frame = self.device.screenshot(next_frame=True)
            target = self._target_in_bar(frame)
            if target:
                loaded = target
                break
            if self._drain_popups(frame):
                continue
            now = time.monotonic()
            if cfg.spawn_timeout and now - start >= cfg.spawn_timeout:
                break
            if self._on_waiting is not None and now >= next_log:
                next_log = now + cfg.spawn_wait_log
                self._on_waiting(int(now - start))
        if loaded is None:
            self.stats.last_event = "nospawn"
            return "nospawn"
        # Step 3: keep this QuickSniper item pending through the bounded no-answer retry.
        # It advances only after an encounter, a toast, or repeated confirmed map taps.
        self._queue_pending(loaded)
        outcome = self._attempt_nearby(loaded)
        if outcome not in KEEP_PENDING:
            self._release_pending()
        return outcome

    def _grade_encounter(self, confirmed_frame=None) -> str:
        """We're inside a shiny encounter; compare its exact IV with the configured target."""
        cfg = self.config
        frame = confirmed_frame
        if frame is None:
            # Live H.264 detections are candidates only. A separate one-shot ADB frame
            # must still show the Berry button before a shiny is counted or reported.
            frame = self.device.screenshot(fresh=True)
            if not self._encounter_visible(frame):
                self.stats.last_event = "miss"
                return "miss"

        self.stats.checked += 1
        self.stats.shinies += 1
        self.stats.last_ivs = None
        for attempt in range(cfg.iv_read_tries):
            if self.stop_event.is_set():
                return "shiny"
            # The normal stream is intentionally half-resolution for smooth MuMu
            # operation. A rare shiny gets a crisp one-shot frame for tiny IV glyphs.
            iv_stats = self._read_iv_stats(frame)
            if iv_stats is not None:
                self.stats.last_ivs = iv_stats
            if iv_stats == tuple(cfg.target_ivs):
                self.stats.shundos += 1
                self.stats.last_event = "shundo"
                return "shundo"
            if iv_stats is not None:
                self.stats.last_event = "shiny"
                return "shiny"
            if attempt + 1 < cfg.iv_read_tries:
                self._interruptible_sleep(0.4)
                frame = self.device.screenshot(fresh=True)
        # Never flee a shiny whose IV could not be read: it might be the requested target.
        self.stats.last_event = "iv_unknown"
        return "iv_unknown"

    def run(self, on_event=None) -> None:
        """Blocking loop. on_event(stats, outcome) fires after every cycle."""
        cfg = self.config
        self.stop_event.clear()
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            outcome = self.run_once()
            if on_event:
                on_event(self.stats, outcome)
            if outcome == "goplus":
                # Every shundo cycle teleports, and the Go Plus warning refuses every one of
                # them. There is nothing to fall back on, so end the run instead of looping
                # tap -> warning -> CANCEL; the caller reports why.
                break
            if outcome == "shundo":
                # Full shundo: hand it to the user. "pause" waits for Resume; "stop" ends the loop.
                if cfg.shundo_action == "stop":
                    break
                self.pause_event.set()
            elif outcome == "shiny":
                if cfg.shiny_action == "skip":
                    # Different IV — leave this shiny (flee the encounter) and keep hunting.
                    # on_event has already fired, so the Discord screenshot alert still goes out.
                    # Do not advance QuickSniper until the map return is visually confirmed.
                    fled = self._flee_to_map()
                    if fled is None:
                        self.stats.last_event = "stopped"
                        break
                    self.stats.last_event = "fled" if fled else "flee_failed"
                    if on_event:
                        on_event(self.stats, self.stats.last_event)
                    if not fled:
                        # Continuing here could tap the next feed entry over an encounter
                        # or transition screen. Stop safely and make the failure explicit.
                        break
                elif cfg.shundo_action == "stop":
                    break
                else:
                    self.pause_event.set()
            elif outcome == "iv_unknown":
                self.pause_event.set()

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    # -- live-view annotation --------------------------------------------------------
    def annotate(self, frame, canvas=None):
        """The routine's detections drawn for the GUI's live view: feed tap spot, nearby '@'
        first slot (the double-tap target) and its state, the IV pill region and the
        blocked-toast region.

        Detection runs against `frame`; the drawing goes onto `canvas`, which defaults to a
        copy of the frame. A blank canvas gives an overlay layer the caller can composite onto
        live frames instead of paying for this pass on every displayed frame."""
        import cv2
        cfg = self.config
        img = frame.copy() if canvas is None else canvas

        slot = self._feed_slot_in(frame)
        if slot is not None:
            cv2.circle(img, slot, 45, (0, 220, 0), 6)
            cv2.putText(img, "FEED TAP", (slot[0] + 55, slot[1] + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 220, 0), 3)

        anchor = self._anchor_in(frame)
        if anchor is not None:
            ax, ay = anchor
            busy = self._target_in_bar(frame)
            sx, sy = busy if busy else self._nearby_slot(frame, anchor)
            half = cfg.slot_patch // 2
            x0, y0 = sx - half, sy - half
            color = (255, 255, 0)
            cv2.rectangle(img, (x0, y0), (x0 + cfg.slot_patch, y0 + cfg.slot_patch), color, 5)
            cv2.putText(img, "DBL TAP" if busy else "EMPTY", (x0 - 260, y0 + 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            cv2.drawMarker(img, (sx, sy), (0, 255, 255), cv2.MARKER_CROSS, 80, 6)
            cv2.circle(img, (ax, ay), 40, color, 4)

        px, py, pw, ph = cfg.pill_region
        cv2.rectangle(img, (px, py), (px + pw, py + ph), (0, 165, 255), 4)
        cv2.putText(img, "IV", (px, py - 12), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 165, 255), 3)
        tx, ty, tw, th = cfg.toast_region
        cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (255, 255, 255), 3)

        if self._encounter_visible(frame):
            cv2.putText(img, "ENCOUNTER (SHINY)", (60, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4)
        if self._enc_berry_at is not None:
            berry_x, berry_y = self._enc_berry_at
            cv2.circle(img, (berry_x, berry_y), cfg.enc_berry_radius, (0, 255, 0), 4)
            cv2.putText(img, "BERRY", (berry_x - cfg.s(70),
                                       berry_y - cfg.enc_berry_radius - cfg.s(12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        return img
