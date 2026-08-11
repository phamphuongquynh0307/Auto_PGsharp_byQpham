"""Template matching on captured frames.

Given a scene image (a screenshot) and a template image, find where the template appears.
Supports multi-scale search (so a template still matches when the UI renders at a slightly
different size) and returns every match above a similarity threshold with simple
non-maximum suppression so the same spot isn't reported twice.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Match:
    x: int          # top-left in scene coords
    y: int
    width: int
    height: int
    score: float

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


def _to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def find_disconnected_goplus(scene: np.ndarray, *, scale: float = 1.0) -> tuple[int, int] | None:
    """Locate Pokémon GO's disconnected accessory button in the upper-right icon rail.

    The rail is dynamic: event buttons come and go, moving Go Plus vertically, so a remembered
    coordinate is unsafe. The disconnected button itself is stable — a muted red upper
    semicircle over a blue-grey lower half with a dark centre. Only the narrow right-edge rail is
    searched, and the red cap must have the measured size/shape of that control. A connected or
    connecting button is deliberately not returned, so callers cannot turn Go Plus back off.
    """
    if scene is None or scene.ndim != 3 or scene.shape[2] < 3:
        return None
    h, w = scene.shape[:2]
    s = max(0.25, float(scale or 1.0))
    # The icon hugs the right edge, while its vertical slot moves as event icons are inserted.
    x0 = max(0, w - int(round(160 * s)))
    y0 = max(0, int(round(100 * s)))
    y1 = min(h, int(round(1100 * s)))
    if x0 >= w or y0 >= y1:
        return None
    roi = scene[y0:y1, x0:w]
    b, g, r = (channel.astype(np.int16) for channel in cv2.split(roi)[:3])
    red = ((r > g + 25) & (r > b + 25) & (r > 110)).astype(np.uint8) * 255
    kernel_size = max(1, int(round(3 * s)))
    red = cv2.morphologyEx(
        red,
        cv2.MORPH_OPEN,
        np.ones((kernel_size, kernel_size), dtype=np.uint8),
    )
    contours, _hierarchy = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, tuple[int, int]]] = []
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        if not (55 * s <= cw <= 105 * s and 20 * s <= ch <= 65 * s):
            continue
        fill = cv2.contourArea(contour) / max(1, cw * ch)
        if fill < 0.35:
            continue
        cx = x0 + x + cw // 2
        # The dark centre sits just below the red cap's bounding box.
        cy = y0 + y + ch + int(round(8 * s))
        radius = max(4, int(round(20 * s)))
        core = scene[max(0, cy - radius):min(h, cy + radius),
                     max(0, cx - radius):min(w, cx + radius)]
        if core.size == 0:
            continue
        dark_fraction = float((core[..., :3].mean(axis=2) < 115).mean())
        if dark_fraction < 0.25:
            continue
        candidates.append((fill + dark_fraction, (cx, cy)))
    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]


# Pokéstop blue, measured off a live 1220x2712 map (HSV, OpenCV ranges).
#
# The window spans hue 88-122 because a stop is drawn in two quite different blues depending on
# how far away it is, and both must match. Far off it is a tall royal-blue pillar at hue 112-113
# with saturation ~200; close up it becomes a turquoise disc over a small cube at hue 90 with
# saturation ~155. A window fitted to the pillar alone found nothing at all on a screen full of
# stops standing right beside the avatar — which is precisely the case this feature exists for.
#
# What the window must keep out is darker, not bluer:
#   * map water sits at hue 114 but value ~188, i.e. clearly dimmer. The brightness floor is the
#     only thing that stops a lake reading as the biggest Pokéstop on screen — the same trap that
#     made _is_pokestop_screen misfire on water-heavy maps;
#   * pale blue Pokémon (a Salamence beside the avatar measured hue 99, saturation 138) are
#     washed out rather than dark, so the saturation floor is what excludes those.
POKESTOP_HSV_LO = (88, 150, 200)
POKESTOP_HSV_HI = (122, 255, 255)


def find_pokestops(
    scene: np.ndarray,
    *,
    region: tuple[int, int, int, int] | None = None,
    scale: float = 1.0,
    min_area: int = 700,
    max_span: int = 400,
) -> list[Match]:
    """Locate unspun Pokéstops by their body colour. Biggest first.

    `region` is an (x, y, w, h) box whose *inscribed ellipse* is the search area — the circle
    around the avatar the user draws in the calibration window. An ellipse rather than the box
    because the map is drawn tilted, so a screen circle around the avatar is the honest shape
    of "near me", and because the box's corners are exactly where the HUD rails live.

    Biggest rather than nearest, because a stop spins non-stop and the rings around it throw off
    bright blue fragments. Ranking by distance let one of those glints win over the very stop it
    belongs to — 120 px to the side of the body, which lands on bare map and earns a PGSharp
    "Stop AutoWalk?" dialog instead of a spin. A fragment is never the biggest blue thing in the
    circle, so ordering by size settles it without having to guess which shapes are legitimate.

    That matters because the shape genuinely varies: the cube turns continuously, so its
    silhouette swings between clearly taller than wide and clearly wider than tall (0.5 to 1.6
    across the frames this was measured on). The aspect window below is therefore deliberately
    loose — wide enough for any rotation of a cube, tight enough that a HUD pill, which is
    several times longer than it is tall, still cannot get in.
    """
    if scene is None or scene.ndim != 3 or scene.shape[2] < 3:
        return []
    h, w = scene.shape[:2]
    s = max(0.25, float(scale or 1.0))
    if region is None:
        region = (0, 0, w, h)
    rx, ry, rw, rh = region
    if rw <= 0 or rh <= 0:
        return []
    # Clip the box to the screen, but keep the *original* ellipse: a box half off the left edge
    # still describes a circle centred on the avatar, and re-centring it on the clipped box
    # would drag the search area sideways.
    cx0, cy0 = rx + rw / 2.0, ry + rh / 2.0
    ax, ay = rw / 2.0, rh / 2.0
    x0, y0 = max(0, int(rx)), max(0, int(ry))
    x1, y1 = min(w, int(rx + rw)), min(h, int(ry + rh))
    if x0 >= x1 or y0 >= y1:
        return []

    roi = scene[y0:y1, x0:x1]
    mask = cv2.inRange(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV),
                       np.array(POKESTOP_HSV_LO, np.uint8),
                       np.array(POKESTOP_HSV_HI, np.uint8))
    # Close over the white highlight band and the pole seam that split one body into pieces.
    k = max(3, int(round(15 * s)))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))

    floor = max(1, int(round(min_area * s * s)))
    span = max(8, int(round(max_span * s)))
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    found: list[tuple[float, Match]] = []
    for i in range(1, count):
        bx, by, bw, bh, area = (int(v) for v in stats[i])
        if area < floor or bw > span or bh > span:
            continue
        if not 0.3 <= bw / max(1, bh) <= 3.0:
            continue
        cx, cy = x0 + float(centroids[i][0]), y0 + float(centroids[i][1])
        if ((cx - cx0) / ax) ** 2 + ((cy - cy0) / ay) ** 2 > 1.0:
            continue
        found.append((area, Match(x0 + bx, y0 + by, bw, bh, area / float(bw * bh))))
    found.sort(key=lambda item: -item[0])
    return [m for _area, m in found]


def find(
    scene: np.ndarray,
    template: np.ndarray,
    *,
    threshold: float = 0.8,
    scales: tuple[float, ...] = (1.0,),
    max_matches: int = 10,
    grayscale: bool = True,
    region: tuple[int, int, int, int] | None = None,
) -> list[Match]:
    """Return matches of `template` in `scene`, best first.

    region: optional (x, y, w, h) to restrict the search area (speeds things up).
    """
    scene_proc = _to_gray(scene) if grayscale else scene
    templ_proc = _to_gray(template) if grayscale else template

    off_x = off_y = 0
    if region is not None:
        rx, ry, rw, rh = region
        rx = max(0, rx); ry = max(0, ry)
        scene_proc = scene_proc[ry:ry + rh, rx:rx + rw]
        off_x, off_y = rx, ry

    results: list[Match] = []
    for scale in scales:
        tw = max(1, int(templ_proc.shape[1] * scale))
        th = max(1, int(templ_proc.shape[0] * scale))
        if tw > scene_proc.shape[1] or th > scene_proc.shape[0] or tw < 8 or th < 8:
            continue
        resized = cv2.resize(templ_proc, (tw, th)) if scale != 1.0 else templ_proc

        result = cv2.matchTemplate(scene_proc, resized, cv2.TM_CCOEFF_NORMED)
        # Repeatedly take the strongest peak and blank its neighborhood.
        work = result.copy()
        for _ in range(max_matches * 3):
            _min_v, max_v, _min_l, max_l = cv2.minMaxLoc(work)
            if max_v < threshold:
                break
            mx, my = max_l
            results.append(Match(mx + off_x, my + off_y, tw, th, float(max_v)))
            x0 = max(0, mx - tw // 2); y0 = max(0, my - th // 2)
            x1 = min(work.shape[1], mx + tw // 2); y1 = min(work.shape[0], my + th // 2)
            work[y0:y1, x0:x1] = 0.0

    return _suppress(results, max_matches)


def find_popup_close(
    scene: np.ndarray,
    templates: list[np.ndarray | None] | tuple[np.ndarray | None, ...],
    *,
    threshold: float = 0.7,
    scales: tuple[float, ...] = (1.0,),
    fallback_scales: tuple[float, ...] = (),
    cache: dict | None = None,
) -> Match | None:
    """Find a modal close X without relying on a particular device resolution.

    Pokemon GO places dismiss X buttons in the lower, horizontally-centred part of the
    viewport.  Expressing that safe area as frame percentages avoids the aspect-ratio
    drift caused by mapping a box authored for one phone.  The normal calibrated scale
    sweep is tried first; a wider sweep is only paid for after it misses.
    """
    height, width = scene.shape[:2]
    x0, y0 = int(width * 0.15), int(height * 0.52)
    x1, y1 = int(width * 0.85), int(height * 0.99)
    region = (x0, y0, x1 - x0, y1 - y0)
    usable = [template for template in templates if template is not None]
    for sweep in (scales, fallback_scales):
        if not sweep:
            continue
        candidates: list[Match] = []
        for template in usable:
            candidates.extend(find_fast(scene, template, threshold=threshold,
                                        scales=sweep, max_matches=1, region=region, cache=cache))
        if candidates:
            return max(candidates, key=lambda match: match.score)

    # Some menus use the same X glyph inside a white disc whose surrounding artwork and
    # shadow changed between game versions.  Matching the old full-button crop then fails
    # even though the X itself is pixel-identical.  Retry only the central glyph in a much
    # tighter bottom-centre region, where Pokemon GO places these close controls.  Keeping
    # this separate from the broad modal search prevents unrelated map art from becoming a
    # tap target.
    gx0, gy0 = int(width * 0.25), int(height * 0.78)
    gx1, gy1 = int(width * 0.75), int(height * 0.99)
    glyph_region = (gx0, gy0, gx1 - gx0, gy1 - gy0)
    for sweep in (scales, fallback_scales):
        if not sweep:
            continue
        candidates = []
        for template in usable:
            th, tw = template.shape[:2]
            glyph = template[th // 4:th - th // 4, tw // 4:tw - tw // 4]
            if glyph.size:
                candidates.extend(find_fast(
                    scene,
                    glyph,
                    threshold=max(0.78, threshold),
                    scales=sweep,
                    max_matches=1,
                    region=glyph_region,
                    cache=cache,
                ))
        if candidates:
            return max(candidates, key=lambda match: match.score)
    return None


def find_fast(
    scene: np.ndarray,
    template: np.ndarray,
    *,
    threshold: float = 0.8,
    scales: tuple[float, ...] = (1.0,),
    max_matches: int = 10,
    grayscale: bool = True,
    region: tuple[int, int, int, int] | None = None,
    reduction: float = 0.3,
    cache: dict | None = None,
) -> list[Match]:
    """A coordinate-preserving, downsampled variant of :func:`find` for large UI controls."""
    height, width = scene.shape[:2]
    if region is None:
        x0, y0, rw, rh = 0, 0, width, height
    else:
        x0, y0, rw, rh = region
        x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width, x0 + rw), min(height, y0 + rh)
    if x1 <= x0 or y1 <= y0:
        return []
    cache_key = (id(scene), x0, y0, x1, y1, reduction)
    search = cache.get(cache_key) if cache is not None else None
    if search is None:
        search = cv2.resize(scene[y0:y1, x0:x1], None, fx=reduction, fy=reduction,
                            interpolation=cv2.INTER_AREA)
        if cache is not None:
            cache[cache_key] = search
    reduced_scales = tuple(scale * reduction for scale in scales)
    matches = find(search, template, threshold=threshold, scales=reduced_scales,
                   max_matches=max_matches, grayscale=grayscale)
    return [Match(
        x=x0 + int(round(match.x / reduction)),
        y=y0 + int(round(match.y / reduction)),
        width=int(round(match.width / reduction)),
        height=int(round(match.height / reduction)),
        score=match.score,
    ) for match in matches]


def slot_has_pokemon(
    scene: np.ndarray,
    center: tuple[int, int],
    *,
    half_width: int,
    height: int,
    min_core_range: float = 50.0,
    min_core_edge: float = 0.055,
    min_edge_prominence: float = 0.0,
    min_foreground_bright_fraction: float = 0.008,
) -> bool:
    """Detect a Pokemon sprite in the exact sidebar slot that will be tapped.

    A translucent empty sidebar inherits colour/variance from the moving map and can easily
    pass a whole-patch standard-deviation test. Pokemon sprites instead produce a compact
    cluster of edges in the middle of the slot.

    The measure is the core's *brightness range* (98th percentile minus 20th), not its standard
    deviation. Deviation fails on a night scene: a dark sprite on a dark sidebar spreads little
    even though its highlights stand out plainly. Range asks the question that actually matters —
    is there something distinctly brighter than the backdrop in the middle of this slot.

    Measured on a 1220x2712 MuMu across 37 slots — 21 holding a sprite in daylight and night
    scenes, 16 empty with the map showing through:

                        range        core std
        sprite        55 .. 217     17.9 .. 84.5
        empty bar      1 ..  74      0.8 .. 27.9

    Standard deviation overlaps badly (a night-scene Combee scores 17.9 while busy map clutter
    reaches 27.9), so no threshold on it can be right: 22.0 missed six real sprites and 31.0
    missed nine. Range overlaps far less, and the threshold is deliberately set at the bottom of
    it rather than the middle.

    That bias is on purpose, because the two errors do not cost the same. A missed sprite idles
    the bot, or walks it away from a Pokémon that was there. A false one costs a double-tap that
    opens nothing and one wasted cycle — it can never throw a ball, because the encounter check
    gates that separately. So the test is tuned to catch every sprite and tolerate the occasional
    phantom, not the other way round.

    Edge *prominence* over the surrounding sidebar reads like it should help and does not: on
    these samples an empty slot scored 0.093 while a real Combee scored 0.037. It stays available
    as a parameter but defaults off.

    There is deliberately no saturation-based alternative. One used to stand in for contrast on
    dark sprites, but map bleed-through is strongly coloured too — it waved through every empty
    slot, which made the main threshold irrelevant.
    """
    cx, cy = center
    y0, y1 = max(0, cy - height // 2), min(scene.shape[0], cy + height // 2)
    x0, x1 = max(0, cx - half_width), min(scene.shape[1], cx + half_width)
    patch = scene[y0:y1, x0:x1]
    if patch.size == 0 or patch.shape[0] < 12 or patch.shape[1] < 12:
        return False
    gray = _to_gray(patch)
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    edges = cv2.Canny(gray, 60, 140) > 0
    h, w = gray.shape[:2]
    core = (slice(h // 6, max(h // 6 + 1, 5 * h // 6)),
            slice(w // 4, max(w // 4 + 1, 3 * w // 4)))
    surround = np.ones(gray.shape, dtype=bool)
    surround[core] = False
    core_edge = float(edges[core].mean())
    side_edge = float(edges[surround].mean()) if surround.any() else 0.0
    core_pixels = gray[core]
    core_range = float(np.percentile(core_pixels, 98) - np.percentile(core_pixels, 20))
    # Objects behind PGSharp's translucent sidebar are uniformly darkened. A Pokémon icon is
    # drawn on top of that layer and retains full-bright pixels. This optional gate rejects
    # detailed gyms/map art bleeding through an empty bar — the live false positive measured
    # 0.0% here, while the real first-slot icon measured 25.3%.
    # HSV value keeps vivid blue/red/yellow sprites eligible even when their grayscale
    # luminance is modest. Map content behind the dark overlay remains below this value.
    foreground_values = hsv[core][..., 2]
    foreground_bright = float((foreground_values >= 175).mean())
    return (
        core_range >= min_core_range
        and core_edge >= min_core_edge
        and core_edge - side_edge >= min_edge_prominence
        and foreground_bright >= max(0.0, float(min_foreground_bright_fraction))
    )


def camera_icon_visible(
    scene: np.ndarray,
    region: tuple[int, int, int, int],
    *,
    min_fill: float = 0.06,
    max_fill: float = 0.45,
    min_value: int = 170,
    max_sat: int = 70,
) -> bool:
    """True when the encounter's camera/AR button occupies `region` (x, y, w, h).

    The button is present in every encounter and absent everywhere else, which makes it a clean
    second opinion on "are we still in an encounter" — the question the red ball-selector alone
    keeps getting wrong just after a Flee.

    It is measured, not template-matched. The glyph is a near-white outline, so what identifies
    it is the fraction of pixels that are bright *and desaturated*. Brightness alone is what sank
    the earlier attempt at this icon: on a bright scene the background is bright too. Saturation
    survives that, because encounter and map backdrops alike (sky, water, grass, city) are
    strongly coloured while the glyph is not.

    The upper bound matters as much as the lower one: a white wall or a blown-out sky fills the
    whole box, and that is a backdrop, not an outline. Measured on a 1220x2712 MuMu — encounter
    19.9% of the box, map 0.0%.
    """
    x, y, w, h = region
    y0, y1 = max(0, y), min(scene.shape[0], y + h)
    x0, x1 = max(0, x), min(scene.shape[1], x + w)
    patch = scene[y0:y1, x0:x1]
    if patch.size == 0 or patch.shape[0] < 8 or patch.shape[1] < 8:
        return False
    gray = _to_gray(patch)
    sat = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[..., 1]
    fill = float(((gray > min_value) & (sat < max_sat)).mean())
    return min_fill <= fill <= max_fill


def find_berry_button(
    scene: np.ndarray,
    *,
    scale: float = 1.0,
    radius: int = 95,
    min_berry_fill: float = 0.06,
) -> tuple[int, int] | None:
    """Find the encounter's bottom-left Berry button and return its actual centre.

    No remembered tap coordinate participates in this search. The bottom-left corner is scanned
    for a compact raspberry-coloured glyph, then the candidate is validated against the pale
    circular button around it. This lets the detector follow UI offsets and resolution changes
    instead of drawing a fixed circle near the control.

    A red ball flying elsewhere is rejected by the corner and component bounds. Map avatar
    details are rejected by the minimum glyph area and the required pale button surround.
    The surround must form a ring on every side at the UI's bottom-anchored position; a
    red/white Pokemon on the map can have the same colour totals, but not that geometry.
    """
    height, width = scene.shape[:2]
    if height < 80 or width < 80:
        return None
    scale = max(0.2, float(scale))
    x0, x1 = 0, int(width * 0.32)
    y0, y1 = int(height * 0.78), int(height * 0.965)
    patch = scene[y0:y1, x0:x1]
    if patch.size == 0:
        return None

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    hue, sat, value = cv2.split(hsv)
    raw_berry = (
        ((hue <= 10) | (hue >= 140))
        & (sat >= 90)
        & (value >= 70)
    )
    kernel_size = max(3, int(round(15 * scale)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    joined = cv2.morphologyEx(raw_berry.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    count, _labels, stats, centres = cv2.connectedComponentsWithStats(joined, 8)

    radius = max(8, int(radius))
    min_area, max_area = 700 * scale * scale, 9000 * scale * scale
    min_side, max_side = 35 * scale, 145 * scale
    candidates: list[tuple[float, tuple[int, int]]] = []
    for i in range(1, count):
        bx, by, bw, bh, area = stats[i]
        if not (min_area <= area <= max_area):
            continue
        if not (min_side <= bw <= max_side and min_side <= bh <= max_side):
            continue
        if not (0.55 <= bw / max(1, bh) <= 1.55):
            continue
        cx = int(round(centres[i][0])) + x0
        cy = int(round(centres[i][1])) + y0
        if cx > width * 0.24:
            continue
        # The game UI anchors this control 245 base pixels above the bottom. A map Pokemon
        # triggered a real false positive 380 base pixels above it, so use the UI anchor as
        # a deliberately generous band rather than allowing the whole bottom quarter.
        expected_bottom = 245.0 * scale
        bottom_tolerance = max(radius * 0.80, 60.0 * scale)
        if abs((height - cy) - expected_bottom) > bottom_tolerance:
            continue

        dx0, dx1 = max(0, cx - radius), min(width, cx + radius + 1)
        dy0, dy1 = max(0, cy - radius), min(height, cy + radius + 1)
        disk_patch = scene[dy0:dy1, dx0:dx1]
        disk_hsv = cv2.cvtColor(disk_patch, cv2.COLOR_BGR2HSV)
        disk_h, disk_s, disk_v = cv2.split(disk_hsv)
        yy, xx = np.ogrid[dy0 - cy:dy1 - cy, dx0 - cx:dx1 - cx]
        disk = xx * xx + yy * yy <= radius * radius
        berry = (
            ((disk_h <= 10) | (disk_h >= 140))
            & (disk_s >= 90)
            & (disk_v >= 70)
            & disk
        )
        berry_fill = float(berry.sum()) / float(disk.sum())
        light = (disk_s < 70) & (disk_v > 150)
        light_fill = float((light & disk).sum()) / float(disk.sum())
        if berry_fill < min_berry_fill or light_fill < 0.20:
            continue

        # A Berry button has a pale circular surround around the central raspberry. Colour
        # totals alone accepted the orange/white head of a bird on the map; its light pixels
        # occupied only one side. Require the outer ring to be both substantial and present
        # in all four quadrants.
        radius_sq = float(radius * radius)
        annulus = disk & (xx * xx + yy * yy >= radius_sq * 0.55 * 0.55)
        if not annulus.any() or float(light[annulus].mean()) < 0.35:
            continue
        quadrants = (
            annulus & (xx < 0) & (yy < 0),
            annulus & (xx >= 0) & (yy < 0),
            annulus & (xx < 0) & (yy >= 0),
            annulus & (xx >= 0) & (yy >= 0),
        )
        if any(not q.any() or float(light[q].mean()) < 0.25 for q in quadrants):
            continue
        candidates.append((float(area) + light_fill * 1000.0, (cx, cy)))

    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def berry_button_visible(
    scene: np.ndarray,
    *,
    scale: float = 1.0,
    radius: int = 95,
    min_berry_fill: float = 0.06,
) -> bool:
    """Compatibility boolean for callers that do not need the detected centre."""
    return find_berry_button(
        scene,
        scale=scale,
        radius=radius,
        min_berry_fill=min_berry_fill,
    ) is not None


def find_dialog_buttons(
    scene: np.ndarray,
    region: tuple[int, int, int, int] | None = None,
    *,
    min_pixels: int = 120,
    max_gap: int = 40,
    max_panel_sat: float = 40.0,
) -> list[tuple[int, int]]:
    """Centres of an Android alert dialog's text buttons, left to right.

    PGSharp raises a stock system AlertDialog for "Stop AutoWalk?" whenever a tap lands on the
    map, and it blocks everything until answered. Matching it by template failed outright — the
    bundled ones came from a different build and scored below 0.55 even swept across every scale
    — which is the same lesson the camera icon and the ball selector already taught: the shape
    and colour of these controls are stable across versions while their exact pixels are not.

    So the buttons are found by what they are: short runs of the dialog's accent-cyan text,
    sitting side by side on the same baseline. The caller decides which one to press — for a
    "Stop AutoWalk?" prompt that is the left one, CANCEL, because the answer is never OK.

    Returns [] when there is no such row, which is the normal case.
    """
    x_off = y_off = 0
    patch = scene
    if region is not None:
        rx, ry, rw, rh = region
        rx, ry = max(0, rx), max(0, ry)
        patch = scene[ry:ry + rh, rx:rx + rw]
        x_off, y_off = rx, ry
    if patch.size == 0:
        return []
    p = patch.astype(int)
    b, g, r = p[..., 0], p[..., 1], p[..., 2]
    # The accent is a light cyan: blue and green high, red clearly lower.
    cyan = ((b > 150) & (g > 140) & (r < 150) & (b - r > 55)).astype(np.uint8)
    if int(cyan.sum()) < min_pixels:
        return []
    ys, xs = np.nonzero(cyan)
    # Group the runs by their x gaps; each word is one group.
    order = np.argsort(xs)
    xs_s, ys_s = xs[order], ys[order]
    groups: list[tuple[int, int, int, int]] = []
    start = 0
    for i in range(1, len(xs_s) + 1):
        if i == len(xs_s) or xs_s[i] - xs_s[i - 1] > max_gap:
            gx, gy = xs_s[start:i], ys_s[start:i]
            if len(gx) >= min_pixels // 4:
                groups.append((int(gx.min()), int(gx.max()), int(gy.min()), int(gy.max())))
            start = i
    if not groups:
        return []
    # Buttons share a baseline; anything on another line belongs to something else.
    base = float(np.median([(y0 + y1) / 2 for _, _, y0, y1 in groups]))
    row = [gp for gp in groups if abs((gp[2] + gp[3]) / 2 - base) <= 20]
    if not row:
        return []

    # The colour test alone is not enough: the map has plenty of cyan of its own (Pokestop
    # diamonds, route glow) and it produced false rows on every map frame tried. What no map
    # frame has is the dialog's flat grey panel behind the text. Measured over five frames the
    # separation is total — panel saturation 5 on the dialog against 135..174 on map and
    # encounter frames — so requiring a drained backdrop settles it.
    xs_row = [x for gp in row for x in (gp[0], gp[1])]
    px0, px1 = max(0, min(xs_row) - 120), min(patch.shape[1], max(xs_row) + 120)
    py0, py1 = max(0, int(base) - 90), min(patch.shape[0], int(base) + 70)
    panel = patch[py0:py1, px0:px1]
    if panel.size == 0:
        return []
    if float(cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)[..., 1].mean()) > max_panel_sat:
        return []
    return [((x0 + x1) // 2 + x_off, (y0 + y1) // 2 + y_off) for x0, x1, y0, y1 in row]


def find_enc_ball(
    scene: np.ndarray,
    *,
    scale: float = 1.0,
    min_area: int = 900,
    max_area: int = 13000,
) -> tuple[int, int] | None:
    """Locate the encounter's bottom-right ball-selector button, or None if it isn't up.

    Needs no calibration. The corner to search is expressed as a fraction of the frame, and
    the button is identified by its own shape rather than by sitting at a remembered spot: a
    wide red dome (the ball's top half) with a bright white belly directly beneath it. That
    pairing is what separates it from any other red thing on the map, and it holds for every
    ball type because this selector always shows a red Poké Ball.

    This replaces sampling a hand-placed strip. That strip had to be positioned within a few
    pixels of a 70x40 box clipping the dome's edge — painful to calibrate and silently broken
    when slightly off — whereas the button itself is large and unmistakable.
    """
    height, width = scene.shape[:2]
    x0, y0 = int(width * 0.68), int(height * 0.80)
    patch = scene[y0:, x0:]
    if patch.size == 0:
        return None
    p = patch.astype(int)
    b, g, r = p[..., 0], p[..., 1], p[..., 2]
    # A *saturated true red*, not merely "reddish". Measured on this UI: the ball's dome sits
    # at r-b ≈ 175, while the pink "A Route is nearby!" banner that shares this corner is only
    # at r-b ≈ 52 — a loose threshold picked the banner up and reported a phantom encounter.
    red = ((r > 120) & (r - g > 60) & (r - b > 100)).astype(np.uint8)
    count, _labels, stats, _cents = cv2.connectedComponentsWithStats(red, 8)
    best_area = 0
    best_center: tuple[int, int] | None = None
    for i in range(1, count):
        cx, cy, cw, ch, area = stats[i]
        # The button has a known size; anything far larger is a banner or backdrop, not it.
        if not (min_area * scale * scale <= area <= max_area * scale * scale):
            continue
        if area <= best_area:
            continue
        if not (1.1 <= cw / max(1, ch) <= 3.0):      # a dome is wider than it is tall
            continue
        belly = p[cy + ch:min(patch.shape[0], cy + ch + max(6, int(ch * 0.8))), cx:cx + cw]
        if belly.size == 0:
            continue
        bb, bg, br = belly[..., 0], belly[..., 1], belly[..., 2]
        spread = np.maximum.reduce((bb, bg, br)) - np.minimum.reduce((bb, bg, br))
        if float(((br > 150) & (bg > 150) & (bb > 150) & (spread < 60)).mean()) < 0.25:
            continue
        best_area = area
        best_center = (x0 + cx + cw // 2, y0 + cy + ch // 2)
    return best_center


def _iou(a: Match, b: Match) -> float:
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    ix1, iy1 = max(a.x, b.x), max(a.y, b.y)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    union = a.width * a.height + b.width * b.height - inter
    return inter / union


def _suppress(matches: list[Match], max_matches: int) -> list[Match]:
    matches = sorted(matches, key=lambda m: m.score, reverse=True)
    kept: list[Match] = []
    for cand in matches:
        if len(kept) >= max_matches:
            break
        if all(_iou(cand, k) <= 0.3 for k in kept):
            kept.append(cand)
    return kept


def load_template(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"template not found or unreadable: {path}")
    return img


def best_matching_scale(
    scene: np.ndarray,
    template: np.ndarray,
    scales,
    *,
    grayscale: bool = True,
    region: tuple[int, int, int, int] | None = None,
    reduction: float = 1.0,
) -> tuple[float | None, float]:
    """Return (scale, score): the scale in `scales` whose resized `template` best matches
    `scene`. Used once at startup to *measure* how big the UI actually renders on this
    device, instead of guessing it from the screen resolution or density.

    `reduction` shrinks both scene and template before the sweep, which cuts the cost by its
    square while leaving the answer in the caller's units. This is the routine's single most
    expensive operation — seventeen full-frame colour matches — and a scale estimate does not
    need full resolution: what is being measured is how big a 50-120px icon renders, and that
    survives halving intact. The returned scale is unchanged by the reduction.
    """
    from .layout import resize_template

    if reduction != 1.0:
        scene = cv2.resize(scene, None, fx=reduction, fy=reduction, interpolation=cv2.INTER_AREA)
        if region is not None:
            region = tuple(int(round(v * reduction)) for v in region)  # type: ignore[assignment]

    best_s: float | None = None
    best_score = -1.0
    for s in scales:
        t = resize_template(template, s * reduction)
        if t is None or min(t.shape[0], t.shape[1]) < 8:
            continue
        m = find(scene, t, threshold=0.0, scales=(1.0,), max_matches=1,
                 grayscale=grayscale, region=region)
        sc = m[0].score if m else 0.0
        if sc > best_score:
            best_s, best_score = s, sc
    return best_s, best_score
