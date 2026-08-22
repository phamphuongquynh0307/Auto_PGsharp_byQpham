"""Settings must be hidden when they do nothing — and saved even while hidden.

Which control is inert in which mode is a fact about avc/catch.py and avc/shundo.py, so it
drifts silently as those change. These tests pin the mapping to the reason for it.
"""
import json
import os
import sys
import tempfile
import tkinter as tk
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tk_available() -> bool:
    try:
        tk.Tk().destroy()
        return True
    except Exception:  # noqa: BLE001 - headless runner
        return False


@unittest.skipUnless(_tk_available(), "no display for tkinter")
class VisibilityTests(unittest.TestCase):
    def setUp(self):
        import gui

        self.gui = gui
        self.tmp = tempfile.mkdtemp()
        self._real_path = gui._settings_path
        gui._settings_path = lambda: os.path.join(self.tmp, "settings.json")
        self.root = tk.Tk()
        self.app = gui.App(self.root)

    def tearDown(self):
        self.root.destroy()
        self.gui._settings_path = self._real_path

    def _shown(self, key: str) -> bool:
        widgets, _advanced = self.app._rows[key]
        return any(bool(w.winfo_manager()) for w in widgets)

    def _configure(self, mode: str, style: str = "normal", advanced: bool = False):
        self.app.mode, self.app.catch_style = mode, style
        self.app.show_advanced.set(advanced)
        self.app._sync_settings_visibility()
        self.root.update_idletasks()

    def _group_shown(self, frame) -> bool:
        return bool(frame.winfo_manager())

    def test_quick_catch_only_rows_are_hidden_while_catching_normally(self):
        self._configure("catch", "normal", advanced=True)

        # Read only inside CatchRoutine._quick_throw.
        self.assertFalse(self._shown("quick_flick"))
        self.assertFalse(self._shown("post_throw"))
        self.assertFalse(self._shown("flee_taps"))
        self.assertFalse(self._shown("flee_gap"))
        self.assertTrue(self._shown("no_balls_goplus"))

    def test_quick_catch_shows_its_own_knobs(self):
        self._configure("catch", "quick")

        self.assertTrue(self._shown("quick_flick"))
        self.assertTrue(self._shown("flee_taps"))
        self.assertFalse(self._shown("no_balls_goplus"))

    def test_shundo_hides_the_catching_rows_but_keeps_the_flee_taps(self):
        self._configure("shundo")

        self.assertFalse(self._shown("throw_power"))
        self.assertFalse(self._shown("wait_catch"))
        self.assertTrue(self._shown("flee_taps"))   # ShundoRoutine._flee spends these

    def test_advanced_rows_stay_hidden_until_asked_for(self):
        self._configure("catch", "normal", advanced=False)
        self.assertFalse(self._shown("touch_delay"))

        self._configure("catch", "normal", advanced=True)
        self.assertTrue(self._shown("touch_delay"))

    def test_the_spin_knobs_stay_hidden_until_something_reads_them(self):
        """Nothing spins in a plain catching run, so the circle radius would be a control that
        changes nothing — the exact thing this whole sync exists to prevent."""
        self._configure("catch", "normal")
        self.app.no_balls_spin.set(False)
        self.app._sync_settings_visibility()

        self.assertFalse(self._group_shown(self.app._grp_spin))
        self.assertFalse(self._shown("no_balls_min"))

    def test_ticking_the_out_of_balls_box_reveals_the_spin_knobs(self):
        self._configure("catch", "normal")
        self.app.no_balls_spin.set(True)
        self.app._sync_settings_visibility()
        self.root.update_idletasks()

        self.assertTrue(self._group_shown(self.app._grp_spin))
        self.assertTrue(self._shown("no_balls_min"))

    def test_spinning_to_refill_is_offered_without_a_key(self):
        """Go Plus needs the paid key, so Quick Catch hides it — the screen spinner does not,
        and hiding it there would leave that user no refill path at all."""
        self._configure("catch", "quick")

        self.assertFalse(self._shown("no_balls_goplus"))
        self.assertTrue(self._shown("no_balls_spin"))

    def test_spin_mode_shows_its_own_group_and_hides_the_catching_one(self):
        self._configure("spin")

        self.assertTrue(self._group_shown(self.app._grp_spin))
        self.assertFalse(self._group_shown(self.app._grp_catch))
        self.assertFalse(self._shown("throw_power"))
        # SpinRoutine._leave_encounter spends these when Go Plus opens an encounter on it.
        self.assertTrue(self._shown("flee_taps"))

    def test_the_default_view_is_substantially_smaller_than_every_control(self):
        self._configure("catch", "normal", advanced=False)
        shown = sum(1 for key in self.app._rows if self._shown(key))

        self.assertLess(shown, len(self.app._rows) * 0.75)


