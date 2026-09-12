import threading
import unittest
from types import SimpleNamespace

from avc import uidump
from avc.shundo import ShundoRoutine, ShundoStats


def icon(x0, y0, x1, y1):
    return ('<node resource-id="x:id/hl_sri_icon" '
            f'bounds="[{x0},{y0}][{x1},{y1}]" />')


def two_sidebar_xml(*, nearby_occupied=True):
    nearby = icon(991, 275, 1117, 395) if nearby_occupied else ""
    return (
        '<hierarchy bounds="[0,0][1220,2712]">'
        '<node class="android.widget.ListView" bounds="[49,318][175,1074]">'
        f'{icon(49,318,175,438)}</node>'
        '<node class="android.widget.ListView" bounds="[991,275][1117,1031]">'
        f'{nearby}</node>'
        '</hierarchy>'
    )


def bare_routine(xml):
    routine = object.__new__(ShundoRoutine)
    routine.config = SimpleNamespace(
        use_ui_dump=True,
        ui_dump_cooldown=0.0,
        anchor_region=(760, 200, 460, 1800),
        handle_column_tol=60,
        s=lambda value: value,
        encounter_open_wait=0.0,
        encounter_no_answer_attempts=1,
        require_confirmed_check=False,
        nearby_recheck_attempts=3,
        nearby_recheck_gap=0.0,
    )
    routine.device = SimpleNamespace(
        ui_dump=lambda: xml,
        screenshot=lambda **_kwargs: object(),
        double_tap=lambda x, y: routine.double_taps.append((x, y)),
    )
    routine.double_taps = []
    routine._ui_dump_at = float("-inf")
    routine._ui_state_cache = None
    routine._ui_state_cache_at = 0.0
    routine._ui_nearby_slot = None
    routine._ui_feed_slot = None
    routine._ui_nearby_verified_at = 0.0
    routine._nearby_column_x = None
    routine._anchor_cache = None
    routine._feed_cache = None
    routine._pending_no_target = 0
    routine._pending_no_answers = 0
    routine.stats = ShundoStats()
    routine.stop_event = threading.Event()
    routine.pause_event = threading.Event()
    routine._interruptible_sleep = lambda _seconds: None
    routine._encounter_visible = lambda _frame: False
    routine._poll = lambda _predicate, _timeout: None
    return routine


class ShundoUiFallbackTests(unittest.TestCase):
    def test_names_empty_nearby_and_occupied_feed_without_image_templates(self):
        routine = bare_routine(two_sidebar_xml(nearby_occupied=False))
        state = uidump.parse(two_sidebar_xml(nearby_occupied=False))

        self.assertEqual([], routine._ui_nearby_bar(state))
        self.assertEqual([(112, 378)], routine._ui_feed_bar(state))

    def test_fresh_image_miss_uses_exact_nearby_widget_coordinate(self):
        routine = bare_routine(two_sidebar_xml(nearby_occupied=True))
        routine._raw_target_in_bar = lambda _frame: None

        outcome = routine._attempt_nearby((900, 500))

        self.assertEqual("blocked", outcome)
        self.assertEqual([(1054, 335)], routine.double_taps)
        self.assertEqual(1, routine.stats.checked)

    def test_just_verified_ui_target_is_not_dumped_twice_before_tap(self):
        routine = bare_routine(two_sidebar_xml(nearby_occupied=True))
        dumps = []
        routine.device.ui_dump = lambda: dumps.append(True) or two_sidebar_xml(
            nearby_occupied=True
        )
        target = routine._ui_nearby_target(force=True)
        routine._raw_target_in_bar = lambda _frame: None

        outcome = routine._attempt_nearby(target)

        self.assertEqual("blocked", outcome)
        self.assertEqual(1, len(dumps))
        self.assertEqual([(1054, 335)], routine.double_taps)

    def test_does_not_mistake_lone_nearby_bar_for_feed(self):
        xml = (
            '<hierarchy bounds="[0,0][1220,2712]">'
            '<node class="android.widget.ListView" bounds="[991,275][1117,1031]">'
            f'{icon(991,275,1117,395)}</node></hierarchy>'
        )
        routine = bare_routine(xml)
        state = uidump.parse(xml)

        self.assertIsNone(routine._ui_feed_bar(state))


if __name__ == "__main__":
    unittest.main()
