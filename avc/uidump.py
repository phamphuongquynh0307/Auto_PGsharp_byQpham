"""Read PGSharp's own overlay through the Android view hierarchy.

PGSharp is a patched Pokemon GO APK rather than a separate app — every node in a dump reports
``package='com.nianticlabs.pokemongo'``, and ``me.underw.hp`` is only the resource namespace of
the code merged into it. What matters here is that its overlay is built from real Android views
instead of the game's Unity canvas, so ``uiautomator dump`` reads it directly — and that answers,
exactly, questions the pixel detectors can only estimate:

  * how many Pokemon are on the Nearby bar, and where each one is (``hl_sri_icon``)
  * whether AutoWalk is running or paused, and where its row is (``hl_shortcut_menu_item_txt``)
  * how long PGSharp says the jump cooldown still has to run (``hl_cd_text``)
  * the encounter's level / IV / stats as text (``hl_ec_sum_*``)

Measured against the vision path on a live 1220x2712 MuMu, the icon nodes matched the detected
slots exactly, three dumps in a row, with centres within 3px.

The catch is speed: a dump costs ~1.6s against ~25ms for a screenshot, so this cannot sit in a
poll loop. It belongs where the flow already pays for an expensive, decisive answer — the last
word before declaring the bar empty — with the pixel detectors carrying every fast path and
covering the dumps that fail (uiautomator refuses while the UI is animating).

Nothing here is authoritative about the *game*; it only reads what PGSharp has already worked
out and put on screen. Ids are PGSharp's, so a PGSharp update can rename them, which is why
every caller must keep its vision fallback.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

# PGSharp resource ids, minus the package prefix.
_NEARBY_ICON = "hl_sri_icon"
_MENU_TEXT = "hl_shortcut_menu_item_txt"
_ENCOUNTER_PREFIX = "hl_ec_sum_"
_COOLDOWN_TEXT = "hl_cd_text"

_CLOCK = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")

_BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def _centre(bounds: str) -> tuple[int, int] | None:
    m = _BOUNDS.match(bounds or "")
    if not m:
        return None
    x0, y0, x1, y1 = (int(v) for v in m.groups())
    return ((x0 + x1) // 2, (y0 + y1) // 2)


@dataclass
class UiState:
    """What one dump saw. Empty lists mean "the dump was fine and there was nothing"."""

    nearby: list[tuple[int, int]] = field(default_factory=list)   # slot centres, top first
    menu: dict[str, tuple[int, int]] = field(default_factory=dict)  # row text -> centre
    encounter: dict[str, str] = field(default_factory=dict)       # hl_ec_sum_* suffix -> text
    cooldown: float = 0.0        # seconds left on PGSharp's jump cooldown, 0 when clear

    @property
    def autowalk_row(self) -> tuple[str, tuple[int, int]] | None:
        """The AutoWalk row as (label, centre). Its label carries the state: PGSharp writes
        'AW(Paused)' when the walk has stalled and 'AW' (plus the mode) while it runs."""
        for label, centre in self.menu.items():
            if label.upper().startswith("AW"):
                return label, centre
        return None

    @property
    def autowalk_paused(self) -> bool:
        row = self.autowalk_row
        return bool(row and "paus" in row[0].lower())

    @property
    def speed_kmh(self) -> float | None:
        """The walking speed PGSharp shows in its menu, e.g. '9.3 km/h'."""
        for label in self.menu:
            m = re.match(r"^([\d.]+)\s*km/h$", label.strip(), re.I)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    return None
        return None

    @property
    def in_encounter(self) -> bool:
        """PGSharp only renders its encounter summary while an encounter is open."""
        return bool(self.encounter)


def parse(xml_text: str) -> UiState | None:
    """Turn a uiautomator dump into a UiState, or None if it isn't parseable."""
    if not xml_text or "<node" not in xml_text:
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    state = UiState()
    nearby: list[tuple[int, int]] = []
    for node in root.iter("node"):
        rid = node.get("resource-id") or ""
        if not rid:
            continue
        name = rid.rsplit("/", 1)[-1]
        centre = _centre(node.get("bounds") or "")
        if centre is None:
            continue
        if name == _NEARBY_ICON:
            nearby.append(centre)
        elif name == _MENU_TEXT:
            text = (node.get("text") or "").strip()
            if text:
                state.menu[text] = centre
        elif name == _COOLDOWN_TEXT:
            m = _CLOCK.match((node.get("text") or "").strip())
            if m:
                h, mi, sec = (int(v) for v in m.groups())
                state.cooldown = float(h * 3600 + mi * 60 + sec)
        elif name.startswith(_ENCOUNTER_PREFIX):
            text = (node.get("text") or "").strip()
            if text:
                state.encounter[name[len(_ENCOUNTER_PREFIX):]] = text
    # The bar reads top-down, and so does every caller.
    state.nearby = sorted(nearby, key=lambda c: c[1])
    return state
