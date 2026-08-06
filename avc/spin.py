"""PokéStop spinning mode: walk, and tap every unspun stop that comes within reach.

The whole feature rests on one fact about how Pokémon GO draws the map: a stop that can still
be spun is a single flat, very bright blue, and a stop already spun turns violet. So the colour
test is also the "worth tapping" test — no template, no key, no Go Plus (see
`vision.find_pokestops` for the measured HSV window and why map water needs a brightness floor
to stay out of it).

The loop itself is deliberately thin. Everything it needs — popup handling, AutoWalk restarts,
render-scale calibration, the encounter test — already exists on `CatchRoutine` and is used
here unchanged, so this file only decides the *order*:

  1. clear whatever is blocking the screen (PGSharp raises its "Stop AutoWalk?" dialog after
     every touch that reaches the map, so this runs constantly, not occasionally);
  2. leave any encounter that opened behind our back — a Go Plus catch or a stray tap — because
     the encounter screen covers the map entirely and nothing below can see a stop;
  3. make sure the walk is running, once, at the start;
  4. tap the biggest unspun stop inside the scan circle.

Step 3 happens once per run and never again, which is the whole difference from the catch
routine. There, an empty cycle means the spawns dried up and walking somewhere else is the fix.
Here it only means no stop is in reach yet — stops do not appear because you walked, they stand
where they stand. Re-tapping that row every empty cycle could therefore achieve exactly one
thing: stopping a walk that was running fine.
"""
from __future__ import annotations

import time

from .catch import CatchConfig, CatchRoutine
from .device import Device


class SpinRoutine(CatchRoutine):
    """Tap PokéStops while AutoWalk carries the avatar past them."""

    # How many cycles to spend looking for the AutoWalk row before dropping the question. The
    # row only exists while the PGSharp menu is expanded, and a collapsed menu is a perfectly
    # normal way to play — scanning for it forever would cost a template sweep every cycle to
    # answer a question that already has an answer: the player's walk is their own business.
    WALK_CHECK_CYCLES = 8

    def __init__(self, device: Device, config: CatchConfig | None = None) -> None:
        super().__init__(device, config)
        # This mode never throws a ball, so an encounter is only ever in the way.
        self._autowalk_active = False
        self._walk_checks_left = self.WALK_CHECK_CYCLES

    def _ensure_walking(self, frame) -> bool:
        """Start AutoWalk if it is visibly stopped. True once the question is settled.

        Only ever taps a row that is *showing* the paused '⊘'. `_try_autowalk` will also aim by
        a remembered offset below the menu star when the row icon cannot be read, which is right
        for the catch routine — it re-checks constantly and a missed walk costs it spawns — but
        wrong here: an unverified tap on a running row raises "Stop AutoWalk?" and, answered
        CANCEL, leaves the walk stopped. Unreadable means unknown, and unknown means try again
        next cycle rather than guess.
        """
        row = self._autowalk_row_in(frame, self._star_in(frame))
        if row is None:
            return False
        target, paused = row
        if paused is not True:
            self._autowalk_active = True
            self._trace("spin_walk_running", "AutoWalk đang chạy; không đụng vào.", 0.0)
            return True
        self.device.tap(*target)
        self._autowalk_active = True
        self.stats.autowalks += 1
        self._trace("spin_walk_start",
                    f"AutoWalk đang dừng; bấm một lần tại {target} rồi thôi.", 0.0)
        return True

    def _leave_encounter(self) -> None:
        """Tap Flee until the encounter screen is gone.

        Sent over plain adb on a fresh control session for the same reason the catch routine
        does it: MuMu can keep stale pointer state on the scrcpy socket and swallow the tap.
        """
        cfg = self.config
        self.device.close_control()
        for attempt in range(max(1, cfg.flee_taps)):
            if self.stop_event.is_set():
                return
            self.device.adb_tap(*cfg.flee_xy)
            if attempt + 1 < max(1, cfg.flee_taps):
                self._interruptible_sleep(max(0.25, cfg.flee_gap_ms / 1000.0))

    def run_once(self) -> bool:
        """One spin cycle. True if a PokéStop was tapped."""
        self.stats.cycles += 1
        # run() reads this back to decide what to report, so it must describe *this* cycle
        # rather than whatever the last one left behind.
        self.stats.last_event = ""
        self._ensure_calibrated()
        frame = self.device.screenshot()

        if self._drain_popups(frame):
            return False

        # Strict: on the map alone a lone ball-selector reading is far more likely to be a
        # leftover frame than a real encounter, and fleeing one that isn't there taps the
        # top-left corner of the map — which PGSharp answers with another dialog.
        if self._in_encounter(frame, strict=True):
            self._trace("spin_encounter",
                        "Có encounter đang mở che mất map; thoát ra để quay stop tiếp.", 0.0)
            self._leave_encounter()
            return False

        # Asked once at the start, then dropped for the rest of the run — see the module docstring.
        if self._walk_checks_left > 0:
            self._walk_checks_left -= 1
            if self._ensure_walking(frame):
                self._walk_checks_left = 0

        return self.spin_once(frame)

    def run(self, on_event=None) -> None:
        """Blocking loop. Honors stop_event / pause_event so a GUI can drive it in a thread."""
        cfg = self.config
        self.stop_event.clear()
        while not self.stop_event.is_set():
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            spun = self.run_once()
            self.stats.last_event = "spin" if spun else "idle"
            if on_event:
                on_event(self.stats, spun)
            self._interruptible_sleep(cfg.spin_interval if spun else cfg.idle_poll)

    # -- live-view annotation --------------------------------------------------------
    def annotate(self, frame, canvas=None):
        """Draw the scan circle and every stop found in it, so the preview window shows exactly
        what the mode is aiming at before it taps anything."""
        import cv2  # local: annotate is only ever called from the GUI preview

        cfg = self.config
        img = frame if canvas is None else canvas
        x, y, w, h = cfg.spin_region
        cv2.ellipse(img, (x + w // 2, y + h // 2), (w // 2, h // 2), 0, 0, 360,
                    (0, 220, 255), 3)
        for i, m in enumerate(self.find_stops(frame)):
            colour = (0, 255, 0) if i == 0 else (255, 200, 0)
            cv2.rectangle(img, (m.x, m.y), (m.x + m.width, m.y + m.height), colour, 4)
            cv2.drawMarker(img, m.center, colour, cv2.MARKER_CROSS, cfg.s(40), 3)
        return img
