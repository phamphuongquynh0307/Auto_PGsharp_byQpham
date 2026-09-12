"""Local vision fallback for PGSharp's ``ATK/DEF/HP`` encounter text.

Some PGSharp builds draw the Encounter IV pill on a surface that Android's accessibility tree
does not expose at all.  UIAutomator then returns a perfectly valid hierarchy with no ``hl_ec``
nodes, so exact non-hundo IVs need a pixel reader.  This module deliberately recognizes only the
three small fields around PGSharp's two slash glyphs; it is not a general screen OCR path.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

import cv2
import numpy as np


OCR_VOCABULARY = list("0123456789abcdefghijklmnopqrstuvwxyz")


@dataclass(frozen=True)
class _Component:
    label: int
    x: int
    y: int
    w: int
    h: int
    area: int
    slope: float

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def centre_y(self) -> float:
        return self.y + self.h / 2


def _light_components(roi: np.ndarray) -> list[_Component]:
    """Connected pale glyphs, including slash candidates, inside one pill search region."""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation, value = hsv[..., 1], hsv[..., 2]
    # Encounter stats are white.  Capping saturation rejects the shiny/background artwork and
    # most of the map showing through the translucent pill; the geometric slash pair rejects the
    # remaining rain/highlight noise.
    mask = ((value >= 105) & (saturation <= 115)).astype(np.uint8)
    count, labels, stats, _centres = cv2.connectedComponentsWithStats(mask, 8)
    out: list[_Component] = []
    for label in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[label])
        if area < 3 or h < 3:
            continue
        ys, xs = np.nonzero(labels[y:y + h, x:x + w] == label)
        if len(np.unique(ys)) >= 3:
            slope = float(np.polyfit(ys, xs, 1)[0])
        else:
            slope = 0.0
        out.append(_Component(label, x, y, w, h, area, slope))
    return out


def _digit_groups(components: list[_Component], first: _Component,
                  second: _Component) -> tuple[list[_Component], list[_Component],
                                                list[_Component]] | None:
    """Return the 1-2 glyph components immediately around a plausible slash pair."""
    height = (first.h + second.h) / 2
    line = [
        comp for comp in components
        if comp.label not in (first.label, second.label)
        and 0.55 * height <= comp.h <= 1.55 * height
        and comp.w <= 1.25 * height
        and abs(comp.centre_y - (first.centre_y + second.centre_y) / 2) <= 0.45 * height
    ]
    line.sort(key=lambda comp: comp.x)

    left_pool = [comp for comp in line
                 if comp.right <= first.x + 1 and comp.x >= first.x - 2.35 * height]
    left: list[_Component] = []
    edge = first.x
    for comp in reversed(left_pool):
        gap = edge - comp.right
        if gap > 0.62 * height:
            break
        left.append(comp)
        edge = comp.x
        if len(left) == 2:
            break
    left.reverse()

    middle = [comp for comp in line
              if comp.x >= first.right - 1 and comp.right <= second.x + 1]

    right_pool = [comp for comp in line
                  if comp.x >= second.right - 1 and comp.right <= second.right + 2.35 * height]
    right: list[_Component] = []
    edge = second.right
    for comp in right_pool:
        gap = comp.x - edge
        if gap > 0.62 * height:
            break
        right.append(comp)
        edge = comp.right
        if len(right) == 2:
            break

    groups = (left, middle, right)
    if all(1 <= len(group) <= 2 for group in groups):
        return groups
    return None


def _slash_group_candidates(components: list[_Component], roi_h: int):
    min_h = max(5, int(round(roi_h * 0.035)))
    max_h = max(min_h + 1, int(round(roi_h * 0.26)))
    slashes = [
        comp for comp in components
        if min_h <= comp.h <= max_h
        and comp.w <= 0.78 * comp.h
        and comp.slope <= -0.22
        and comp.area >= max(4, int(round(comp.h * 0.75)))
    ]
    candidates = []
    for first, second in combinations(sorted(slashes, key=lambda comp: comp.x), 2):
        height = (first.h + second.h) / 2
        distance = second.x - first.x
        if not (0.75 * height <= distance <= 5.2 * height):
            continue
        if abs(first.centre_y - second.centre_y) > 0.40 * height:
            continue
        if not 0.60 <= first.h / max(1, second.h) <= 1.67:
            continue
        groups = _digit_groups(components, first, second)
        if groups is None:
            continue
        geometry_penalty = abs(first.centre_y - second.centre_y) + abs(first.h - second.h)
        candidates.append((geometry_penalty, first, second, groups))
    return sorted(candidates, key=lambda candidate: candidate[0])


class IvOcr:
    """Lazy caller-owned CRNN reader; one instance is safe for one Shundo worker thread."""

    def __init__(self, model_path: str) -> None:
        self.model = cv2.dnn_TextRecognitionModel(model_path)
        self.model.setDecodeType("CTC-greedy")
        self.model.setVocabulary(OCR_VOCABULARY)
        self.model.setInputParams(1.0 / 127.5, (100, 32), (127.5, 127.5, 127.5))

    def _digit(self, roi: np.ndarray, component: _Component) -> tuple[int, int] | None:
        pad_x = max(2, int(round(component.h * 0.28)))
        pad_y = max(3, int(round(component.h * 0.45)))
        x0, y0 = max(0, component.x - pad_x), max(0, component.y - pad_y)
        x1 = min(roi.shape[1], component.right + pad_x)
        y1 = min(roi.shape[0], component.bottom + pad_y)
        crop = roi[y0:y1, x0:x1]
        if crop.size == 0:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        votes: list[int] = []
        thresholds = [
            cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            *(cv2.threshold(gray, value, 255, cv2.THRESH_BINARY)[1]
              for value in (95, 125, 155, 185, 210)),
        ]
        for binary in thresholds:
            text = self.model.recognize(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR))
            digits = [char for char in text if char.isdigit()]
            # A single narrow glyph can be stretched by the fixed-width CRNN input and decoded
            # as "777".  It is still an unambiguous 7; mixed outputs such as "14" are ignored.
            if digits and len(set(digits)) == 1:
                votes.append(int(digits[0]))
        if not votes:
            return None
        digit, support = Counter(votes).most_common(1)[0]
        return digit, support

    def read(self, frame: np.ndarray,
             region: tuple[int, int, int, int]) -> tuple[int, int, int] | None:
        x, y, w, h = region
        frame_h, frame_w = frame.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(frame_w, x + w), min(frame_h, y + h)
        if x1 - x0 < 30 or y1 - y0 < 18:
            return None
        roi = frame[y0:y1, x0:x1]
        components = _light_components(roi)
        answers = []
        for geometry_penalty, first, _second, groups in _slash_group_candidates(
                components, roi.shape[0]):
            values: list[int] = []
            support = 0
            valid = True
            for group in groups:
                value = 0
                for component in group:
                    result = self._digit(roi, component)
                    if result is None:
                        valid = False
                        break
                    digit, digit_support = result
                    value = value * 10 + digit
                    support += digit_support
                if not valid or not 0 <= value <= 15:
                    valid = False
                    break
                values.append(value)
            if not valid:
                continue

            stats = tuple(values)
            expected_percent = str(round(sum(stats) * 100 / 45))
            percent_components = [
                comp for comp in components
                if comp.right < groups[0][0].x
                and 0.55 * first.h <= comp.h <= 1.55 * first.h
                and abs(comp.centre_y - first.centre_y) <= 0.45 * first.h
                and comp.w <= 1.25 * first.h
            ]
            percent_components.sort(key=lambda comp: comp.x)
            percent_components = percent_components[-len(expected_percent):]
            percent_digits = []
            if len(percent_components) == len(expected_percent):
                for component in percent_components:
                    result = self._digit(roi, component)
                    if result is None:
                        percent_digits = []
                        break
                    percent_digits.append(str(result[0]))
            percent_match = "".join(percent_digits) == expected_percent
            answers.append((percent_match, support, -geometry_penalty, stats))

        if not answers:
            return None
        answers.sort(reverse=True)
        best = answers[0]
        # Each glyph is tried under six independent binarisations. Require a conservative average
        # of two agreeing reads, then refuse an unresolved tie between different IV triplets.
        if best[1] < len("".join(str(value) for value in best[3])) * 2:
            return None
        equally_good = [answer for answer in answers
                        if answer[:3] == best[:3] and answer[3] != best[3]]
        return None if equally_good else best[3]
