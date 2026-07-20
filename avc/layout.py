"""Resolution- and aspect-independent coordinate mapping.

The game/PGSharp UI is *edge-anchored*: icons hug a screen edge or corner and keep a
fixed dp size while the map stretches in the middle. Scaling a coordinate proportionally
from the top-left corner (x·w/W0, y·h/H0) therefore only lines up when the aspect ratio
matches the one the coordinates were authored on — a bottom-anchored button drifts on a
taller/shorter screen.

Here every fixed coordinate is authored in BASE_RESOLUTION pixels *plus an anchor* naming
the edge/corner it is measured from. `Layout` re-anchors it to any device:

  * horizontal L → from left, C → from screen centre, R → from right edge
  * vertical    T → from top,  M → from screen centre, B → from bottom edge

A single UI scale `s` drives everything. The game/PGSharp UI is laid out in **dp**, so a
dp-sized icon or a dp offset from an edge occupies `dp · density / 160` pixels — its pixel
size depends on the screen's *density*, not its pixel width. The correct factor is therefore
the density ratio `s = density / base_density`. (Width ratio only equals this when density
happens to scale with width — true if you shrink a display proportionally, but false across
real phones, where a narrower screen often keeps the same density and drifts by width·%.)

When the device density is unknown, `s` falls back to the old width ratio `width / base_width`.
Pure distances/sizes (swipe lengths, search radii, glyph gaps) use `scale()`.

`resize_template` rescales a template bitmap by the same `s` so template matching still
finds an icon that renders bigger/smaller on a denser/sparser screen.
"""
from __future__ import annotations

import cv2
import numpy as np

BASE_RESOLUTION: tuple[int, int] = (1220, 2712)
BASE_DENSITY: int = 480   # dpi the BASE_RESOLUTION coordinates were authored at


class Layout:
    """Maps BASE_RESOLUTION coordinates onto a device of size (width, height).

    Pass the device `density` (dpi) for correct dp-based scaling on any aspect ratio; omit it
    to fall back to width-ratio scaling (only exact when density scales with width)."""

    def __init__(self, width: int, height: int, density: int | None = None,
                 base: tuple[int, int] = BASE_RESOLUTION, base_density: int = BASE_DENSITY) -> None:
        self.w, self.h = int(width), int(height)
        self.bw, self.bh = base
        # dp-anchored UI scales with density; edge anchoring below uses the real w/h.
        self.s = (density / base_density) if density else (self.w / self.bw)

    def scale(self, v: float) -> int:
        """Scale a pure distance or size (no anchoring)."""
        return int(round(v * self.s))

    def _mx(self, x: float, ah: str) -> int:
        if ah == "L":
            return int(round(x * self.s))
        if ah == "R":
            return self.w - int(round((self.bw - x) * self.s))
        # C: measured from the horizontal centre
        return int(round(self.w / 2 + (x - self.bw / 2) * self.s))

    def _my(self, y: float, av: str) -> int:
        if av == "T":
            return int(round(y * self.s))
        if av == "B":
            return self.h - int(round((self.bh - y) * self.s))
        # M: measured from the vertical centre
        return int(round(self.h / 2 + (y - self.bh / 2) * self.s))

    def point(self, p: tuple[int, int], anchor: str) -> tuple[int, int]:
        """Map an absolute (x, y). `anchor` is vertical+horizontal, e.g. 'BC', 'TL', 'TR'."""
        av, ah = anchor[0], anchor[1]
        return (self._mx(p[0], ah), self._my(p[1], av))

    def region(self, r: tuple[int, int, int, int], anchor: str) -> tuple[int, int, int, int]:
        """Map a box (x, y, w, h): its (x, y) corner is anchored; w and h are scaled."""
        x, y, w, h = r
        px, py = self.point((x, y), anchor)
        return (px, py, self.scale(w), self.scale(h))


# Wide one-time sweep used to *measure* the device's real UI render scale (self-calibration).
CALIBRATION_SWEEP: tuple[float, ...] = tuple(round(0.40 + 0.05 * i, 2) for i in range(17))  # 0.40..1.20


def scales_around(s: float, spread: float = 0.16, steps: int = 5) -> tuple[float, ...]:
    """A tight bracket of match scales centred on a *measured* render scale `s`, with enough
    spread (±spread) to absorb small differences between UI layers (e.g. the PGSharp overlay
    vs the game's own dialogs)."""
    lo, hi = s * (1 - spread), s * (1 + spread)
    return tuple(round(lo + (hi - lo) * i / (max(2, steps) - 1), 3) for i in range(max(2, steps)))


def bracket_scales(s: float, steps: int = 4) -> tuple[float, ...]:
    """Template-match scale multipliers that bracket the uncertainty in how the game renders
    UI on a non-base device: some elements scale with the screen (factor ~`s`), others keep
    their base pixel size (factor 1.0) — Pokémon GO/PGSharp don't reliably re-layout under a
    resolution override, so we can't assume either. Sweeping the whole span (plus a small
    margin) catches the icon whichever way it rendered. Collapses to a tight sweep near 1.0 on
    the base device (s≈1), so base behaviour is unchanged."""
    if abs(s - 1.0) < 1e-3:
        return (0.94, 1.0, 1.06)          # base device: tight sweep around 1.0
    lo, hi = (s, 1.0) if s < 1.0 else (1.0, s)
    # Even spread across [lo, hi] plus the exact endpoints (the two most likely renders:
    # UI scaled by s, or not scaled at all) and a small margin either side.
    inner = [lo + (hi - lo) * i / (max(2, steps) - 1) for i in range(max(2, steps))]
    vals = {round(v, 3) for v in ([lo * 0.94] + inner + [hi * 1.06])}
    return tuple(sorted(vals))


def resize_template(img: np.ndarray, s: float) -> np.ndarray:
    """Return `img` rescaled by `s` so it matches how the icon renders on the device.
    A no-op when `s` is ~1. Uses area interpolation shrinking, linear enlarging."""
    if img is None or abs(s - 1.0) < 1e-3:
        return img
    h, w = img.shape[:2]
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(img, (nw, nh), interpolation=interp)
