"""Persistent diagnostics: a rotating log of everything the GUI shows, and a one-click report.

The routine already narrates itself in detail — `CatchRoutine._trace` explains which detector
fired and why — but that narration only ever reached the log pane, and the pane dies with the
window. So a user reporting "it works sometimes" has nothing to send, and the only way to find
out what their machine actually did was to guess. Faults that appear on one machine and not
another are exactly the ones that cannot be reasoned about without their side of the story.

Everything here is best-effort and swallows its own errors. Diagnostics that can stop a run are
worse than no diagnostics.
"""
from __future__ import annotations

import io
import json
import logging
import os
import platform
import sys
import time
import zipfile
from logging.handlers import RotatingFileHandler

LOG_NAME = "autoclick.log"
# ~1 MB holds a few hours of a talkative run; one backup means a report still covers the
# stretch before the failure rather than only the moment somebody noticed it.
MAX_BYTES = 1_000_000
BACKUPS = 1

# Where the shadow comparison lands (CatchRoutine._shadow_check). Kept out of autoclick.log
# on purpose: it is a machine-readable table for the author, not narration for the user, and
# mixing it into the pane would bury the messages the user is actually meant to read.
SHADOW_NAME = "doi-chieu.log"
SHADOW_MAX_BYTES = 400_000

_logger: logging.Logger | None = None
_log_error: str | None = None   # why the log file could not be opened, if it could not be


def base_dir() -> str:
    """Where the app keeps its writable files: next to the exe (frozen) or the project root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log_path() -> str:
    return os.path.join(base_dir(), LOG_NAME)


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    log = logging.getLogger("avc.diag")
    log.setLevel(logging.INFO)
    log.propagate = False
    try:
        handler = RotatingFileHandler(log_path(), maxBytes=MAX_BYTES,
                                      backupCount=BACKUPS, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        log.addHandler(handler)
    except OSError as e:
        # Read-only install dir, or the file is locked by another copy of the app. Running
        # without a log is a worse experience, not a broken one — but the report must say so,
        # otherwise an empty bundle reads as "nothing happened" instead of "nothing was written".
        global _log_error
        _log_error = str(e)
        log.addHandler(logging.NullHandler())
    _logger = log
    return log


def write(line: str) -> None:
    """Append one line to the log file. Never raises."""
    try:
        _get_logger().info(line)
    except Exception:  # noqa: BLE001 - diagnostics must never stop automation
        pass


def shadow_path() -> str:
    return os.path.join(base_dir(), SHADOW_NAME)


def shadow(line: str) -> None:
    """Append one comparison row. Never raises, and never grows without bound.

    Past the cap the file restarts rather than rotating. What this measures is a property of
    the device, not of the moment, so the newest rows answer the question as well as the
    oldest ones do — and a second file in the report would only be one more thing to explain.
    """
    try:
        path = shadow_path()
        if os.path.exists(path) and os.path.getsize(path) > SHADOW_MAX_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as fh:
            print(line, file=fh)
    except Exception:  # noqa: BLE001 - diagnostics must never stop automation
        pass


def session_banner(info: dict) -> None:
    """Open a new section in the log, stamped with what this run is running on.

    The header is the half of a bug report that users cannot be asked for reliably: screen size,
    density, and whether adb is going over USB or Wi-Fi are what separate "it is broken" from
    "it is a different phone" or "the link is slow".
    """
    write("=" * 72)
    write(f"PHIEN MOI  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    for key, value in info.items():
        write(f"  {key}: {value}")
    write("=" * 72)


def device_info(device, extra: dict | None = None) -> dict:
    """Best-effort facts about the connected phone. Missing entries are recorded as such."""
    info: dict = {}
    serial = getattr(device, "serial", None)
    info["thiet_bi"] = serial or "(mac dinh)"
    # A serial of the form ip:port is a TCP transport, i.e. Wi-Fi — the single most common
    # difference between a machine that runs steadily and one that does not.
    info["ket_noi"] = "Wi-Fi" if serial and ":" in serial else "USB"
    try:
        width, height = device.screen_size()
        info["do_phan_giai"] = f"{width}x{height}"
    except Exception:  # noqa: BLE001
        info["do_phan_giai"] = "(khong doc duoc)"
    try:
        info["mat_do_dpi"] = device.density() or "(khong doc duoc)"
    except Exception:  # noqa: BLE001
        info["mat_do_dpi"] = "(khong doc duoc)"
    info["stream"] = "bat" if getattr(device, "_stream", None) is not None else "tat"
    if extra:
        info.update(extra)
    return info


def _redacted_settings(path: str) -> str | None:
    """settings.json with the Discord webhook removed — it is a credential, not diagnostics."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if data.get("webhook"):
        data["webhook"] = "(da an)"
    return json.dumps(data, indent=2, ensure_ascii=False)


def export(dest: str, *, settings_path: str | None = None,
           screenshot=None, notes: dict | None = None) -> str:
    """Write a support zip to `dest` and return the path.

    A screenshot is included when one is supplied, because half the reports that reach the author
    are about a screen the detector read differently than the user did, and that is settled by
    looking at the frame rather than by describing it.
    """
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in (LOG_NAME, f"{LOG_NAME}.1"):
            path = os.path.join(base_dir(), name)
            if os.path.exists(path):
                bundle.write(path, name)
        timing = os.path.join(base_dir(), "timing.log")
        if os.path.exists(timing):
            bundle.write(timing, "timing.log")
        for name in (SHADOW_NAME, f"{SHADOW_NAME}.1"):
            path = os.path.join(base_dir(), name)
            if os.path.exists(path):
                bundle.write(path, name)
        if settings_path:
            settings = _redacted_settings(settings_path)
            if settings is not None:
                bundle.writestr("settings.json", settings)
        if screenshot is not None:
            try:
                import cv2

                ok, buf = cv2.imencode(".png", screenshot)
                if ok:
                    bundle.writestr("man_hinh.png", buf.tobytes())
            except Exception:  # noqa: BLE001
                pass
        bundle.writestr("he_thong.txt", _system_report(notes or {}))
    return dest


def _system_report(notes: dict) -> str:
    out = io.StringIO()
    out.write(f"Thoi diem xuat: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    out.write(f"He dieu hanh:   {platform.platform()}\n")
    out.write(f"Python:         {platform.python_version()}\n")
    out.write(f"Dong goi:       {'exe' if getattr(sys, 'frozen', False) else 'ma nguon'}\n")
    out.write(f"Thu muc log:    {base_dir()}\n")
    out.write(f"Ghi log:        {'LOI - ' + _log_error if _log_error else 'binh thuong'}\n")
    for key, value in notes.items():
        out.write(f"{key}: {value}\n")
    return out.getvalue()
