"""Read PGSharp's own overlay through the Android view hierarchy.

PGSharp is a patched Pokemon GO APK rather than a separate app — every node in a dump reports
``package='com.nianticlabs.pokemongo'``, and ``me.underw.hp`` is only the resource namespace of
the code merged into it. What matters here is that its overlay is built from real Android views
instead of the game's Unity canvas, so ``uiautomator dump`` reads it directly — and that answers,
exactly, questions the pixel detectors can only estimate:

  * how many Pokemon are on the Nearby bar, and where each one is (``hl_sri_icon``) --
    but see ``_columns``: the Feeds sidebar is the same widget with the same id, so a dump
    holds *two* bars under it and only their columns tell them apart
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
_IV_EXPLICIT = re.compile(r"\bIV\s*:?\s*(100|\d{1,2})(?:\s*%)?\b", re.I)
_IV_BARE = re.compile(r"^\s*(100|\d{1,2})(?:\s*%)?\s*$")
_IV_STATS = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\b")

_BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")

# Icons within one sidebar share an x exactly (same ListView), and the two sidebars sit at
# opposite edges of the screen. Anything short of a full icon width therefore separates them.
_COLUMN_TOL = 40


def _centre(bounds: str) -> tuple[int, int] | None:
    m = _BOUNDS.match(bounds or "")
    if not m:
        return None
    x0, y0, x1, y1 = (int(v) for v in m.groups())
    return ((x0 + x1) // 2, (y0 + y1) // 2)


def _box(bounds: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS.match(bounds or "")
    return tuple(int(v) for v in m.groups()) if m else None  # type: ignore[return-value]


def _columns(slots: list[tuple[int, int]], tol: int = _COLUMN_TOL) -> list[list[tuple[int, int]]]:
    """Split slot centres into one list per sidebar, each reading top-down.

    Both of PGSharp's sidebars -- Nearby and Feeds -- are the same list widget, so every entry
    in either one reports ``hl_sri_icon`` and a dump cannot name them apart. What separates
    them is position: each bar is a single narrow column, and every icon inside one shares an
    x to the pixel. Grouping on x therefore recovers the bars themselves; which of them is
    Nearby is a question for the caller, who has the '@' anchor to answer it with.

    Bars dragged into the *same* column still merge here. That is the one arrangement this
    cannot undo, and it is why the caller must still bound the bar it picks.
    """
    bars: list[list[tuple[int, int]]] = []
    for slot in sorted(slots, key=lambda c: (c[0], c[1])):
        if bars and abs(slot[0] - bars[-1][0][0]) <= tol:
            bars[-1].append(slot)
        else:
            bars.append([slot])
    for bar in bars:
        bar.sort(key=lambda c: c[1])
    return bars


@dataclass
class UiState:
    """What one dump saw. Empty lists mean "the dump was fine and there was nothing"."""

    nearby: list[tuple[int, int]] = field(default_factory=list)   # every bar's slots, top first
    # One entry per sidebar found (Nearby and, when open, Feeds), left to right; each reads
    # top-down. `nearby` merges them and so cannot be trusted to describe one bar -- see
    # `_columns`, and CatchRoutine._ui_nearby_bar for the one that picks Nearby out of these.
    bars: list[list[tuple[int, int]]] = field(default_factory=list)
    menu: dict[str, tuple[int, int]] = field(default_factory=dict)  # row text -> centre
    # Native Android dialog actions. Unlike image templates these retain their text and exact
    # bounds across emulator DPI, font rendering, language and light/dark themes.
    dialog_buttons: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    encounter: dict[str, str] = field(default_factory=dict)       # hl_ec_sum_* suffix -> text
    cooldown: float = 0.0        # seconds left on PGSharp's jump cooldown, 0 when clear

    @property
    def autowalk_row(self) -> tuple[str, tuple[int, int]] | None:
        """The AutoWalk row as (label, centre). Its label carries the state: PGSharp writes
        'AW(Paused)' when the walk has stalled and 'AW' (plus the mode) while it runs."""
        for label, centre in self.menu.items():
            upper = label.upper().replace(" ", "")
            # Builds in the field use both "AW(Paused)" and the unabbreviated "AutoWalk".
            if upper.startswith("AW") or "AUTOWALK" in upper:
                return label, centre
        return None

    @property
    def autowalk_paused(self) -> bool:
        row = self.autowalk_row
        return bool(row and "paus" in row[0].lower())

    @property
    def cancel_button(self) -> tuple[int, int] | None:
        """The safe negative action of a native dialog, when exposed by Android."""
        negative = {"CANCEL", "CANCELAR", "HUY", "HỦY", "NO", "KHONG", "KHÔNG"}
        for text, centre in self.dialog_buttons:
            if text.strip().upper() in negative:
                return centre
        return None

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

    @property
    def iv_stats(self) -> tuple[int, int, int] | None:
        """Exact attack / defence / stamina IV columns shown by PGSharp.

        These values must stay separate: ``15/15/14`` and ``14/15/15`` have the same
        percentage but are different targets to the user.
        """
        for text in self.encounter.values():
            stats = _IV_STATS.search(text)
            if not stats:
                continue
            values = tuple(int(value) for value in stats.groups())
            if all(0 <= value <= 15 for value in values):
                return values

        # Some PGSharp builds expose the three stats as separate views instead of one
        # ``15/15/14`` string. Resource suffixes vary slightly, so accept their common
        # abbreviated and full names but never treat an unrelated bare number as a stat.
        individual: dict[str, int] = {}
        aliases = {
            "attack": ("atk", "attack"),
            "defence": ("def", "defence", "defense"),
            "stamina": ("sta", "stamina", "hp"),
        }
        for name, text in self.encounter.items():
            suffix = name.lower().strip("_-")
            bare = _IV_BARE.match(text)
            if not bare:
                continue
            value = int(bare.group(1))
            if not 0 <= value <= 15:
                continue
            for stat, names in aliases.items():
                if suffix in names or any(suffix.endswith(f"_{alias}") for alias in names):
                    individual[stat] = value
                    break
        if len(individual) == 3:
            return individual["attack"], individual["defence"], individual["stamina"]
        return None

    @property
    def iv_percent(self) -> int | None:
        """IV percentage shown by PGSharp, retained for callers that only need a summary.

        PGSharp versions use slightly different ``hl_ec_sum_*`` suffixes and some put
        ``IV`` in the resource id while others put it in the visible text. Prefer those
        explicit fields, then derive the familiar rounded percentage from 0-15 attack /
        defence / stamina values when only the stat triplet is exposed.
        """
        for name, text in self.encounter.items():
            explicit = _IV_EXPLICIT.search(f"{name} {text}")
            if explicit:
                value = int(explicit.group(1))
                if 0 <= value <= 100:
                    return value
            if "iv" in name.lower():
                bare = _IV_BARE.match(text)
                if bare:
                    return int(bare.group(1))

        stats = self.iv_stats
        return round(sum(stats) * 100 / 45) if stats is not None else None


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
        centre = _centre(node.get("bounds") or "")
        if centre is None:
            continue
        text = (node.get("text") or "").strip()
        class_name = node.get("class") or ""
        clickable = (node.get("clickable") or "").lower() == "true"
        # Stock AlertDialog actions normally have android:id/button1..3, but several Android
        # skins omit that id while keeping a clickable Button node. Keep both representations.
        if text and ("android:id/button" in rid or (clickable and class_name.endswith("Button"))):
            state.dialog_buttons.append((text, centre))
        if not rid:
            continue
        name = rid.rsplit("/", 1)[-1]
        if name == _NEARBY_ICON:
            box = _box(node.get("bounds") or "")
            # A list item scrolled half out of its ListView reports a sliver of a box. Its
            # centre is not a slot centre, and tapping it lands on the bar's rim.
            if box is not None and (box[3] - box[1]) * 2 >= (box[2] - box[0]):
                nearby.append(centre)
        elif name == _MENU_TEXT:
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
    state.bars = _columns(nearby)
    state.nearby = sorted(nearby, key=lambda c: c[1])
    return state
