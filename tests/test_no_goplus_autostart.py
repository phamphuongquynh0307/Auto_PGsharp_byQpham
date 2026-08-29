"""The bot must never switch Go Plus on, and must not end a Shundo run over a stray dialog.

Both come from one incident. Pokemon GO added another round button to the upper-right icon
rail shaped like the one the accessory detector keys on — red upper cap, dark centre — so the
out-of-balls path found it and tapped it. That turns Go Plus ON, and with Go Plus connected
PGSharp refuses every teleport, which is what Shundo and the Feed source are built on. The bot
was disabling itself, and the Shundo run then stopped with "Go Plus is connected".
"""
import unittest

import avc.catch as catch
import avc.vision as vision
from avc.catch import CatchConfig


class NoGoPlusAutoStartTests(unittest.TestCase):
    def test_the_accessory_detector_is_gone(self):
        """No threshold saves a detector whose target genuinely looks like another control."""
        self.assertFalse(hasattr(vision, "find_disconnected_goplus"))

    def test_nothing_can_ask_the_routine_to_start_go_plus(self):
        self.assertFalse(hasattr(catch.CatchRoutine, "_try_start_goplus"))
        for field in ("start_goplus_on_no_balls", "goplus_after_autowalk_wait"):
            self.assertNotIn(field, CatchConfig.__dataclass_fields__)

    def test_the_empty_bag_hold_still_has_a_refill_path(self):
        """Removing Go Plus must not leave an out-of-balls run with nothing to do: spinning
        stops refills the bag, and unlike Go Plus it needs no PGSharp key."""
        self.assertIn("spin_on_no_balls", CatchConfig.__dataclass_fields__)
        self.assertGreater(CatchConfig().no_balls_pause, 0)


if __name__ == "__main__":
    unittest.main()
