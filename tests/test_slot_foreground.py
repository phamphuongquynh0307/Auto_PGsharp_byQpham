import unittest

import cv2
import numpy as np

from avc.vision import slot_has_pokemon


class SlotForegroundTests(unittest.TestCase):
    @staticmethod
    def _empty_bar_with_map_edges():
        patch = np.full((110, 140, 3), 112, dtype=np.uint8)
        for x in range(35, 106, 12):
            cv2.line(patch, (x, 18), (x, 91), (60, 60, 60), 3)
        return patch

    @staticmethod
    def _foreground_sprite():
        patch = np.full((110, 140, 3), 112, dtype=np.uint8)
        cv2.rectangle(patch, (43, 23), (97, 87), (245, 245, 245), -1)
        for y in range(29, 88, 10):
            cv2.line(patch, (47, y), (93, y), (45, 45, 45), 3)
        return patch

    def test_old_texture_check_can_accept_darkened_map_edges(self):
        self.assertTrue(slot_has_pokemon(
            self._empty_bar_with_map_edges(), (70, 55), half_width=70, height=110,
            min_foreground_bright_fraction=0.0,
        ))

    def test_foreground_gate_rejects_darkened_map_edges(self):
        self.assertFalse(slot_has_pokemon(
            self._empty_bar_with_map_edges(), (70, 55), half_width=70, height=110,
            min_foreground_bright_fraction=0.008,
        ))

    def test_foreground_gate_keeps_a_bright_sprite(self):
        self.assertTrue(slot_has_pokemon(
            self._foreground_sprite(), (70, 55), half_width=70, height=110,
            min_foreground_bright_fraction=0.008,
        ))


if __name__ == "__main__":
    unittest.main()
