"""Shundo-checking routine (shiny + 100% IV).

Separate from the catch routine. Relies on PGSharp's own shiny check being enabled:
attempting to encounter a non-shiny is blocked by PGSharp (a 1-second
"blocked(non-shiny) IV:xx" toast), so an encounter that actually opens IS a shiny.

Per cycle:
  1. Tap the first slot of the PGSharp *feed* sidebar (the bar with the RSS icon at its
     bottom). PGSharp teleports to that spawn.
  2. Wait for the spawn to load, then double-tap the first slot of the nearby '@' bar —
     the same gesture the catch routine uses — to request the encounter.
  3. If no encounter opens within the timeout, PGSharp blocked it (non-shiny): move on.
  4. If an encounter opens, the Pokémon is shiny. Read PGSharp's info pill
     ("▼ L28 IV55 14/2/9 ⚡") and look for the sub-IV string 15/15/15:
       - found  -> SHUNDO: report it and (by default) pause so the user catches manually.
       - absent -> plain shiny: report (optional) and flee, then continue.

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
    slot_offset_y: int = 770        # '@' anchor -> first slot center (same as catch mode)
    slot_patch: int = 110           # square patch size inspected at the slot
    slot_busy_std: float = 30.0     # gray std above this = a Pokémon icon is present
    # A far teleport makes the game reload spawns, which clears the nearby bar first.
    # Waiting for that clear keeps a stale entry from the previous location from being
    # mistaken for the new spawn (the icons all look alike on event days). If the bar
    # never clears (short hop), proceed after this cap.
    bar_clear_timeout: float = 10.0
    # Loading can be slow — keep waiting for the spawn rather than skipping the target.
    # The instant it shows in the bar the tap goes out; this cap only breaks dead waits
    # (e.g. the spawn despawned while we were on the way).
    spawn_timeout: float = 60.0

    # The teleported-to Pokémon stands at the character's feet — a fixed screen point on
    # the map — so the first taps go straight there the moment the spawn is loaded.
    # Only if those miss (the walker carried us off the spawn) do later attempts aim at
    # the nearest white spawn ring instead. Pokéstop discs also draw white rings, but
    # always two of them stacked vertically — such pairs are dropped.
    feet_xy: tuple[int, int] = (612, 1770)
    fixed_taps: int = 2             # attempts aimed at the fixed feet point first
    feet_offsets: tuple[tuple[int, int], ...] = (
        (0, 0), (0, -70), (0, 110), (-130, 30), (130, 30), (0, 240),
    )
    ring_search_radius: int = 700   # how far from the feet to look for spawn rings
    ring_bounds: tuple[int, int, int, int] = (120, 1150, 1040, 2350)  # x0, y0, x1, y1 tap-safe area
    max_tap_attempts: int = 6
    tap_answer_wait: float = 1.6    # per-tap wait for the encounter/toast answer

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

    # Encounter flee button (top-left runner icon) — fixed UI position.
    flee_xy: tuple[int, int] = (126, 181)

    # PGSharp's "blocked(non-shiny) IV:xx" toast: a white pill with dark text at the
    # bottom center, visible for ~1s. Seeing it means the check answered "not shiny".
    # Detection requires an actual pill shape WITH dark text inside, so the encounter
    # screen's big white ball (also bright, but textless) can't fake a "blocked".
    toast_region: tuple[int, int, int, int] = (180, 2280, 860, 250)   # x, y, w, h
    toast_pill_w: tuple[int, int] = (350, 850)
    toast_pill_h: tuple[int, int] = (80, 190)

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
    settle_after_flee: float = 2.0
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
    def _spawn_rings(self, frame) -> list[tuple[int, int]]:
        """Centers of white spawn rings near the feet, nearest first.
        Vertically stacked ring pairs (Pokéstop discs) are removed."""
        import cv2
        import numpy as np
        cfg = self.config
        cx, cy = cfg.feet_xy
        r = cfg.ring_search_radius
        x0, y0 = max(0, cx - r), max(0, cy - r)
        roi = frame[y0:cy + r, x0:cx + r]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY)
        bw = cv2.dilate(bw, np.ones((9, 9), np.uint8))
        n, _labels, stats, _cents = cv2.connectedComponentsWithStats(bw, 8)
        cands = []
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if not (140 <= w <= 420 and 60 <= h <= 260):
                continue
            if area > w * h * 0.55:     # rings are hollow; reject solid blobs
                continue
            cands.append((x0 + x + w // 2, y0 + y + h // 2))
        # Drop vertical pairs: a Pokéstop disc draws two rings ~75px apart.
        keep = []
        for i, (px, py) in enumerate(cands):
            paired = any(j != i and abs(px - qx) < 40 and abs(py - qy) < 130
                         for j, (qx, qy) in enumerate(cands))
            if paired:
                continue
            bx0, by0, bx1, by1 = cfg.ring_bounds
            if bx0 <= px <= bx1 and by0 <= py <= by1:
                keep.append((px, py))
        keep.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
        return keep

    def _target_in_bar(self, frame) -> bool:
        """True when the nearby '@' bar's first slot shows a Pokémon icon (spawn loaded)."""
        import cv2
        cfg = self.config
        m = find(frame, self._anchor, threshold=cfg.anchor_threshold, scales=(0.9, 1.0, 1.1))
        if not m:
            return False
        ax, ay = m[0].center
        half = cfg.slot_patch // 2
        y0 = max(0, ay - cfg.slot_offset_y - half)
        x0 = max(0, ax - half)
        patch = frame[y0:y0 + cfg.slot_patch, x0:x0 + cfg.slot_patch]
        if patch.size == 0:
            return False
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        return float(gray.std()) > cfg.slot_busy_std

    def _feed_slot_in(self, frame) -> tuple[int, int] | None:
        """First feed slot: the '≡' handle in the RSS icon's column, plus a fixed dy."""
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
        import cv2
        cfg = self.config
        x, y, w, h = cfg.toast_region
        gray = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        n, _labels, stats, _cents = cv2.connectedComponentsWithStats(bw, 8)
        for i in range(1, n):
            cx, cy, cw, ch, area = stats[i]
            if not (cfg.toast_pill_w[0] <= cw <= cfg.toast_pill_w[1]
                    and cfg.toast_pill_h[0] <= ch <= cfg.toast_pill_h[1]):
                continue
            if area < cw * ch * 0.55:          # pills are solid white (minus the text)
                continue
            sub = gray[cy:cy + ch, cx:cx + cw]
            dark = float((sub < 120).mean())   # the "blocked(non-shiny)" text itself
            if 0.02 <= dark <= 0.4:
                return True
        return False

    def _encounter_answer(self, frame) -> str | None:
        """'shiny' when the encounter opened, 'blocked' when PGSharp's toast showed."""
        if self._camera_in(frame):
            return "shiny"
        if self._blocked_toast_in(frame):
            return "blocked"
        return None

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

    # -- gestures -------------------------------------------------------------------
    def flee(self) -> None:
        self.device.tap(*self.config.flee_xy)
        self._interruptible_sleep(self.config.settle_after_flee)

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

        # Step 1: teleport to the next feed candidate.
        slot = self._feed_slot_in(frame)
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
        # in the bar's first slot — then tap the Pokémon at the character's feet.
        # Waits patiently (spawns can load slowly); popups that appear meanwhile (speed
        # warning after the teleport) are cleared without giving up on the target.
        deadline = time.monotonic() + cfg.spawn_timeout
        loaded = False
        while time.monotonic() < deadline and not self.stop_event.is_set():
            self._wait_if_paused()
            if self._target_in_bar(self.device.screenshot()):
                loaded = True
                break
            if self._handle_popups():
                self._interruptible_sleep(0.8)
                continue
            time.sleep(cfg.poll_interval)
        if not loaded:
            self.stats.last_event = "nospawn"
            return "nospawn"
        answer = None
        for attempt in range(cfg.max_tap_attempts):
            if self.stop_event.is_set():
                return "idle"
            if attempt < cfg.fixed_taps:
                # The character's feet are a fixed screen point — tap straight there.
                dx, dy = cfg.feet_offsets[attempt % len(cfg.feet_offsets)]
                tx, ty = cfg.feet_xy[0] + dx, cfg.feet_xy[1] + dy
            else:
                # Missed — the walker likely carried us off the spawn. Aim at the
                # nearest spawn ring instead (re-detected each try: Pokémon wander).
                rings = self._spawn_rings(self.device.screenshot())
                if rings:
                    tx, ty = rings[min(attempt - cfg.fixed_taps, len(rings) - 1)]
                else:
                    dx, dy = cfg.feet_offsets[attempt % len(cfg.feet_offsets)]
                    tx, ty = cfg.feet_xy[0] + dx, cfg.feet_xy[1] + dy
            self.device.tap(tx, ty)
            answer = self._poll(self._encounter_answer, cfg.tap_answer_wait)
            if answer:
                break
        if answer is None:
            self.stats.last_event = "miss"
            return "miss"
        self.stats.checked += 1

        # Step 3: shiny check happens inside PGSharp. Encounter open = shiny.
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
            if outcome == "shundo":
                # Leave the encounter open for the user. "pause" waits for Resume;
                # "stop" ends the loop entirely.
                if cfg.shundo_action == "stop":
                    break
                self.pause_event.set()
            elif outcome == "shiny":
                self.flee()

    def stop(self) -> None:
        self.stop_event.set()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()
