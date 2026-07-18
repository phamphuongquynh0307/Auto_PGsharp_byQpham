"""Shundo-checking routine (shiny + 100% IV).

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
     sub-IV string 15/15/15 decides whether it is announced as a full SHUNDO.

The sub-IVs are read by template-matching the glyphs '1', '5' and '/' inside the pill
region and checking for the exact ordered sequence 1 5 / 1 5 / 1 5 with sane gaps.
The '5' glyph was cropped from the pill's larger IV-percent font, so it is matched at
~0.84 scale to fit the smaller sub-IV font.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .catch import _load_optional, _resolve
from .device import Device
from .vision import find, load_template


@dataclass
class ShundoConfig:
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
    # A far teleport makes the game reload spawns, which clears the nearby bar first.
    # Waiting for that clear keeps a stale entry from the previous location from being
    # mistaken for the new spawn (the icons all look alike on event days). If the bar
    # never clears (short hop), proceed after this cap.
    bar_clear_timeout: float = 10.0
    # Loading can be slow (hot phone, teleport cooldown), so stay put and keep waiting
    # for the spawn instead of teleporting away to another feed entry. 0 = wait until it
    # loads or the user stops (the user's explicit preference); a positive value caps the
    # wait and then moves on. The instant it shows in the bar the double-tap goes out.
    spawn_timeout: float = 0.0
    spawn_wait_log: float = 20.0    # log a "still waiting" heartbeat this often (s)

    # The encounter is requested by ONE double-tap of the bar's first slot (same gesture
    # as the catch routine). The reliable "shiny" signal is the encounter's camera icon,
    # which appears and stays; we wait up to encounter_open_wait for it and never re-tap
    # (a second double-tap would land on the opening encounter screen). No camera in that
    # window ⇒ the Pokémon is non-shiny and we move on.
    encounter_open_wait: float = 3.0

    # Encounter confirmation: the camera icon at the top of the encounter screen.
    camera_template: str = "templates/camera.png"
    camera_threshold: float = 0.7
    camera_region: tuple[int, int, int, int] = (430, 40, 360, 300)

    # PGSharp info pill glyphs for the 15/15/15 check.
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
    # region, so the caller must confirm we're NOT in/opening an encounter first (camera
    # absent AND the '@' bar still visible) before trusting a toast here.
    toast_region: tuple[int, int, int, int] = (150, 2260, 920, 300)   # x, y, w, h
    toast_pill_w: tuple[int, int] = (380, 860)
    toast_pill_h: tuple[int, int] = (85, 210)
    toast_fill: float = 0.7          # min filled fraction of the pill's bounding box
    toast_center_tol: int = 320      # max |pill center x - screen center x|

    # PGSharp menu accidentally left open (it occludes the map and eats taps):
    # detected via its Settings-gear icon, closed by tapping the yellow menu star.
    menu_open_template: str = "templates/pgsharp_menu.png"
    menu_star_template: str = "templates/menu_star.png"

    # Popups. Teleporting long distances reliably triggers the speed warning.
    popup_speed_template: str = "templates/popup_speed.png"
    close_btn_template: str = "templates/close_btn.png"
    close_btn_blue_template: str = "templates/close_btn_blue.png"
    close_btn_white_template: str = "templates/close_btn_white.png"
    popup_threshold: float = 0.7

    # Timing (seconds).
    teleport_wait: float = 4.0      # after the feed tap, let spawns + nearby bar load
    poll_interval: float = 0.15
    idle_poll: float = 1.5          # pause between cycles when the feed bar is missing

    # What to do when a shundo is found: "pause" (default) or "stop".
    shundo_action: str = "pause"


@dataclass
class ShundoStats:
    cycles: int = 0
    checked: int = 0    # encounter attempts (double-taps that got an answer)
    shinies: int = 0    # encounters that actually opened
    shundos: int = 0
    last_event: str = ""  # "blocked" | "shiny" | "shundo" | "miss" | "nospawn" | "idle" | "popup"


class ShundoRoutine:
    def __init__(self, device: Device, config: ShundoConfig | None = None) -> None:
        self.device = device
        self.config = config or ShundoConfig()
        self._rss = load_template(_resolve(self.config.feed_rss_template))
        self._handle = load_template(_resolve(self.config.bar_handle_template))
        self._anchor = load_template(_resolve(self.config.anchor_template))
        self._camera = load_template(_resolve(self.config.camera_template))
        self._g1 = load_template(_resolve(self.config.glyph_1_template))
        self._g5 = load_template(_resolve(self.config.glyph_5_template))
        self._gs = load_template(_resolve(self.config.glyph_slash_template))
        self._menu_open = _load_optional(self.config.menu_open_template)
        self._menu_star = _load_optional(self.config.menu_star_template)
        self._popup_speed = _load_optional(self.config.popup_speed_template)
        self._close_btns = [
            b for b in (
                _load_optional(self.config.close_btn_template),
                _load_optional(self.config.close_btn_blue_template),
                _load_optional(self.config.close_btn_white_template),
            ) if b is not None
        ]
        self.stats = ShundoStats()
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
            result = predicate(self.device.screenshot())
            if result:
                return result
            if time.monotonic() >= deadline:
                return None
            time.sleep(self.config.poll_interval)

    # -- element lookups ---------------------------------------------------------
    def _anchor_in(self, frame) -> tuple[int, int] | None:
        m = find(frame, self._anchor, threshold=self.config.anchor_threshold, scales=(0.9, 1.0, 1.1))
        return m[0].center if m else None

    def _target_in_bar(self, frame) -> bool:
        """True when a Pokémon icon is present anywhere in the nearby '@' bar (spawn
        loaded). Scans the whole bar column and takes the busiest band, so it doesn't
        depend on the spawn sitting at one exact slot."""
        import cv2
        cfg = self.config
        anchor = self._anchor_in(frame)
        if anchor is None:
            return False
        ax, ay = anchor
        x0, x1 = max(0, ax - cfg.bar_half_w), ax + cfg.bar_half_w
        for top in range(ay - cfg.bar_scan_top, ay - cfg.bar_scan_bottom, cfg.bar_scan_step):
            patch = frame[max(0, top):top + cfg.slot_patch, x0:x1]
            if patch.size == 0:
                continue
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            if float(gray.std()) > cfg.slot_busy_std:
                return True
        return False

    def _feed_slot_in(self, frame) -> tuple[int, int] | None:
        """First feed slot. The feed is a QUEUE: tapping the top entry teleports to it and
        removes it, so the next spawn shifts up into the top slot — we always tap slot 1.
        Located as the '≡' handle in the RSS icon's column, plus a fixed dy."""
        cfg = self.config
        rss = find(frame, self._rss, threshold=cfg.feed_threshold, scales=(0.9, 1.0, 1.1))
        if not rss:
            return None
        rx, _ry = rss[0].center
        handles = find(frame, self._handle, threshold=cfg.feed_threshold, scales=(0.9, 1.0, 1.1))
        for h in handles:
            hx, hy = h.center
            if abs(hx - rx) <= cfg.handle_column_tol:
                return (rx, hy + cfg.feed_slot_dy)
        return None

    def _camera_in(self, frame) -> bool:
        return bool(find(frame, self._camera, threshold=self.config.camera_threshold,
                         scales=(0.95, 1.0, 1.05), region=self.config.camera_region))

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

    def _handle_popups(self) -> bool:
        frame = self.device.screenshot()
        # PGSharp menu left open — close it by tapping the star it hangs off of.
        if self._menu_open is not None and self._menu_star is not None:
            m = find(frame, self._menu_open, threshold=0.8, scales=(0.95, 1.0, 1.05))
            if m:
                star = find(frame, self._menu_star, threshold=0.7, scales=(0.9, 1.0, 1.1), grayscale=False)
                if star:
                    self.device.tap(*star[0].center)
                    self.stats.last_event = "popup"
                    return True
        if self._popup_speed is not None:
            m = find(frame, self._popup_speed, threshold=self.config.popup_threshold, scales=(1.0,))
            if m:
                self.device.tap(*m[0].center)
                self.stats.last_event = "popup"
                return True
        # Never tap a close button while an encounter is up — that region overlaps game UI.
        # A stray Pokéstop screen is closed by its templated X as well; no blind fixed-spot
        # tap here: the catch routine's "two blue side patches" heuristic false-positives on
        # water-heavy maps and would press the map's pokeball menu instead.
        if not self._camera_in(frame):
            for btn in self._close_btns:
                m = find(frame, btn, threshold=self.config.popup_threshold,
                         scales=(0.9, 1.0, 1.1), region=(400, 2000, 420, 712))
                if m:
                    self.device.tap(*m[0].center)
                    self.stats.last_event = "popup"
                    return True
        return False

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

    # -- main loop --------------------------------------------------------------------
    def run_once(self) -> str:
        """One check cycle. Returns the outcome:
        blocked | shiny | shundo | miss | nospawn | idle | popup."""
        cfg = self.config
        self.stats.cycles += 1

        if self._handle_popups():
            self._interruptible_sleep(1.0)
            return "popup"

        # An encounter already open at cycle start is a shiny whose answer we missed
        # (it can open a beat after the per-tap wait gave up — PGSharp hides both bars
        # while it's up, so this must be checked before looking for the feed). Grade it
        # now instead of idling forever.
        frame = self.device.screenshot()
        if self._camera_in(frame):
            self.stats.checked += 1
            return self._grade_encounter()

        # Step 1: teleport to the next feed candidate. A miss on the stream frame is
        # retried on a crisp one-shot capture first — H.264 smear between keyframes
        # periodically drops the small RSS/handle templates below threshold.
        slot = self._feed_slot_in(frame)
        if slot is None:
            slot = self._feed_slot_in(self.device.screenshot(fresh=True))
        if slot is None:
            self._interruptible_sleep(cfg.idle_poll)
            self.stats.last_event = "idle"
            return "idle"
        self.device.tap(*slot)
        self._interruptible_sleep(cfg.teleport_wait)
        if self.stop_event.is_set():
            return "idle"

        # Teleporting far reliably raises the speed warning — clear it before tapping on.
        if self._handle_popups():
            self._interruptible_sleep(1.0)

        # Step 2a: the far teleport reloads spawns and empties the nearby '@' bar.
        # Wait for that clear first, so an entry left over from the previous location
        # can't be mistaken for the new spawn.
        clear_deadline = time.monotonic() + cfg.bar_clear_timeout
        while time.monotonic() < clear_deadline and not self.stop_event.is_set():
            self._wait_if_paused()
            if not self._target_in_bar(self.device.screenshot()):
                break
            if self._handle_popups():
                self._interruptible_sleep(0.8)
                continue
            time.sleep(cfg.poll_interval)

        # Step 2b: wait until the game actually loads the spawn — the Pokémon shows up
        # in the bar's first slot. Stays put and waits (spawns can load slowly); it does
        # NOT teleport away. With spawn_timeout == 0 it waits until the spawn loads or the
        # user stops; a positive value caps the wait and then moves to the next entry.
        # Popups that appear meanwhile (speed warning after the teleport) are cleared.
        start = time.monotonic()
        next_log = start + cfg.spawn_wait_log
        loaded = False
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self._target_in_bar(self.device.screenshot()):
                loaded = True
                break
            if self._handle_popups():
                self._interruptible_sleep(0.8)
                continue
            now = time.monotonic()
            if cfg.spawn_timeout and now - start >= cfg.spawn_timeout:
                break
            if self._on_waiting is not None and now >= next_log:
                next_log = now + cfg.spawn_wait_log
                self._on_waiting(int(now - start))
            time.sleep(cfg.poll_interval)
        if not loaded:
            self.stats.last_event = "nospawn"
            return "nospawn"
        # Step 3: double-tap the bar's first slot ONCE, then watch for the camera icon —
        # the decisive shiny signal (it appears and stays). Camera up ⇒ shiny. No camera
        # within the window ⇒ non-shiny; move on. Never a second double-tap: it would land
        # on the opening encounter screen (the stray taps the user was seeing).
        frame = self.device.screenshot()
        if self._camera_in(frame):
            answer = "shiny"
        else:
            anchor = self._anchor_in(frame)
            if anchor is not None:
                self.device.double_tap(anchor[0], anchor[1] - cfg.slot_offset_y)
            answer = "shiny" if self._poll(self._camera_in, cfg.encounter_open_wait) else "blocked"
        self.stats.checked += 1

        if answer == "blocked":
            self.stats.last_event = "blocked"
            return "blocked"

        # Step 4: shiny confirmed — grade the IVs off the info pill.
        return self._grade_encounter()

    def _grade_encounter(self) -> str:
        """We're inside an open encounter — a shiny. Read the pill; shundo = 15/15/15."""
        cfg = self.config
        self.stats.shinies += 1
        for _ in range(cfg.iv_read_tries):
            if self.stop_event.is_set():
                return "shiny"
            if self._is_hundo(self.device.screenshot()):
                self.stats.shundos += 1
                self.stats.last_event = "shundo"
                return "shundo"
            self._interruptible_sleep(0.4)
        self.stats.last_event = "shiny"
        return "shiny"

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
            if outcome in ("shundo", "shiny"):
                # Any shiny is left open for the user to handle. "pause" waits for
                # Resume; "stop" ends the loop entirely.
                if cfg.shundo_action == "stop":
                    break
                self.pause_event.set()

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    # -- live-view annotation --------------------------------------------------------
    def annotate(self, frame):
        """Copy of `frame` with the routine's detections drawn on it, for the GUI's
        live view: feed tap spot, nearby '@' first slot (the double-tap target) and its
        state, the IV pill region and the blocked-toast region."""
        import cv2
        cfg = self.config
        img = frame.copy()

        slot = self._feed_slot_in(frame)
        if slot is not None:
            cv2.circle(img, slot, 45, (0, 220, 0), 6)
            cv2.putText(img, "FEED TAP", (slot[0] + 55, slot[1] + 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 220, 0), 3)

        anchor = self._anchor_in(frame)
        if anchor is not None:
            ax, ay = anchor
            half = cfg.slot_patch // 2
            x0, y0 = ax - half, ay - cfg.slot_offset_y - half
            busy = self._target_in_bar(frame)
            color = (255, 255, 0)
            cv2.rectangle(img, (x0, y0), (x0 + cfg.slot_patch, y0 + cfg.slot_patch), color, 5)
            cv2.putText(img, "DBL TAP" if busy else "EMPTY", (x0 - 260, y0 + 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            cv2.drawMarker(img, (ax, ay - cfg.slot_offset_y), (0, 255, 255), cv2.MARKER_CROSS, 80, 6)
            cv2.circle(img, (ax, ay), 40, color, 4)

        px, py, pw, ph = cfg.pill_region
        cv2.rectangle(img, (px, py), (px + pw, py + ph), (0, 165, 255), 4)
        cv2.putText(img, "IV", (px, py - 12), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 165, 255), 3)
        tx, ty, tw, th = cfg.toast_region
        cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (255, 255, 255), 3)

        if self._camera_in(frame):
            cv2.putText(img, "ENCOUNTER (SHINY)", (60, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 255), 4)
        return img