@unittest.skipUnless(_tk_available(), "no display for tkinter")
class HiddenPersistenceTests(unittest.TestCase):
    """A hidden control is still a set control; hiding it must never drop its value."""

    def test_a_setting_hidden_by_the_current_mode_is_still_saved(self):
        import gui

        tmp = tempfile.mkdtemp()
        real_path = gui._settings_path
        gui._settings_path = lambda: os.path.join(tmp, "settings.json")
        try:
            root = tk.Tk()
            app = gui.App(root)
            app.throw_power.set(1234)
            app.no_balls_goplus.set(False)
            app.target_iv_atk.set(15)
            app.target_iv_def.set(14)
            app.target_iv_sta.set(13)
            app.mode = "shundo"          # hides the whole catching group
            app._sync_settings_visibility()
            app.save_settings()
            root.destroy()

            with open(gui._settings_path(), encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(1234, saved["throw_power"])
            self.assertFalse(saved["no_balls_goplus"])
            self.assertEqual((15, 14, 13), (
                saved["target_iv_atk"], saved["target_iv_def"], saved["target_iv_sta"]))

            root = tk.Tk()
            reloaded = gui.App(root)
            self.assertEqual(1234, reloaded.throw_power.get())
            self.assertFalse(reloaded.no_balls_goplus.get())
            self.assertEqual((15, 14, 13), (
                reloaded.target_iv_atk.get(), reloaded.target_iv_def.get(),
                reloaded.target_iv_sta.get()))
            root.destroy()
        finally:
            gui._settings_path = real_path

    def test_a_value_below_the_routines_floor_is_clamped_on_load(self):
        import gui

        tmp = tempfile.mkdtemp()
        real_path = gui._settings_path
        gui._settings_path = lambda: os.path.join(tmp, "settings.json")
        try:
            with open(gui._settings_path(), "w", encoding="utf-8") as fh:
                json.dump({"post_throw": 0.0, "flee_gap": 0.05}, fh)
            root = tk.Tk()
            app = gui.App(root)
            # avc/catch.py raises these at the point of use; the box must not claim otherwise.
            self.assertGreaterEqual(app.post_throw.get(), 1.0)
            self.assertGreaterEqual(app.flee_gap.get(), 0.25)
            root.destroy()
        finally:
            gui._settings_path = real_path


@unittest.skipUnless(_tk_available(), "no display for tkinter")
class SpinConfigTests(unittest.TestCase):
    """The scan circle is authored in base coordinates and re-anchored by scale_to like every
    other coordinate — writing device pixels straight into the config would leave this one box
    behind whenever the routine re-derives everything at a measured render scale."""

    def setUp(self):
        import gui

        self.gui = gui
        self.tmp = tempfile.mkdtemp()
        self._real_path = gui._settings_path
        gui._settings_path = lambda: os.path.join(self.tmp, "settings.json")
        self.root = tk.Tk()
        self.app = gui.App(self.root)

    def tearDown(self):
        self.root.destroy()
        self.gui._settings_path = self._real_path

    def test_the_radius_setting_becomes_a_circle_around_the_avatar(self):
        from avc.catch import CatchConfig

        self.app.spin_radius.set(300)
        cfg = self.app._spin_config(CatchConfig())

        x, y, w, h = cfg.spin_region
        self.assertEqual((600, 600), (w, h))
        self.assertEqual((610, 1750), (x + w // 2, y + h // 2))   # the avatar's feet

    def test_a_hand_drawn_circle_outranks_the_radius_setting(self):
        """The calibration box is the player's own measurement of what is in range; a number
        computed from a default must never quietly win over it."""
        from avc.catch import CatchConfig

        self.app.spin_radius.set(300)
        self.app.manual = {"_screen": [1220, 2712], "spin_region": [100, 1200, 950, 880]}
        cfg = self.app._apply_manual(
            self.app._spin_config(CatchConfig()).scale_to(1220, 2712, 480), "catch")

        self.assertEqual((100, 1200, 950, 880), cfg.spin_region)

    def test_the_circle_follows_the_phone_through_scale_to(self):
        from avc.catch import CatchConfig

        self.app.spin_radius.set(900)
        cfg = self.app._spin_config(CatchConfig()).scale_to(1080, 2400, 480)

        _x, _y, w, h = cfg.spin_region
        self.assertLess(w, 1800)       # a narrower screen draws a smaller map
        self.assertEqual(w, h)

    def test_every_calibration_handle_has_a_starting_position(self):
        """A field listed on a tab but missing from the defaults aborts the canvas redraw at
        that point: the handles before it are drawn, the rest are not, and nothing is logged —
        so the tab looks fine and simply refuses to be dragged."""
        import gui as gui_module

        defaults = self.app._cal_defaults(1220, 2712, 480)
        listed = {f for fields in gui_module.CALIB_GROUP_FIELDS.values() for f in fields}

        self.assertEqual(set(), listed - set(defaults))

    def test_the_scan_circle_handle_opens_where_the_radius_setting_puts_it(self):
        self.app.spin_radius.set(300)

        x, y, w, h = self.app._cal_defaults(1220, 2712, 480)["spin_region"]

        self.assertEqual((600, 600), (w, h))
        self.assertEqual((610, 1750), (x + w // 2, y + h // 2))

    def test_the_out_of_balls_hold_is_the_minutes_the_user_typed(self):
        from avc.catch import CatchConfig

        self.app.no_balls_min.set(4)
        self.assertEqual(240.0, self.app._spin_config(CatchConfig()).no_balls_pause)


if __name__ == "__main__":
    unittest.main()
