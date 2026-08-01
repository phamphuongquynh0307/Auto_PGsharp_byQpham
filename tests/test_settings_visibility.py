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

    def test_quick_catch_only_rows_are_hidden_while_catching_normally(self):
        self._configure("catch", "normal", advanced=True)

        # Read only inside CatchRoutine._quick_throw.
        self.assertFalse(self._shown("quick_flick"))
        self.assertFalse(self._shown("post_throw"))
        self.assertFalse(self._shown("flee_taps"))
        self.assertFalse(self._shown("flee_gap"))

    def test_quick_catch_shows_its_own_knobs(self):
        self._configure("catch", "quick")

        self.assertTrue(self._shown("quick_flick"))
        self.assertTrue(self._shown("flee_taps"))

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
            app.mode = "shundo"          # hides the whole catching group
            app._sync_settings_visibility()
            app.save_settings()
            root.destroy()

            with open(gui._settings_path(), encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(1234, saved["throw_power"])

            root = tk.Tk()
            reloaded = gui.App(root)
            self.assertEqual(1234, reloaded.throw_power.get())
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


if __name__ == "__main__":
    unittest.main()
