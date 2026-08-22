"""PGSharp gives its Nearby bar and its Feeds bar the same `hl_sri_icon` id, so one dump
describes two bars. Everything here guards the line between them: reading them as one list
put a Feed coordinate into the Nearby calibration and had the bot double-tapping Feeds while
Nearby was full."""
import unittest
from types import SimpleNamespace

from avc import uidump
from avc.catch import CatchRoutine


def icon(x0: int, y0: int, x1: int, y1: int) -> str:
    return ('<node resource-id="com.nianticlabs.pokemongo:id/hl_sri_icon" '
            f'bounds="[{x0},{y0}][{x1},{y1}]" />')


# Bounds copied from a live 1220x2712 dump: Feeds parked on the left with 6 entries, Nearby
# on the right with 3, plus the half-scrolled sliver the Feed ListView reports at its foot.
FEED_ICONS = [(79, 321 + n * 123, 205, 441 + n * 123) for n in range(6)]
NEARBY_ICONS = [(887, 270 + n * 123, 1013, 390 + n * 123) for n in range(3)]
SLIVER = (79, 1059, 205, 1077)


def dump(*boxes) -> str:
    return "<hierarchy>" + "".join(icon(*b) for b in boxes) + "</hierarchy>"


class ColumnSplitTests(unittest.TestCase):
    def test_two_sidebars_split_into_two_bars(self):
        state = uidump.parse(dump(*FEED_ICONS, *NEARBY_ICONS))
        self.assertEqual([6, 3], [len(bar) for bar in state.bars])
        self.assertEqual(142, state.bars[0][0][0])
        self.assertEqual(950, state.bars[1][0][0])

    def test_each_bar_reads_top_down(self):
        state = uidump.parse(dump(*reversed(NEARBY_ICONS), *FEED_ICONS))
        for bar in state.bars:
            self.assertEqual(sorted(y for _x, y in bar), [y for _x, y in bar])

    def test_half_scrolled_item_is_not_a_slot(self):
        state = uidump.parse(dump(*FEED_ICONS, SLIVER))
        self.assertEqual([6], [len(bar) for bar in state.bars])

    def test_single_bar_still_reads_as_one(self):
        state = uidump.parse(dump(*NEARBY_ICONS))
        self.assertEqual(1, len(state.bars))
        self.assertEqual(3, len(state.bars[0]))


def bare_routine(*, force_slot=True, nearby_slot=(927, 312), anchor=None, ui_slot=None):
    routine = object.__new__(CatchRoutine)
    routine.config = SimpleNamespace(
        force_slot=force_slot, nearby_slot=nearby_slot, handle_column_tol=60,
    )
    routine._anchor_cache = anchor
    routine._ui_nearby_slot = ui_slot
    return routine


class NearbyBarPickTests(unittest.TestCase):
    def setUp(self):
        self.state = uidump.parse(dump(*FEED_ICONS, *NEARBY_ICONS))

    def test_anchor_column_picks_nearby_not_the_higher_feed_bar(self):
        # The Feed bar's top entry sits *below* Nearby's here, and the '@' still decides.
        routine = bare_routine(anchor=(950, 1089))
        self.assertEqual([(950, 330), (950, 453), (950, 576)],
                         routine._ui_nearby_bar(self.state))

    def test_feed_bar_hanging_higher_is_still_rejected(self):
        higher_feed = [(79, 231 + n * 123, 205, 351 + n * 123) for n in range(6)]
        state = uidump.parse(dump(*higher_feed, *NEARBY_ICONS))
        self.assertEqual((142, 291), state.nearby[0])   # merged list leads with Feeds
        routine = bare_routine(anchor=(950, 1089))
        self.assertEqual((950, 330), routine._ui_nearby_bar(state)[0])

    def test_manual_calibration_names_the_column_before_any_anchor(self):
        routine = bare_routine(nearby_slot=(927, 312))
        self.assertEqual((950, 330), routine._ui_nearby_bar(self.state)[0])

    def test_column_accepted_earlier_survives_a_lost_anchor(self):
        routine = bare_routine(force_slot=False, ui_slot=(950, 330))
        self.assertEqual((950, 330), routine._ui_nearby_bar(self.state)[0])

    def test_two_bars_and_no_reference_says_it_cannot_tell(self):
        # None, not [] — "I cannot name the Nearby column" must not read as "Nearby is empty",
        # which would let the caller skip the pixel fallback on the strength of a shrug.
        self.assertIsNone(bare_routine(force_slot=False)._ui_nearby_bar(self.state))

    def test_one_bar_and_no_reference_is_unambiguous(self):
        state = uidump.parse(dump(*NEARBY_ICONS))
        self.assertEqual((950, 330), bare_routine(force_slot=False)._ui_nearby_bar(state)[0])

    def test_calibration_in_neither_column_says_it_cannot_tell(self):
        self.assertIsNone(bare_routine(nearby_slot=(500, 312))._ui_nearby_bar(self.state))

    def test_a_tree_with_no_sidebar_entries_is_a_real_empty_bar(self):
        # [] here, because an empty ListView contributes no icons: nothing on either bar means
        # nothing on Nearby, whichever column it is, and the caller may trust that.
        other = ('<hierarchy><node resource-id="x:id/hl_shortcut_menu_item_txt" '
                 'text="AutoWalk" bounds="[468,672][679,768]" /></hierarchy>')
        self.assertEqual([], bare_routine()._ui_nearby_bar(uidump.parse(other)))

    def test_entries_below_the_anchor_belong_to_the_other_bar(self):
        # Both bars dragged into one column: the split cannot separate them, so the '@' —
        # which ends the Nearby bar — is what cuts the Feed entries off the bottom.
        # Nearby's three entries, its '@' at 699, then the Feed bar's own entries below it.
        below = [(887, 840 + n * 123, 1013, 960 + n * 123) for n in range(3)]
        state = uidump.parse(dump(*NEARBY_ICONS, *below))
        routine = bare_routine(anchor=(950, 699))
        self.assertEqual([(950, 330), (950, 453), (950, 576)],
                         routine._ui_nearby_bar(state))


if __name__ == "__main__":
    unittest.main()
