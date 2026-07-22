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
) -> tuple[float | None, float]:
    """Return (scale, score): the scale in `scales` whose resized `template` best matches
    `scene`. Used once at startup to *measure* how big the UI actually renders on this
    device, instead of guessing it from the screen resolution or density."""
    from .layout import resize_template

    best_s: float | None = None
    best_score = -1.0
    for s in scales:
        t = resize_template(template, s)
        if t is None or min(t.shape[0], t.shape[1]) < 8:
            continue
        m = find(scene, t, threshold=0.0, scales=(1.0,), max_matches=1,
                 grayscale=grayscale, region=region)
        sc = m[0].score if m else 0.0
        if sc > best_score:
            best_s, best_score = s, sc
    return best_s, best_score
