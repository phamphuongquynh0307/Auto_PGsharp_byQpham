"""Path resolution that works both from source and from a PyInstaller one-file bundle."""
from __future__ import annotations

import os
import sys


def resource_path(relative: str) -> str:
    """Absolute path to a bundled resource (e.g. 'templates/pokeball.png').

    PyInstaller unpacks data files to sys._MEIPASS at runtime; in a normal source checkout
    we resolve relative to the project root instead.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def find_adb() -> str:
    """Locate adb: a copy bundled next to us wins, otherwise fall back to PATH."""
    import shutil

    bundled = resource_path("adb/adb.exe")
    if os.path.exists(bundled):
        return bundled
    return shutil.which("adb") or "adb"
