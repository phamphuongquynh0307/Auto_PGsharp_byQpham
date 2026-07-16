"""Auto Vision Clicker — desktop GUI.

A small tkinter control panel: pick the connected device, tune the catch settings,
and drive the catch routine with Play / Pause / Stop. The routine runs on a background
thread; log lines are marshalled back to the UI thread through a queue.

Two tabs: Control (device, run buttons, log) and Settings (tuning, Discord alerts,
language). All user-facing strings go through the LANG table so the UI can switch
between Vietnamese and English at runtime.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
import tkinter as tk
from tkinter import ttk

import cv2

from avc.catch import CatchConfig, CatchRoutine
from avc.device import Device

# Donate destinations shown on the Donate tab.
DONATE_PAYPAL = "https://paypal.me/CHANGE_ME"   # TODO: real PayPal.me link
DONATE_MOMO = "09xx xxx xxx"                     # TODO: real MoMo number

LANG = {
    "title":         {"vi": "Auto Catch Pokemon PGSharp", "en": "Auto Catch Pokemon PGSharp"},
    "tab_main":      {"vi": "Điều khiển", "en": "Control"},
    "tab_settings":  {"vi": "Cài đặt", "en": "Settings"},
    "tab_donate":    {"vi": "Ủng hộ ❤", "en": "Donate ❤"},
    "donate_msg":    {"vi": "Nếu app giúp bạn bắt được kha khá Pokémon, mời mình ly cà phê nhé ☕ Cảm ơn bạn!",
                      "en": "If this app catches you a good few Pokémon, consider buying me a coffee ☕ Thank you!"},
    "copy":          {"vi": "Sao chép", "en": "Copy"},
    "copied":        {"vi": "Đã chép ✓", "en": "Copied ✓"},
    "device":        {"vi": "Thiết bị:", "en": "Device:"},
    "refresh":       {"vi": "Làm mới", "en": "Refresh"},
    "grp_catch":     {"vi": "Bắt Pokémon", "en": "Catching"},
    "slot_offset":   {"vi": "Khoảng cách @ → ô đầu (px):", "en": "Distance @ → first slot (px):"},
    "throw_power":   {"vi": "Lực ném (px, càng lớn càng mạnh):", "en": "Throw power (px, higher = stronger):"},
    "wait_enc":      {"vi": "Chờ mở màn bắt tối đa (giây):", "en": "Max wait for encounter (s):"},
    "wait_catch":    {"vi": "Chờ bắt xong tối đa (giây):", "en": "Max wait after throw (s):"},
    "idle_aw":       {"vi": "Trống mấy lần thì AutoWalk (0=tắt):", "en": "Empty cycles before AutoWalk (0=off):"},
    "max_catches":   {"vi": "Giới hạn số con (0=∞):", "en": "Catch limit (0=∞):"},
    "dim":           {"vi": "Tắt sáng màn hình khi chạy (giảm nóng)", "en": "Screen off while running (less heat)"},
    "grp_discord":   {"vi": "Thông báo Discord", "en": "Discord alerts"},
    "webhook":       {"vi": "Webhook URL:", "en": "Webhook URL:"},
    "alert_idle":    {"vi": "Báo khi trống liên tiếp (chu kỳ, 0=tắt):", "en": "Alert after empty cycles in a row (0=off):"},
    "alert_report":  {"vi": "Báo cáo định kỳ (phút, 0=tắt):", "en": "Status report every (min, 0=off):"},
    "alert_batt":    {"vi": "Báo pin yếu dưới (%, 0=tắt):", "en": "Low battery alert below (%, 0=off):"},
    "language":      {"vi": "Ngôn ngữ / Language:", "en": "Language / Ngôn ngữ:"},
    "run":           {"vi": "▶ Chạy", "en": "▶ Run"},
    "pause":         {"vi": "⏸ Tạm dừng", "en": "⏸ Pause"},
    "resume":        {"vi": "▶ Tiếp tục", "en": "▶ Resume"},
    "stop":          {"vi": "⏹ Dừng", "en": "⏹ Stop"},
    "log_frame":     {"vi": "Nhật ký", "en": "Log"},
    "st_ready":      {"vi": "Sẵn sàng", "en": "Ready"},
    "st_running":    {"vi": "Đang chạy…", "en": "Running…"},
    "st_paused":     {"vi": "Tạm dừng", "en": "Paused"},
    "st_stopping":   {"vi": "Đang dừng…", "en": "Stopping…"},
    "st_no_device":  {"vi": "Không thấy thiết bị — cắm USB + bật gỡ lỗi", "en": "No device — plug USB + enable debugging"},
    "thrown":        {"vi": "Đã ném: {}", "en": "Thrown: {}"},
    "msg_started":   {"vi": "Bắt đầu (bật stream realtime).", "en": "Started (realtime stream on)."},
    "msg_dim":       {"vi": "Đã tắt sáng màn hình (game vẫn chạy nền).", "en": "Screen dimmed (game keeps running)."},
    "msg_throw":     {"vi": "NÉM BÓNG", "en": "THREW BALL"},
    "msg_empty":     {"vi": "(không có pokemon)", "en": "(no pokémon)"},
    "msg_cycle":     {"vi": "chu kỳ {}: {} | tổng ném: {}", "en": "cycle {}: {} | total thrown: {}"},
    "msg_autowalk":  {"vi": "→ Trống lâu, bấm AutoWalk đi kiếm spawn (lần {})", "en": "→ Dry spell, tapped AutoWalk to find spawns (#{})"},
    "msg_done":      {"vi": "Hoàn tất.", "en": "Done."},
    "msg_err":       {"vi": "Lỗi: {}", "en": "Error: {}"},
    "msg_no_init":   {"vi": "Không khởi tạo được: {}", "en": "Could not initialize: {}"},
    "msg_no_device": {"vi": "Chưa chọn thiết bị.", "en": "No device selected."},
    "msg_dev_err":   {"vi": "Lỗi liệt kê thiết bị: {}", "en": "Device listing error: {}"},
    "msg_resumed":   {"vi": "Tiếp tục.", "en": "Resumed."},
    "msg_paused":    {"vi": "Tạm dừng.", "en": "Paused."},
    "dc_alert":      {"vi": "⚠️ AutoClick: {} chu kỳ liên tiếp không thấy Pokémon (tổng đã ném: {})",
                      "en": "⚠️ AutoClick: {} cycles in a row with no Pokémon (total thrown: {})"},
    "dc_report":     {"vi": "📊 AutoClick: chạy {} phút | ném {} ({}/giờ) | {} chu kỳ{}",
                      "en": "📊 AutoClick: up {} min | thrown {} ({}/hr) | {} cycles{}"},
    "dc_batt_part":  {"vi": " | pin {}% ({}°C)", "en": " | battery {}% ({}°C)"},
    "dc_low_batt":   {"vi": "🔋 AutoClick: pin còn {}% — cắm sạc đi!", "en": "🔋 AutoClick: battery at {}% — plug in!"},
    "dc_stopped":    {"vi": "🛑 AutoClick dừng vì lỗi: {}", "en": "🛑 AutoClick stopped with error: {}"},
    "dc_sent":       {"vi": "Đã gửi cảnh báo Discord.", "en": "Discord alert sent."},
    "dc_fail":       {"vi": "Gửi Discord thất bại: {}", "en": "Discord send failed: {}"},
}

LANG_NAMES = [("vi", "Tiếng Việt"), ("en", "English")]


def _settings_path() -> str:
    """Store settings next to the exe (frozen) or the script (source)."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "settings.json")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.geometry("470x720")
        root.minsize(430, 640)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.routine: CatchRoutine | None = None
        self.device: Device | None = None
        self.worker: threading.Thread | None = None
        self.paused = False
        self._i18n: list[tuple] = []       # (widget, key) pairs retranslated on language switch
        self._status_key = "st_ready"
        self._last_throws = 0
        self._empty_streak = 0             # consecutive empty cycles, for the Discord alert
        self._alert_fired = False          # one alert per dry spell

        data = self._read_settings()
        self.lang = data.get("lang", "vi") if data.get("lang") in ("vi", "en") else "vi"

        self._build_ui()
        self._apply_settings(data)
        self._retranslate()
        self.refresh_devices()
        self.root.after(100, self._drain_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def tr(self, key: str) -> str:
        return LANG[key][self.lang]

    # -- UI construction ------------------------------------------------------
    def _label(self, parent, key, **grid):
        lbl = ttk.Label(parent, text=self.tr(key))
        if grid:
            lbl.grid(**grid)
        self._i18n.append((lbl, key))
        return lbl

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_donate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=self.tr("tab_main"))
        self.notebook.add(self.tab_settings, text=self.tr("tab_settings"))
        self.notebook.add(self.tab_donate, text=self.tr("tab_donate"))

        # ---- Control tab ----
        top = ttk.Frame(self.tab_main)
        top.pack(fill="x", **pad)
        self._label(top, "device").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(top, textvariable=self.device_var, state="readonly", width=22)
        self.device_combo.pack(side="left", padx=6)
        self.refresh_btn = ttk.Button(top, text=self.tr("refresh"), command=self.refresh_devices)
        self.refresh_btn.pack(side="left")
        self._i18n.append((self.refresh_btn, "refresh"))

        controls = ttk.Frame(self.tab_main)
        controls.pack(fill="x", **pad)
        self.play_btn = ttk.Button(controls, text=self.tr("run"), command=self.on_play)
        self.play_btn.pack(side="left", expand=True, fill="x", padx=3)
        self._i18n.append((self.play_btn, "run"))
        self.pause_btn = ttk.Button(controls, text=self.tr("pause"), command=self.on_pause, state="disabled")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=3)
        self.stop_btn = ttk.Button(controls, text=self.tr("stop"), command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=3)
        self._i18n.append((self.stop_btn, "stop"))

        status = ttk.Frame(self.tab_main)
        status.pack(fill="x", **pad)
        self.status_var = tk.StringVar(value=self.tr("st_ready"))
        ttk.Label(status, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.count_var = tk.StringVar(value=self.tr("thrown").format(0))
        ttk.Label(status, textvariable=self.count_var).pack(side="right")

        self.logframe = ttk.LabelFrame(self.tab_main, text=self.tr("log_frame"))
        self.logframe.pack(fill="both", expand=True, **pad)
        self._i18n.append((self.logframe, "log_frame"))
        self.log = tk.Text(self.logframe, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(self.logframe, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set)

        # ---- Settings tab ----
        catch_grp = ttk.LabelFrame(self.tab_settings, text=self.tr("grp_catch"))
        catch_grp.pack(fill="x", **pad)
        self._i18n.append((catch_grp, "grp_catch"))
        self.slot_offset = self._spin(catch_grp, "slot_offset", 0, 100, 1500, 770)
        self.throw_power = self._spin(catch_grp, "throw_power", 1, 200, 1400, 550)
        self.wait_enc = self._spin(catch_grp, "wait_enc", 2, 2, 15, 3.0, is_float=True)
        self.wait_catch = self._spin(catch_grp, "wait_catch", 3, 2, 20, 6.0, is_float=True)
        self.idle_aw = self._spin(catch_grp, "idle_aw", 4, 0, 20, 3)
        self.max_catches = self._spin(catch_grp, "max_catches", 5, 0, 9999, 0)
        self.dim_screen = tk.BooleanVar(value=False)
        dim_chk = ttk.Checkbutton(catch_grp, text=self.tr("dim"), variable=self.dim_screen)
        dim_chk.grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((dim_chk, "dim"))

        dc_grp = ttk.LabelFrame(self.tab_settings, text=self.tr("grp_discord"))
        dc_grp.pack(fill="x", **pad)
        self._i18n.append((dc_grp, "grp_discord"))
        self._label(dc_grp, "webhook", row=0, column=0, sticky="w", padx=6, pady=2)
        self.webhook_url = tk.StringVar()
        ttk.Entry(dc_grp, textvariable=self.webhook_url, width=34).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        self.alert_idle = self._spin(dc_grp, "alert_idle", 1, 0, 200, 10)
        self.alert_report = self._spin(dc_grp, "alert_report", 2, 0, 720, 30)
        self.alert_batt = self._spin(dc_grp, "alert_batt", 3, 0, 90, 20)
        dc_grp.columnconfigure(1, weight=1)

        # ---- Donate tab ----
        donate_msg = ttk.Label(self.tab_donate, text=self.tr("donate_msg"), wraplength=410, justify="left")
        donate_msg.pack(anchor="w", padx=14, pady=(16, 12))
        self._i18n.append((donate_msg, "donate_msg"))
        self._donate_row(self.tab_donate, "PayPal:", DONATE_PAYPAL, link=True)
        self._donate_row(self.tab_donate, "MoMo:", DONATE_MOMO, link=False)

        lang_row = ttk.Frame(self.tab_settings)
        lang_row.pack(fill="x", **pad)
        self._label(lang_row, "language").pack(side="left")
        self.lang_var = tk.StringVar(value=dict(LANG_NAMES)[self.lang])
        self.lang_combo = ttk.Combobox(lang_row, textvariable=self.lang_var, state="readonly",
                                       values=[name for _c, name in LANG_NAMES], width=14)
        self.lang_combo.pack(side="left", padx=6)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

    def _donate_row(self, parent, brand: str, value: str, link: bool) -> None:
        """One donate line: brand label, the address (clickable when it's a URL), a copy button."""
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=14, pady=4)
        ttk.Label(row, text=brand, width=8, font=("Segoe UI", 10, "bold")).pack(side="left")
        val = ttk.Label(row, text=value, foreground="#1a6fc4",
                        cursor="hand2" if link else "arrow",
                        font=("Segoe UI", 10, "underline" if link else "normal"))
        val.pack(side="left", padx=4)
        if link:
            val.bind("<Button-1>", lambda _e: webbrowser.open(value))
        copy_btn = ttk.Button(row, text=self.tr("copy"))
        copy_btn.config(command=lambda: self._copy_to_clipboard(value, copy_btn))
        copy_btn.pack(side="right")
        self._i18n.append((copy_btn, "copy"))

    def _copy_to_clipboard(self, text: str, btn: ttk.Button) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        btn.config(text=self.tr("copied"))
        self.root.after(1500, lambda: btn.config(text=self.tr("copy")))

    def _spin(self, parent, key, row, lo, hi, default, is_float=False):
        self._label(parent, key, row=row, column=0, sticky="w", padx=6, pady=2)
        var = tk.DoubleVar(value=default) if is_float else tk.IntVar(value=default)
        inc = 0.5 if is_float else 1
        spin = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10, increment=inc)
        spin.grid(row=row, column=1, sticky="e", padx=6, pady=2)
        parent.columnconfigure(1, weight=1)
        return var

    # -- language ---------------------------------------------------------------
    def _on_lang_change(self, _event=None) -> None:
        chosen = self.lang_var.get()
        for code, name in LANG_NAMES:
            if name == chosen:
                self.lang = code
                break
        self._retranslate()
        self.save_settings()

    def _retranslate(self) -> None:
        self.root.title(self.tr("title"))
        self.notebook.tab(0, text=self.tr("tab_main"))
        self.notebook.tab(1, text=self.tr("tab_settings"))
        self.notebook.tab(2, text=self.tr("tab_donate"))
        for widget, key in self._i18n:
            widget.config(text=self.tr(key))
        self.pause_btn.config(text=self.tr("resume" if self.paused else "pause"))
        self.status_var.set(self.tr(self._status_key))
        self.count_var.set(self.tr("thrown").format(self._last_throws))

    def _set_status(self, key: str) -> None:
        self._status_key = key
        self.status_var.set(self.tr(key))

    # -- settings persistence -------------------------------------------------
    def _read_settings(self) -> dict:
        try:
            with open(_settings_path(), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _apply_settings(self, data: dict) -> None:
        if not data:
            return
        self.slot_offset.set(data.get("slot_offset", int(self.slot_offset.get())))
        self.throw_power.set(data.get("throw_power", int(self.throw_power.get())))
        # Encounters take ~2-3s to open; a stored wait below that makes the routine give up
        # mid-load and re-tap from scratch every cycle, so clamp old too-low values.
        self.wait_enc.set(max(2.0, float(data.get("wait_enc", self.wait_enc.get()))))
        self.wait_catch.set(max(2.0, float(data.get("wait_catch", self.wait_catch.get()))))
        self.idle_aw.set(data.get("idle_aw", int(self.idle_aw.get())))
        self.max_catches.set(data.get("max_catches", int(self.max_catches.get())))
        self.dim_screen.set(data.get("dim_screen", False))
        self.webhook_url.set(data.get("webhook", ""))
        self.alert_idle.set(data.get("alert_idle", int(self.alert_idle.get())))
        self.alert_report.set(data.get("alert_report", int(self.alert_report.get())))
        self.alert_batt.set(data.get("alert_batt", int(self.alert_batt.get())))
        if data.get("device"):
            self.device_var.set(data["device"])

    def save_settings(self) -> None:
        data = {
            "slot_offset": int(self.slot_offset.get()),
            "throw_power": int(self.throw_power.get()),
            "wait_enc": float(self.wait_enc.get()),
            "wait_catch": float(self.wait_catch.get()),
            "idle_aw": int(self.idle_aw.get()),
            "max_catches": int(self.max_catches.get()),
            "dim_screen": bool(self.dim_screen.get()),
            "device": self.device_var.get(),
            "webhook": self.webhook_url.get().strip(),
            "alert_idle": int(self.alert_idle.get()),
            "alert_report": int(self.alert_report.get()),
            "alert_batt": int(self.alert_batt.get()),
            "lang": self.lang,
        }
        try:
            with open(_settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _on_close(self) -> None:
        if self.routine:
            self.routine.stop()
        # Best-effort: never leave the phone stuck at brightness 0 if closed mid-run.
        if self.device is not None:
            try:
                self.device.restore_dim()
            except Exception:  # noqa: BLE001
                pass
        self.save_settings()
        self.root.destroy()

    # -- device ---------------------------------------------------------------
    def refresh_devices(self) -> None:
        try:
            devices = Device.list_devices()
        except Exception as e:  # noqa: BLE001
            devices = []
            self._log(self.tr("msg_dev_err").format(e))
        self.device_combo["values"] = devices
        if devices and not self.device_var.get():
            self.device_var.set(devices[0])
        if not devices:
            self._set_status("st_no_device")

    # -- Discord alert ----------------------------------------------------------
    def _send_discord(self, content: str, shot: bool = False) -> None:
        """POST to the webhook on a short-lived thread so the catch loop never waits on it.
        With shot=True the current phone screen is attached as a JPEG (best effort — if the
        screen can't be grabbed, e.g. the device just dropped, the text still goes out)."""
        url = self.webhook_url.get().strip()
        if not url:
            return
        device = self.device

        def push() -> None:
            try:
                img = None
                if shot and device is not None:
                    try:
                        ok, buf = cv2.imencode(".jpg", device.screenshot(), [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                        if ok:
                            img = buf.tobytes()
                    except Exception:  # noqa: BLE001
                        img = None
                if img is None:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps({"content": content}).encode("utf-8"),
                        headers={"Content-Type": "application/json", "User-Agent": "AutoVisionClicker"},
                    )
                else:
                    boundary = uuid.uuid4().hex
                    body = (
                        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
                         f"Content-Type: application/json\r\n\r\n").encode("utf-8")
                        + json.dumps({"content": content}).encode("utf-8")
                        + (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; "
                           f"filename=\"screen.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode("utf-8")
                        + img
                        + f"\r\n--{boundary}--\r\n".encode("utf-8")
                    )
                    req = urllib.request.Request(
                        url,
                        data=body,
                        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                 "User-Agent": "AutoVisionClicker"},
                    )
                urllib.request.urlopen(req, timeout=15)
                self.log_queue.put(self.tr("dc_sent"))
            except Exception as e:  # noqa: BLE001
                self.log_queue.put(self.tr("dc_fail").format(e))

        threading.Thread(target=push, daemon=True).start()

    def _tick_alerts(self, stats, threw: bool) -> None:
        """Per-cycle Discord bookkeeping: dry-spell alert, periodic status report, low battery.
        Runs on the worker thread; battery reads are spaced out so the extra adb call is rare."""
        now = time.monotonic()

        # Dry spell: N empty cycles in a row, one message (with screenshot) per spell.
        if threw:
            self._empty_streak = 0
            self._alert_fired = False
        else:
            self._empty_streak += 1
            limit = int(self.alert_idle.get())
            if limit > 0 and self._empty_streak >= limit and not self._alert_fired:
                self._alert_fired = True
                self._send_discord(self.tr("dc_alert").format(self._empty_streak, stats.throws), shot=True)

        # Low battery: check every 2 minutes, alert once, re-arm after a decent recharge.
        batt_limit = int(self.alert_batt.get())
        level = None
        if batt_limit > 0 and now - self._last_batt_check >= 120:
            self._last_batt_check = now
            try:
                self._batt_last = self.device.battery_info()
            except Exception:  # noqa: BLE001
                self._batt_last = {}
            level = self._batt_last.get("level")
            if level is not None:
                if level <= batt_limit and not self._batt_fired:
                    self._batt_fired = True
                    self._send_discord(self.tr("dc_low_batt").format(level))
                elif level >= batt_limit + 10:
                    self._batt_fired = False

        # Heartbeat report: totals since start. Silence past the interval = something is wrong.
        report_min = int(self.alert_report.get())
        if report_min > 0 and now - self._last_report >= report_min * 60:
            self._last_report = now
            up_min = int((now - self._run_started) / 60)
            rate = round(stats.throws / max((now - self._run_started) / 3600, 1 / 60))
            part = ""
            if self._batt_last.get("level") is not None:
                part = self.tr("dc_batt_part").format(self._batt_last["level"], self._batt_last.get("temp", "?"))
            self._send_discord(self.tr("dc_report").format(up_min, stats.throws, rate, stats.cycles, part))

    # -- run control ----------------------------------------------------------
    def on_play(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        serial = self.device_var.get()
        if not serial:
            self._log(self.tr("msg_no_device"))
            return
        self.save_settings()
        cfg = CatchConfig(
            slot_offset_y=int(self.slot_offset.get()),
            throw_dy=-abs(int(self.throw_power.get())),
            encounter_timeout=max(2.0, float(self.wait_enc.get())),
            catch_timeout=max(2.0, float(self.wait_catch.get())),
            idle_before_autowalk=int(self.idle_aw.get()),
            max_catches=int(self.max_catches.get()),
        )
        try:
            self.device = Device(serial)
            self.routine = CatchRoutine(self.device, cfg)
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("msg_no_init").format(e))
            return

        self.paused = False
        self._empty_streak = 0
        self._alert_fired = False
        self._run_started = time.monotonic()
        self._last_report = time.monotonic()
        self._last_batt_check = 0.0
        self._batt_fired = False
        self._batt_last = {}
        self.worker = threading.Thread(target=self._run_worker, daemon=True)
        self.worker.start()
        self.play_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text=self.tr("pause"))
        self.stop_btn.config(state="normal")
        self._set_status("st_running")
        self._log(self.tr("msg_started"))

    def _run_worker(self) -> None:
        def on_event(stats, threw):
            if stats.last_event == "autowalk":
                self.log_queue.put(self.tr("msg_autowalk").format(stats.autowalks))
                return
            tag = self.tr("msg_throw") if threw else self.tr("msg_empty")
            self.log_queue.put(self.tr("msg_cycle").format(stats.cycles, tag, stats.throws))
            self.log_queue.put(f"__count__{stats.throws}")
            self._tick_alerts(stats, threw)

        dim = self.dim_screen.get()
        try:
            if dim:
                self.device.enable_dim()
                self.log_queue.put(self.tr("msg_dim"))
            self.device.start_stream()  # realtime H.264 capture
            self.routine.run(on_event=on_event)
            self.log_queue.put("__done__" + self.tr("msg_done"))
        except Exception as e:  # noqa: BLE001
            self.log_queue.put("__done__" + self.tr("msg_err").format(e))
            # The bot died while unattended — this is the alert that matters most.
            self._send_discord(self.tr("dc_stopped").format(e), shot=True)
        finally:
            self.device.stop_stream()
            if dim:
                self.device.restore_dim()

    def on_pause(self) -> None:
        if not self.routine:
            return
        if self.paused:
            self.routine.resume()
            self.paused = False
            self.pause_btn.config(text=self.tr("pause"))
            self._set_status("st_running")
            self._log(self.tr("msg_resumed"))
        else:
            self.routine.pause()
            self.paused = True
            self.pause_btn.config(text=self.tr("resume"))
            self._set_status("st_paused")
            self._log(self.tr("msg_paused"))

    def on_stop(self) -> None:
        if self.routine:
            self.routine.stop()
            self.routine.resume()  # unblock a paused loop so it can see the stop
        self._set_status("st_stopping")

    def _finish(self, message: str) -> None:
        self._set_status("st_ready")
        self.play_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text=self.tr("pause"))
        self.stop_btn.config(state="disabled")
        self.paused = False
        self._log(message)

    # -- log pump -------------------------------------------------------------
    def _drain_log(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg.startswith("__count__"):
                    self._last_throws = int(msg[len("__count__"):])
                    self.count_var.set(self.tr("thrown").format(self._last_throws))
                elif msg.startswith("__done__"):
                    self._finish(msg[len("__done__"):])
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _log(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
