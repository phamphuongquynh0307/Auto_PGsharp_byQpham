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
