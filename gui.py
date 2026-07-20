"""Auto Vision Clicker — desktop GUI.

A small tkinter control panel: pick the connected device, tune the catch settings,
and drive the catch routine with Play / Pause / Stop. The routine runs on a background
thread; log lines are marshalled back to the UI thread through a queue.

Two tabs: Control (device, run buttons, log) and Settings (tuning, Discord alerts,
language). All user-facing strings go through the LANG table so the UI can switch
between Vietnamese and English at runtime.
"""
from __future__ import annotations

import base64
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
from avc.shundo import ShundoConfig, ShundoRoutine

# Donate destinations shown on the Donate tab.
DONATE_KOFI = "https://ko-fi.com/qpham7286"
DISCORD_INVITE = "https://discord.gg/QXSfKKPpG6"

# Manual-alignment items shown in the calibrate window.
# (config field, kind 'point'|'region', mode 'catch'|'shundo'|'both', i18n key, colour)
CALIB_ITEMS = [
    ("nearby_slot",   "point",  "catch",  "cal_nearby",  "#ff3030"),
    ("ball_fallback", "point",  "catch",  "cal_ball",    "#00c000"),
    ("flee_xy",       "point",  "both",   "cal_flee",    "#ffcc00"),
    ("ball_region",        "region", "catch",  "cal_camera",  "#00c000"),
    ("pokestop_close_xy",  "point",  "catch",  "cal_stop",    "#ff33cc"),
    ("out_of_balls_region","region", "catch",  "cal_noball",  "#ff8800"),
    ("pill_region",        "region", "shundo", "cal_pill",    "#3399ff"),
    ("camera_region",      "region", "shundo", "cal_scamera", "#00ccff"),
    ("toast_region",       "region", "shundo", "cal_toast",   "#cc66ff"),
]

LANG = {
    "title":         {"vi": "Auto Catch Pokemon PGSharp", "en": "Auto Catch Pokemon PGSharp"},
    "tab_main":      {"vi": "Điều khiển", "en": "Control"},
    "tab_settings":  {"vi": "Cài đặt", "en": "Settings"},
    "tab_donate":    {"vi": "Ủng hộ ❤", "en": "Donate ❤"},
    "tab_guide":     {"vi": "Hướng dẫn", "en": "Guide"},
    "guide_text":    {"vi": (
        "📖 HƯỚNG DẪN SỬ DỤNG\n"
        "\n"
        "① CHUẨN BỊ ĐIỆN THOẠI\n"
        "• Bật \"Tùy chọn nhà phát triển\" → bật \"Gỡ lỗi USB (USB debugging)\".\n"
        "• Mở Pokémon GO (PGSharp), vào tới màn hình bản đồ.\n"
        "• Điện thoại và máy tính phải chung một mạng Wi-Fi.\n"
        "\n"
        "② KẾT NỐI (nút \"Kết nối\")\n"
        "• Lần đầu: CẮM CÁP USB → bấm \"Kết nối\". App tự bật adb qua Wi-Fi và nhớ máy. "
        "Khi thấy báo \"có thể rút cáp USB\" là rút cáp ra được.\n"
        "• Lần sau: KHÔNG cần cáp. Mở app → chọn máy trong danh sách (hoặc bấm \"Kết nối\") "
        "là tự nối lại qua Wi-Fi.\n"
        "\n"
        "③ CHỌN CHẾ ĐỘ\n"
        "• \"Bắt Pokémon\": tự bắt các Pokémon ở thanh bên phải màn hình.\n"
        "• \"Shundo\": chỉ săn shiny / 100% IV theo cấu hình.\n"
        "\n"
        "④ CHẠY\n"
        "• Bấm ▶ Chạy để bắt đầu, ⏸ Tạm dừng, ⏹ Dừng.\n"
        "• Theo dõi hoạt động ở khung \"Nhật ký\" phía dưới.\n"
        "\n"
        "⑤ HẾT POKÉ BALL\n"
        "• Khi hết bóng, app tự thoát màn bắt, báo Discord, tạm ngừng 10 phút và vẫn tự di "
        "chuyển (AutoWalk) để đi kiếm bóng, rồi tự bắt lại.\n"
        "\n"
        "⑥ THÔNG BÁO DISCORD (tab Cài đặt)\n"
        "• Dán \"Webhook URL\" của kênh Discord để nhận cảnh báo: trống spawn lâu, báo cáo "
        "định kỳ, pin yếu, hết bóng, gặp shiny…\n"
        "\n"
        "⑦ MẸO\n"
        "• Cắm sạc khi chạy lâu; app có thể tự làm tối màn hình cho đỡ nóng (game vẫn chạy nền).\n"
        "• Nếu ném lệch: chỉnh \"Lực ném\" và \"Khoảng cách @ → ô đầu\" trong tab Cài đặt.\n"
        "• Mất kết nối: bấm \"Làm mới\" hoặc chọn lại máy trong danh sách để nối lại Wi-Fi.\n"
    ), "en": (
        "📖 USER GUIDE\n"
        "\n"
        "① PREPARE THE PHONE\n"
        "• Enable \"Developer options\" → turn on \"USB debugging\".\n"
        "• Open Pokémon GO (PGSharp) and reach the map screen.\n"
        "• The phone and PC must be on the same Wi-Fi network.\n"
        "\n"
        "② CONNECT (the \"Connect\" button)\n"
        "• First time: PLUG IN THE USB CABLE → click \"Connect\". The app switches adb to "
        "Wi-Fi and remembers the phone. When it says \"you can unplug the USB cable\", unplug it.\n"
        "• Next times: NO cable needed. Open the app → pick the phone from the list (or click "
        "\"Connect\") and it reconnects over Wi-Fi.\n"
        "\n"
        "③ PICK A MODE\n"
        "• \"Catching\": auto-catches the Pokémon in the right-side sidebar.\n"
        "• \"Shundo\": hunts only shiny / 100% IV per your settings.\n"
        "\n"
        "④ RUN\n"
        "• Click ▶ Run to start, ⏸ Pause, ⏹ Stop.\n"
        "• Watch activity in the \"Log\" box below.\n"
        "\n"
        "⑤ OUT OF POKÉ BALLS\n"
        "• When balls run out, the app leaves the encounter, alerts Discord, holds off catching "
        "for 10 minutes while still AutoWalking to find balls, then resumes.\n"
        "\n"
        "⑥ DISCORD ALERTS (Settings tab)\n"
        "• Paste a Discord channel \"Webhook URL\" to receive alerts: long dry spells, periodic "
        "reports, low battery, out of balls, shiny found…\n"
        "\n"
        "⑦ TIPS\n"
        "• Keep it charging for long runs; the app can dim the screen to stay cool (the game "
        "keeps running).\n"
        "• Throws off target? Tune \"Throw power\" and \"Distance @ → first slot\" in Settings.\n"
        "• Lost connection? Click \"Refresh\" or re-pick the phone from the list to reconnect Wi-Fi.\n"
    )},
    "donate_msg":    {"vi": "Nếu app giúp bạn bắt được kha khá Pokémon, mời mình ly cà phê nhé ☕ Cảm ơn bạn!",
                      "en": "If this app catches you a good few Pokémon, consider buying me a coffee ☕ Thank you!"},
    "copy":          {"vi": "Sao chép", "en": "Copy"},
    "copied":        {"vi": "Đã chép ✓", "en": "Copied ✓"},
    "device":        {"vi": "Thiết bị:", "en": "Device:"},
    "refresh":       {"vi": "Làm mới", "en": "Refresh"},
    "connect":       {"vi": "Kết nối", "en": "Connect"},
    "conn_msg":      {"vi": "Điện thoại đang nối với máy tính bằng gì?", "en": "How is the phone connected?"},
    "conn_usb":      {"vi": "USB (cắm cáp)", "en": "USB (cable)"},
    "conn_wifi":     {"vi": "Wi-Fi (rút được cáp)", "en": "Wi-Fi (cable-free)"},
    "conn_need_usb": {"vi": "Cần cắm cáp USB trước, sau đó mới bật được chế độ Wi-Fi.",
                      "en": "Plug in the USB cable first, then Wi-Fi mode can be enabled."},
    "conn_working":  {"vi": "Đang bật adb qua Wi-Fi…", "en": "Enabling adb over Wi-Fi…"},
    "conn_wifi_ok":  {"vi": "✓ Đã kết nối Wi-Fi ({}) — bây giờ có thể rút cáp USB.",
                      "en": "✓ Wi-Fi connected ({}) — you can unplug the USB cable now."},
    "conn_wifi_fail": {"vi": "Kết nối Wi-Fi thất bại: {}", "en": "Wi-Fi connect failed: {}"},
    "conn_usb_ok":   {"vi": "Đã chọn thiết bị USB: {}", "en": "USB device selected: {}"},
    "conn_re_ok":    {"vi": "✓ Tự kết nối lại Wi-Fi ({}).", "en": "✓ Reconnected over Wi-Fi ({})."},
    "conn_reconnecting": {"vi": "Đang kết nối lại Wi-Fi…", "en": "Reconnecting over Wi-Fi…"},
    "conn_re_fail":  {"vi": "Kết nối lại thất bại — cắm cáp USB để bật lại Wi-Fi.",
                      "en": "Reconnect failed — plug in the USB cable to re-enable Wi-Fi."},
    "pick_usb":      {"vi": "Đang cắm nhiều máy — chọn máy:", "en": "Multiple phones plugged in — pick one:"},
    "grp_catch":     {"vi": "Bắt Pokémon", "en": "Catching"},
    "slot_offset":   {"vi": "Khoảng cách @ → ô đầu (px):", "en": "Distance @ → first slot (px):"},
    "throw_power":   {"vi": "Lực ném (px, càng lớn càng mạnh):", "en": "Throw power (px, higher = stronger):"},
    "wait_enc":      {"vi": "Chờ mở màn bắt tối đa (giây):", "en": "Max wait for encounter (s):"},
    "wait_catch":    {"vi": "Chờ bắt xong tối đa (giây):", "en": "Max wait after throw (s):"},
    "idle_aw":       {"vi": "Trống mấy lần thì AutoWalk (0=tắt):", "en": "Empty cycles before AutoWalk (0=off):"},
    "max_catches":   {"vi": "Giới hạn số con (0=∞):", "en": "Catch limit (0=∞):"},
    "dim":           {"vi": "Tắt sáng màn hình khi chạy (giảm nóng)", "en": "Screen off while running (less heat)"},
    "mode":          {"vi": "Chế độ:", "en": "Mode:"},
    "preview":       {"vi": "👁 Xem bot nhìn", "en": "👁 Live view"},
    "calibrate":     {"vi": "🎯 Căn chỉnh tay", "en": "🎯 Manual align"},
    "cal_title":     {"vi": "Căn chỉnh tay — kéo các điểm/khung vào đúng chỗ",
                      "en": "Manual alignment — drag points/boxes into place"},
    "cal_hint":      {"vi": "Kéo dấu (+) tới đúng nút/pokémon; kéo góc khung để đổi kích thước. "
                            "Lưu xong bot dùng đúng các điểm này (tắt dò '@').",
                      "en": "Drag each (+) onto the right button/pokémon; drag a box corner to resize. "
                            "After saving, the bot uses these exact spots (auto-detect off)."},
    "cal_save":      {"vi": "Lưu", "en": "Save"},
    "cal_reset":     {"vi": "Đặt lại mặc định", "en": "Reset to default"},
    "cal_cancel":    {"vi": "Hủy", "en": "Cancel"},
    "cal_refresh":   {"vi": "Chụp lại", "en": "Recapture"},
    "cal_saved":     {"vi": "Đã lưu căn chỉnh tay.", "en": "Manual alignment saved."},
    "cal_cleared":   {"vi": "Đã xóa căn chỉnh tay (về tự động).", "en": "Manual alignment cleared (back to auto)."},
    "cal_mismatch":  {"vi": "⚠ Căn chỉnh tay thuộc độ phân giải khác — bỏ qua. Hãy căn lại.",
                      "en": "⚠ Manual alignment was for a different resolution — ignored. Please re-align."},
    "cal_nearby":    {"vi": "Điểm bấm Pokémon (nearby)", "en": "Pokémon tap (nearby)"},
    "cal_ball":      {"vi": "Điểm ném bóng", "en": "Ball throw point"},
    "cal_flee":      {"vi": "Nút Flee (thoát)", "en": "Flee button"},
    "cal_camera":    {"vi": "Khung camera (Bắt)", "en": "Camera box (Catch)"},
    "cal_pill":      {"vi": "Khung IV pill (Shundo)", "en": "IV pill box (Shundo)"},
    "cal_scamera":   {"vi": "Khung camera (Shundo)", "en": "Camera box (Shundo)"},
    "cal_stop":      {"vi": "Nút đóng Pokéstop (X)", "en": "Pokéstop close (X)"},
    "cal_noball":    {"vi": "Khung 'hết bóng' (x0)", "en": "Out-of-balls box (x0)"},
    "cal_toast":     {"vi": "Khung toast (Shundo)", "en": "Toast box (Shundo)"},
    "pv_legend":     {"vi": "Xanh lá = ô feed sẽ bấm • Vàng nhạt = thanh @ / ô spawn • Vàng = điểm tap dưới chân • "
                            "Hồng = vòng Pokémon • Cam = vùng đọc IV • Trắng = vùng toast • Đỏ = đang trong màn bắt",
                      "en": "Green = feed tap • Pale yellow = @ bar / spawn slot • Yellow = feet tap point • "
                            "Pink = Pokémon rings • Orange = IV read area • White = toast area • Red = in encounter"},
    "pv_err":        {"vi": "Không mở được xem trực tiếp: {}", "en": "Could not open live view: {}"},
    "mode_catch":    {"vi": "Auto bắt Pokémon", "en": "Auto catch"},
    "mode_shundo":   {"vi": "Chấm shundo (shiny 100 IV)", "en": "Shundo check (shiny 100 IV)"},
    "grp_shundo":    {"vi": "Chấm shundo", "en": "Shundo check"},
    "shundo_note":   {"vi": "Cần bật chặn không-shiny trong PGSharp (encounter chỉ mở khi shiny).",
                      "en": "Requires PGSharp's non-shiny block (encounters only open for shinies)."},
    "tp_wait":       {"vi": "Chờ dịch chuyển tới con mới (giây):", "en": "Teleport wait (s):"},
    "s_enc_wait":    {"vi": "Chờ máy ảnh hiện tối đa (giây):", "en": "Wait for camera icon (s):"},
    "alert_shiny":   {"vi": "Báo Discord khi gặp shiny chưa đủ 100 IV", "en": "Discord alert on shiny below 100 IV"},
    "shundo_action": {"vi": "Khi thấy shundo:", "en": "On shundo:"},
    "shiny_action":  {"vi": "Khi shiny (chưa 100 IV):", "en": "On shiny (below 100 IV):"},
    "act_pause":     {"vi": "Tạm dừng chờ tôi bắt", "en": "Pause and wait for me"},
    "act_stop":      {"vi": "Dừng hẳn bot", "en": "Stop the bot"},
    "act_skip":      {"vi": "Thoát, soi con khác", "en": "Flee and keep hunting"},
    "msg_s_shiny_skip": {"vi": "✨ shiny (chưa đủ 100 IV) — thoát, soi con tiếp.",
                         "en": "✨ shiny (below 100 IV) — fled, hunting next."},
    "dc_shiny_skip": {"vi": "✨ SHINY (chưa đủ 100 IV) — đã bỏ qua, soi tiếp. (đã soi {} con)",
                      "en": "✨ SHINY (below 100 IV) — skipped, still hunting. ({} checked)"},
    "s_counts":      {"vi": "Soi: {} | shiny: {} | shundo: {}", "en": "Checked: {} | shiny: {} | shundo: {}"},
    "msg_s_blocked": {"vi": "soi {}: không shiny (bị chặn) | shiny {} | shundo {}",
                      "en": "check {}: not shiny (blocked) | shiny {} | shundo {}"},
    "msg_s_shiny":   {"vi": "✨ SHINY! Bot {} — vào máy xử lý!", "en": "✨ SHINY! Bot {} — go handle it!"},
    "st_shiny":      {"vi": "✨ SHINY — chờ bạn xử lý!", "en": "✨ SHINY — waiting for you!"},
    "msg_s_shundo":  {"vi": "🌟💯 SHUNDO!!! Bot {} — vào máy bắt ngay!", "en": "🌟💯 SHUNDO!!! Bot {} — go catch it now!"},
    "msg_s_idle":    {"vi": "(không thấy thanh feed / thanh @ — kiểm tra PGSharp)", "en": "(feed / @ bar not found — check PGSharp)"},
    "msg_s_miss":    {"vi": "(double-tap chưa được trả lời — thử lại)", "en": "(double-tap got no answer — retrying)"},
    "msg_s_nospawn": {"vi": "(pokemon chưa hiện lên thanh @ sau khi dịch chuyển — thử lại)",
                      "en": "(pokémon never showed in the @ bar after teleport — retrying)"},
    "msg_s_waiting": {"vi": "… đang chờ pokemon load ({}s)", "en": "… waiting for pokémon to load ({}s)"},
    "st_shundo":     {"vi": "🌟 SHUNDO — chờ bạn xử lý!", "en": "🌟 SHUNDO — waiting for you!"},
    "dc_shundo":     {"vi": "🌟💯 SHUNDO phát hiện! Bot {} — vào bắt ngay! (đã soi {} con, shiny {})",
                      "en": "🌟💯 SHUNDO found! Bot {} — go catch it! ({} checked, {} shiny)"},
    "dc_shundo_pause": {"vi": "tạm dừng, encounter đang mở", "en": "paused with the encounter open"},
    "dc_shundo_stop":  {"vi": "đã dừng hẳn, encounter đang mở", "en": "stopped with the encounter open"},
    "dc_shiny":      {"vi": "✨ SHINY phát hiện (chưa đủ 100 IV)! Bot {} — vào xử lý! (đã soi {} con)",
                      "en": "✨ SHINY found (below 100 IV)! Bot {} — go handle it! ({} checked)"},
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
    "msg_no_balls":  {"vi": "→ Hết Poké Ball! Thoát màn bắt, tạm ngừng 10 phút (vẫn tự di chuyển).", "en": "→ Out of Poké Balls! Left the encounter, holding off 10 min (still auto-walking)."},
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
    "dc_no_balls":   {"vi": "🎱 AutoClick: Hết Poké Ball! Đã thoát màn bắt, tạm ngừng 10 phút và bật tự di chuyển.", "en": "🎱 AutoClick: Out of Poké Balls! Left the catch screen, pausing 10 min and auto-walking."},
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
        root.geometry("470x780")
        root.minsize(430, 700)

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
        self._reconnecting = False         # background Wi-Fi re-connect in flight

        data = self._read_settings()
        self.lang = data.get("lang", "vi") if data.get("lang") in ("vi", "en") else "vi"
        # Every device ever connected, most recent first; shown in the picker even when
        # currently offline, and Wi-Fi ones are re-connected automatically.
        self.known: list[str] = [s for s in data.get("known_devices", []) if isinstance(s, str)][:10]
        # Manual alignment: device-pixel overrides for tap points / detection boxes, keyed by
        # field name; "_screen" stores the resolution they were set at. Empty = full auto.
        self.manual: dict = data.get("manual", {}) if isinstance(data.get("manual"), dict) else {}

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
        self.tab_guide = ttk.Frame(self.notebook)
        self.tab_donate = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=self.tr("tab_main"))
        self.notebook.add(self.tab_settings, text=self.tr("tab_settings"))
        self.notebook.add(self.tab_guide, text=self.tr("tab_guide"))
        self.notebook.add(self.tab_donate, text=self.tr("tab_donate"))

        # ---- Control tab ----
        top = ttk.Frame(self.tab_main)
        top.pack(fill="x", **pad)
        self._label(top, "device").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(top, textvariable=self.device_var, state="readonly", width=22)
        self.device_combo.pack(side="left", padx=6)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_pick)
        self.connect_btn = ttk.Button(top, text=self.tr("connect"), command=self._connect_smart)
        self.connect_btn.pack(side="left")
        self._i18n.append((self.connect_btn, "connect"))
        self.refresh_btn = ttk.Button(top, text=self.tr("refresh"), command=self.refresh_devices)
        self.refresh_btn.pack(side="left", padx=4)
        self._i18n.append((self.refresh_btn, "refresh"))

        mode_row = ttk.Frame(self.tab_main)
        mode_row.pack(fill="x", **pad)
        self._label(mode_row, "mode").pack(side="left")
        self.mode = "catch"            # "catch" | "shundo"
        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(mode_row, textvariable=self.mode_var, state="readonly", width=28)
        self.mode_combo.pack(side="left", padx=6)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        self.preview_btn = ttk.Button(mode_row, text=self.tr("preview"), command=self.toggle_preview)
        self.preview_btn.pack(side="right")
        self._i18n.append((self.preview_btn, "preview"))
        self.calib_btn = ttk.Button(mode_row, text=self.tr("calibrate"), command=self.open_calibrate)
        self.calib_btn.pack(side="right", padx=4)
        self._i18n.append((self.calib_btn, "calibrate"))

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

        sh_grp = ttk.LabelFrame(self.tab_settings, text=self.tr("grp_shundo"))
        sh_grp.pack(fill="x", **pad)
        self._i18n.append((sh_grp, "grp_shundo"))
        note = ttk.Label(sh_grp, text=self.tr("shundo_note"), wraplength=400, foreground="#666")
        note.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 4))
        self._i18n.append((note, "shundo_note"))
        self.tp_wait = self._spin(sh_grp, "tp_wait", 1, 2, 15, 4.0, is_float=True)
        self.s_enc_wait = self._spin(sh_grp, "s_enc_wait", 2, 2, 12, 3.0, is_float=True)
        self._label(sh_grp, "shundo_action", row=3, column=0, sticky="w", padx=6, pady=2)
        self.shundo_action = "pause"   # "pause" | "stop"
        self.action_var = tk.StringVar()
        self.action_combo = ttk.Combobox(sh_grp, textvariable=self.action_var, state="readonly", width=22)
        self.action_combo.grid(row=3, column=1, sticky="e", padx=6, pady=2)
        self.action_combo.bind("<<ComboboxSelected>>", self._on_action_change)
        self._label(sh_grp, "shiny_action", row=4, column=0, sticky="w", padx=6, pady=2)
        self.shiny_action = "skip"     # "skip" | "pause"
        self.shiny_action_var = tk.StringVar()
        self.shiny_action_combo = ttk.Combobox(sh_grp, textvariable=self.shiny_action_var,
                                                state="readonly", width=22)
        self.shiny_action_combo.grid(row=4, column=1, sticky="e", padx=6, pady=2)
        self.shiny_action_combo.bind("<<ComboboxSelected>>", self._on_shiny_action_change)
        # A skipped shiny still alerts Discord (with screenshot), it just isn't waited on.
        self.alert_shiny = tk.BooleanVar(value=True)

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
        self._donate_row(self.tab_donate, "Ko-fi:", DONATE_KOFI, link=True)
        self._donate_row(self.tab_donate, "Discord:", DISCORD_INVITE, link=True)

        # ---- Guide tab ---- (read-only, scrollable, retranslated on language switch)
        gframe = ttk.Frame(self.tab_guide)
        gframe.pack(fill="both", expand=True, padx=8, pady=8)
        gscroll = ttk.Scrollbar(gframe, orient="vertical")
        gscroll.pack(side="right", fill="y")
        self.guide_text = tk.Text(gframe, wrap="word", yscrollcommand=gscroll.set,
                                  font=("Segoe UI", 10), relief="flat", borderwidth=0,
                                  padx=6, pady=4, height=10, cursor="arrow")
        self.guide_text.pack(side="left", fill="both", expand=True)
        gscroll.config(command=self.guide_text.yview)
        self._set_guide_text()

        lang_row = ttk.Frame(self.tab_settings)
        lang_row.pack(fill="x", **pad)
        self._label(lang_row, "language").pack(side="left")
        self.lang_var = tk.StringVar(value=dict(LANG_NAMES)[self.lang])
        self.lang_combo = ttk.Combobox(lang_row, textvariable=self.lang_var, state="readonly",
                                       values=[name for _c, name in LANG_NAMES], width=14)
        self.lang_combo.pack(side="left", padx=6)
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_lang_change)

    def _set_guide_text(self) -> None:
        """Fill the guide box with the current language's text (read-only)."""
        self.guide_text.config(state="normal")
        self.guide_text.delete("1.0", "end")
        self.guide_text.insert("1.0", self.tr("guide_text"))
        self.guide_text.config(state="disabled")

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

    # -- mode / shundo action selectors ----------------------------------------
    MODES = (("catch", "mode_catch"), ("shundo", "mode_shundo"))
    ACTIONS = (("pause", "act_pause"), ("stop", "act_stop"))
    SHINY_ACTIONS = (("skip", "act_skip"), ("pause", "act_pause"))

    def _refresh_choice(self, combo: ttk.Combobox, var: tk.StringVar, pairs, code: str) -> None:
        combo["values"] = [self.tr(k) for _c, k in pairs]
        var.set(self.tr(dict(pairs)[code]))

    def _code_from_choice(self, var: tk.StringVar, pairs, fallback: str) -> str:
        for code, key in pairs:
            if var.get() == self.tr(key):
                return code
        return fallback

    def _on_mode_change(self, _event=None) -> None:
        self.mode = self._code_from_choice(self.mode_var, self.MODES, self.mode)
        self.save_settings()

    def _on_action_change(self, _event=None) -> None:
        self.shundo_action = self._code_from_choice(self.action_var, self.ACTIONS, self.shundo_action)
        self.save_settings()

    def _on_shiny_action_change(self, _event=None) -> None:
        self.shiny_action = self._code_from_choice(self.shiny_action_var, self.SHINY_ACTIONS, self.shiny_action)
        self.save_settings()

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
        self.notebook.tab(self.tab_main, text=self.tr("tab_main"))
        self.notebook.tab(self.tab_settings, text=self.tr("tab_settings"))
        self.notebook.tab(self.tab_guide, text=self.tr("tab_guide"))
        self.notebook.tab(self.tab_donate, text=self.tr("tab_donate"))
        self._set_guide_text()
        for widget, key in self._i18n:
            widget.config(text=self.tr(key))
        self.pause_btn.config(text=self.tr("resume" if self.paused else "pause"))
        self.status_var.set(self.tr(self._status_key))
        self.count_var.set(self.tr("thrown").format(self._last_throws))
        self._refresh_choice(self.mode_combo, self.mode_var, self.MODES, self.mode)
        self._refresh_choice(self.action_combo, self.action_var, self.ACTIONS, self.shundo_action)
        self._refresh_choice(self.shiny_action_combo, self.shiny_action_var, self.SHINY_ACTIONS, self.shiny_action)

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
        if data.get("mode") in ("catch", "shundo"):
            self.mode = data["mode"]
        self.tp_wait.set(max(2.0, float(data.get("tp_wait", self.tp_wait.get()))))
        self.s_enc_wait.set(max(2.0, float(data.get("s_enc_wait", self.s_enc_wait.get()))))
        if data.get("shundo_action") in ("pause", "stop"):
            self.shundo_action = data["shundo_action"]
        if data.get("shiny_action") in ("skip", "pause"):
            self.shiny_action = data["shiny_action"]
        self.alert_shiny.set(data.get("alert_shiny", True))
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
            "mode": self.mode,
            "tp_wait": float(self.tp_wait.get()),
            "s_enc_wait": float(self.s_enc_wait.get()),
            "shundo_action": self.shundo_action,
            "shiny_action": self.shiny_action,
            "alert_shiny": bool(self.alert_shiny.get()),
            "device": self._sel_serial(),
            "known_devices": self.known,
            "webhook": self.webhook_url.get().strip(),
            "alert_idle": int(self.alert_idle.get()),
            "alert_report": int(self.alert_report.get()),
            "alert_batt": int(self.alert_batt.get()),
            "lang": self.lang,
            "manual": self.manual,
        }
        try:
            with open(_settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _on_close(self) -> None:
        if self.routine:
            self.routine.stop()
        # Let the worker unwind (its finally stops the stream and restores brightness) so no adb
        # child process is left holding files when we exit.
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=3.0)
        if self.device is not None:
            # Best-effort: never leave the phone stuck at brightness 0 if closed mid-run.
            try:
                self.device.restore_dim()
            except Exception:  # noqa: BLE001
                pass
            try:
                self.device.stop_stream()
            except Exception:  # noqa: BLE001
                pass
            # Frozen one-file build: the adb daemon's image lives in PyInstaller's _MEI temp dir;
            # kill it so that dir can be removed on exit (otherwise Windows shows a
            # 'Failed to remove temporary directory' warning).
            try:
                self.device.kill_server()
            except Exception:  # noqa: BLE001
                pass
        self.save_settings()
        self.root.destroy()

    # -- device ---------------------------------------------------------------
    OFFLINE_TAG = " (offline)"

    def _sel_serial(self) -> str:
        """The selected serial with the '(offline)' decoration stripped."""
        return self.device_var.get().replace(self.OFFLINE_TAG, "").strip()

    def _remember_device(self, serial: str) -> None:
        """Put `serial` at the front of the known-devices history (deduped, capped)."""
        if not serial:
            return
        self.known = ([serial] + [s for s in self.known if s != serial])[:10]
        self.save_settings()

    def _on_device_pick(self, _event=None) -> None:
        serial = self._sel_serial()
        self._remember_device(serial)
        # Picking an offline Wi-Fi device from the list is a request to reconnect it (the
        # cable-free "second time" path): bring it straight back over Wi-Fi.
        if ":" in serial:
            try:
                attached = Device.list_devices()
            except Exception:  # noqa: BLE001
                attached = []
            if serial not in attached:
                self._reconnect_wifi([serial])
                return
        self.refresh_devices()

    def refresh_devices(self) -> None:
        try:
            attached = Device.list_devices()
        except Exception as e:  # noqa: BLE001
            attached = []
            self._log(self.tr("msg_dev_err").format(e))
        # Show every known device: attached ones plain, remembered-but-absent ones tagged.
        options = attached + [s + self.OFFLINE_TAG for s in self.known if s not in attached]
        self.device_combo["values"] = options
        cur = self._sel_serial()
        if cur:
            self.device_var.set(cur if cur in attached else
                                (cur + self.OFFLINE_TAG if cur in self.known else cur))
        elif attached:
            self.device_var.set(attached[0])
        elif options:
            self.device_var.set(options[0])
        if not attached:
            self._set_status("st_no_device")
        # Known Wi-Fi devices that aren't attached (adb server restarted, PC rebooted):
        # try to re-establish them all in the background while the phones' adbd is still
        # in TCP mode. On success the list is refreshed and they show up again.
        missing_wifi = [s for s in self.known if ":" in s and s not in attached]
        if missing_wifi and not self._reconnecting:
            self._reconnecting = True

            def rejoin() -> None:
                regained = False
                try:
                    for serial in missing_wifi:
                        try:
                            Device.adb_connect(serial)
                            self.log_queue.put(self.tr("conn_re_ok").format(serial))
                            regained = True
                        except Exception:  # noqa: BLE001
                            pass
                finally:
                    self._reconnecting = False
                if regained:
                    self.root.after(0, self.refresh_devices)

            threading.Thread(target=rejoin, daemon=True).start()

    def _connect_smart(self) -> None:
        """One-tap connect, no USB/Wi-Fi question asked.
        • First time (USB cable plugged in): switch the phone to adb-over-Wi-Fi and remember that
          wireless serial, so the cable can then be unplugged.
        • Later (no cable): reconnect the remembered Wi-Fi device — the same thing that picking
          it from the list does.
        If Wi-Fi can't be enabled it still connects over the cable, so you're never stuck."""
        if self._usb_devices():
            # Cable plugged in → set up (or refresh) Wi-Fi so future connects are cable-free.
            self._connect_wifi()
            return
        # No cable → bring back a remembered Wi-Fi device (its adbd is still in TCP mode).
        wifi_known = [s for s in self.known if ":" in s]
        if wifi_known:
            self._reconnect_wifi(wifi_known)
            return
        self._log(self.tr("conn_need_usb"))
        self._set_status("st_no_device")

    def _reconnect_wifi(self, serials: list[str]) -> None:
        """Reconnect remembered Wi-Fi device(s) without a cable: the phone's adbd stayed in TCP
        mode from the first cable setup, so a plain `adb connect ip:port` brings it back. Runs on
        a thread (connect can take a few seconds) and selects the first serial that comes back."""
        self.connect_btn.config(state="disabled")
        self._log(self.tr("conn_reconnecting"))

        def work() -> None:
            got = None
            for s in serials:
                try:
                    Device.adb_connect(s)
                    got = s
                    break
                except Exception:  # noqa: BLE001
                    pass

            def done() -> None:
                self.connect_btn.config(state="normal")
                self.refresh_devices()
                if got:
                    self.device_var.set(got)
                    self._remember_device(got)
                    self._log(self.tr("conn_re_ok").format(got))
                else:
                    self._log(self.tr("conn_re_fail"))
                    self._set_status("st_no_device")

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _usb_devices(self) -> list[str]:
        try:
            return [d for d in Device.list_devices() if ":" not in d]
        except Exception:  # noqa: BLE001
            return []

    def _pick_usb(self, then) -> None:
        """Run `then(serial)` on a USB device — directly when one is plugged in, via a
        small picker dialog when several are."""
        usb = self._usb_devices()
        if not usb:
            self._log(self.tr("conn_need_usb"))
            self._set_status("st_no_device")
            return
        if len(usb) == 1:
            then(usb[0])
            return
        dlg = tk.Toplevel(self.root)
        dlg.title(self.tr("connect"))
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        ttk.Label(dlg, text=self.tr("pick_usb")).pack(padx=16, pady=(14, 8))
        for serial in usb:
            ttk.Button(dlg, text=serial, width=30,
                       command=lambda s=serial: (dlg.destroy(), then(s))).pack(padx=16, pady=3)
        ttk.Frame(dlg).pack(pady=6)

    def _connect_wifi(self) -> None:
        """Turn on adb-over-Wi-Fi via the USB cable, then hand the GUI the Wi-Fi serial.
        Runs on a thread: tcpip + connect take a few seconds and must not freeze the UI."""

        def start(usb_serial: str) -> None:
            self.connect_btn.config(state="disabled")
            self._log(self.tr("conn_working"))

            def work() -> None:
                try:
                    serial = Device(usb_serial).enable_wifi_adb()
                    self.log_queue.put(self.tr("conn_wifi_ok").format(serial))

                    def adopt() -> None:
                        self.refresh_devices()
                        self.device_var.set(serial)
                        self._remember_device(serial)

                    self.root.after(0, adopt)
                except Exception as e:  # noqa: BLE001
                    # Wi-Fi couldn't be enabled (phone Wi-Fi off, etc.) — fall back to the plain
                    # USB connection so the user is still connected and can run over the cable.
                    self.log_queue.put(self.tr("conn_wifi_fail").format(e))

                    def adopt_usb() -> None:
                        self.refresh_devices()
                        self.device_var.set(usb_serial)
                        self._remember_device(usb_serial)
                        self._log(self.tr("conn_usb_ok").format(usb_serial))

                    self.root.after(0, adopt_usb)
                finally:
                    self.root.after(0, lambda: self.connect_btn.config(state="normal"))

            threading.Thread(target=work, daemon=True).start()

        self._pick_usb(start)

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

    def _tick_alerts(self, stats, threw: bool, *, shundo: bool = False) -> None:
        """Per-cycle Discord bookkeeping: dry-spell alert, periodic status report, low battery.
        Shundo mode keeps only the battery alert — its real notifications are the
        shiny/shundo messages, and the throw-rate heartbeat would just be noise.
        Runs on the worker thread; battery reads are spaced out so the extra adb call is rare."""
        now = time.monotonic()
        # Catch mode counts throws; shundo mode counts checked encounters.
        done = getattr(stats, "throws", None)
        if done is None:
            done = getattr(stats, "checked", 0)

        # Dry spell: N empty cycles in a row, one message (with screenshot) per spell.
        if not shundo:
            if threw:
                self._empty_streak = 0
                self._alert_fired = False
            else:
                self._empty_streak += 1
                limit = int(self.alert_idle.get())
                if limit > 0 and self._empty_streak >= limit and not self._alert_fired:
                    self._alert_fired = True
                    self._send_discord(self.tr("dc_alert").format(self._empty_streak, done), shot=True)

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
        report_min = 0 if shundo else int(self.alert_report.get())
        if report_min > 0 and now - self._last_report >= report_min * 60:
            self._last_report = now
            up_min = int((now - self._run_started) / 60)
            rate = round(done / max((now - self._run_started) / 3600, 1 / 60))
            part = ""
            if self._batt_last.get("level") is not None:
                part = self.tr("dc_batt_part").format(self._batt_last["level"], self._batt_last.get("temp", "?"))
            self._send_discord(self.tr("dc_report").format(up_min, done, rate, stats.cycles, part))

    # -- live view -------------------------------------------------------------
    def toggle_preview(self) -> None:
        """A small window mirroring the phone with the shundo detections drawn on it:
        where the feed tap goes, the '@' slot state, the feet tap point, spawn rings."""
        if getattr(self, "_pv_win", None):
            self._close_preview()
            return
        try:
            dev = self.device or Device(self._sel_serial() or None)
            if not (self._sel_serial() or self.device):
                raise RuntimeError(self.tr("msg_no_device"))
            self._pv_dev = dev
            # Scale the annotation config to this phone so the drawn boxes line up.
            pv_cfg = ShundoConfig()
            try:
                pv_cfg = pv_cfg.scale_to(*dev.screen_size(), dev.density())
            except Exception:  # noqa: BLE001
                pass
            self._pv_det = ShundoRoutine(dev, pv_cfg)
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("pv_err").format(e))
            return
        win = tk.Toplevel(self.root)
        win.title(self.tr("preview"))
        win.resizable(False, False)
        self._pv_win = win
        self._pv_label = ttk.Label(win)
        self._pv_label.pack(padx=4, pady=4)
        ttk.Label(win, text=self.tr("pv_legend"), wraplength=330, justify="left").pack(padx=8, pady=(0, 8))
        win.protocol("WM_DELETE_WINDOW", self._close_preview)
        self._pv_busy = False
        self._pv_img = None
        self._pv_tick()

    def _close_preview(self) -> None:
        win = getattr(self, "_pv_win", None)
        self._pv_win = None
        if win is not None:
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass

    def _pv_tick(self) -> None:
        if getattr(self, "_pv_win", None) is None:
            return
        if not self._pv_busy:
            self._pv_busy = True
            threading.Thread(target=self._pv_work, daemon=True).start()
        self.root.after(800, self._pv_tick)

    def _pv_work(self) -> None:
        """Grab + annotate + display one frame. Runs off the UI thread; only the final
        image swap is marshalled back. Uses the routine's live stream when running,
        else one-shot captures (slower but fine for a preview)."""
        try:
            dev = self.device if self.device is not None else self._pv_dev
            frame = dev.screenshot()
            ann = self._pv_det.annotate(frame)
            h, w = ann.shape[:2]
            scale = 340 / w
            small = cv2.resize(ann, (340, int(h * scale)))
            ok, png = cv2.imencode(".png", small)
            if ok:
                data = base64.b64encode(png.tobytes())

                def show() -> None:
                    if getattr(self, "_pv_win", None) is not None:
                        img = tk.PhotoImage(data=data)
                        self._pv_img = img          # keep a reference or Tk drops it
                        self._pv_label.config(image=img)

                self.root.after(0, show)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._pv_busy = False

    # -- run control ----------------------------------------------------------
    # -- manual alignment -----------------------------------------------------
    def _cal_defaults(self, w: int, h: int, dens) -> dict:
        """Auto positions (device px) for this screen, used as starting handles."""
        c = CatchConfig().scale_to(w, h, dens)
        s = ShundoConfig().scale_to(w, h, dens)
        return {
            "nearby_slot":         list(c.nearby_slot),
            "ball_fallback":       list(c.ball_fallback),
            "flee_xy":             list(c.flee_xy),
            "ball_region":         list(c.ball_region),
            "pokestop_close_xy":   list(c.pokestop_close_xy),
            "out_of_balls_region": list(c.out_of_balls_region),
            "pill_region":         list(s.pill_region),
            "camera_region":       list(s.camera_region),
            "toast_region":        list(s.toast_region),
        }

    def open_calibrate(self) -> None:
        if getattr(self, "_cal_win", None) is not None:
            try: self._cal_win.lift()
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            dev = self.device or Device(self._sel_serial() or None)
            if not (self._sel_serial() or self.device):
                raise RuntimeError(self.tr("msg_no_device"))
            w, h = dev.screen_size(); dens = dev.density()
            frame = dev.screenshot(fresh=True)
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("pv_err").format(e))
            return

        self._cal_dev_size = (w, h)
        self._cal_def = self._cal_defaults(w, h, dens)
        if self.manual and tuple(self.manual.get("_screen", ())) == (w, h):
            self._cal = {k: list(self.manual.get(k, v)) for k, v in self._cal_def.items()}
        else:
            self._cal = {k: list(v) for k, v in self._cal_def.items()}

        disp_h = min(760, h)
        self._cal_sf = disp_h / h
        disp_w = int(round(w * self._cal_sf))
        small = cv2.resize(frame, (disp_w, disp_h))
        ok, png = cv2.imencode(".png", small)
        self._cal_photo = tk.PhotoImage(data=base64.b64encode(png.tobytes())) if ok else None

        win = tk.Toplevel(self.root); win.title(self.tr("cal_title")); win.resizable(False, False)
        self._cal_win = win
        win.protocol("WM_DELETE_WINDOW", self._cal_close)
        ttk.Label(win, text=self.tr("cal_hint"), wraplength=disp_w + 200,
                  foreground="#555", justify="left").pack(anchor="w", padx=8, pady=(8, 4))
        body = ttk.Frame(win); body.pack(padx=8, pady=4)
        cv = tk.Canvas(body, width=disp_w, height=disp_h, highlightthickness=1,
                       highlightbackground="#888", cursor="crosshair")
        cv.pack(side="left")
        self._cal_canvas = cv
        if self._cal_photo is not None:
            cv.create_image(0, 0, anchor="nw", image=self._cal_photo)
        legend = ttk.Frame(body); legend.pack(side="left", fill="y", padx=(10, 0))
        for field, kind, mode, key, color in CALIB_ITEMS:
            row = ttk.Frame(legend); row.pack(anchor="w", pady=3)
            sw = tk.Canvas(row, width=16, height=16, highlightthickness=0)
            sw.pack(side="left"); sw.create_rectangle(2, 2, 14, 14, fill=color, outline=color)
            ttk.Label(row, text=self.tr(key)).pack(side="left", padx=4)
        self._cal_active = None
        cv.bind("<ButtonPress-1>", self._cal_press)
        cv.bind("<B1-Motion>", self._cal_drag)
        cv.bind("<ButtonRelease-1>", self._cal_release)
        btns = ttk.Frame(win); btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text=self.tr("cal_save"), command=self._cal_save).pack(side="right", padx=3)
        ttk.Button(btns, text=self.tr("cal_reset"), command=self._cal_reset).pack(side="right", padx=3)
        ttk.Button(btns, text=self.tr("cal_cancel"), command=self._cal_close).pack(side="right", padx=3)
        self._cal_redraw()

    def _cal_redraw(self) -> None:
        c = self._cal_canvas; sf = self._cal_sf
        c.delete("ov")
        for field, kind, mode, key, color in CALIB_ITEMS:
            v = self._cal[field]
            if kind == "point":
                x, y = v[0] * sf, v[1] * sf
                c.create_line(x - 16, y, x + 16, y, fill=color, width=3, tags="ov")
                c.create_line(x, y - 16, x, y + 16, fill=color, width=3, tags="ov")
                c.create_oval(x - 13, y - 13, x + 13, y + 13, outline=color, width=3, tags="ov")
                c.create_text(x + 17, y - 11, text=self.tr(key), anchor="w", fill=color,
                              font=("Segoe UI", 8, "bold"), tags="ov")
            else:
                x, y, ww, hh = v[0] * sf, v[1] * sf, v[2] * sf, v[3] * sf
                c.create_rectangle(x, y, x + ww, y + hh, outline=color, width=3, tags="ov")
                for cx, cy in ((x, y), (x + ww, y), (x, y + hh), (x + ww, y + hh)):
                    c.create_rectangle(cx - 6, cy - 6, cx + 6, cy + 6, fill=color,
                                       outline="#ffffff", tags="ov")
                c.create_text(x + 4, y + 2, text=self.tr(key), anchor="nw", fill=color,
                              font=("Segoe UI", 8, "bold"), tags="ov")

    def _cal_press(self, e) -> None:
        sf = self._cal_sf; mx, my = e.x, e.y
        pick = None; pickd = 22
        for field, kind, *_ in CALIB_ITEMS:            # points + resize handles first
            v = self._cal[field]
            if kind == "point":
                x, y = v[0] * sf, v[1] * sf
                d = ((mx - x) ** 2 + (my - y) ** 2) ** 0.5
                if d < pickd:
                    pickd = d; pick = (field, "move", mx - x, my - y)
            else:
                x, y, ww, hh = v[0] * sf, v[1] * sf, v[2] * sf, v[3] * sf
                corners = {"tl": (x, y), "tr": (x + ww, y),
                           "bl": (x, y + hh), "br": (x + ww, y + hh)}
                for cn, (cx, cy) in corners.items():
                    if abs(mx - cx) < 13 and abs(my - cy) < 13:
                        pick = (field, "rs:" + cn, 0, 0); pickd = 0
        if pick is None:                                # else a region body move
            for field, kind, *_ in CALIB_ITEMS:
                if kind != "region":
                    continue
                v = self._cal[field]; x, y, ww, hh = v[0] * sf, v[1] * sf, v[2] * sf, v[3] * sf
                if x <= mx <= x + ww and y <= my <= y + hh:
                    pick = (field, "move", mx - x, my - y); break
        self._cal_active = pick

    def _cal_drag(self, e) -> None:
        if not self._cal_active:
            return
        field, mode, ox, oy = self._cal_active
        sf = self._cal_sf; w, h = self._cal_dev_size
        v = self._cal[field]
        if len(v) == 2:                                 # point
            v[0] = int(min(max((e.x - ox) / sf, 0), w))
            v[1] = int(min(max((e.y - oy) / sf, 0), h))
        elif mode.startswith("rs:"):                    # resize from a corner
            corner = mode[3:]
            x, y, ww, hh = v
            mxp, myp = e.x / sf, e.y / sf
            x1, y1, x2, y2 = x, y, x + ww, y + hh       # keep the opposite corner fixed
            if corner in ("tl", "bl"):
                x1 = mxp
            else:
                x2 = mxp
            if corner in ("tl", "tr"):
                y1 = myp
            else:
                y2 = myp
            xa, xb = sorted((x1, x2)); ya, yb = sorted((y1, y2))
            xa = max(0, xa); ya = max(0, ya); xb = min(w, xb); yb = min(h, yb)
            if xb - xa < 20: xb = xa + 20
            if yb - ya < 20: yb = ya + 20
            v[0], v[1], v[2], v[3] = int(xa), int(ya), int(xb - xa), int(yb - ya)
        else:                                           # region move
            v[0] = int(min(max((e.x - ox) / sf, 0), w - v[2]))
            v[1] = int(min(max((e.y - oy) / sf, 0), h - v[3]))
        self._cal_redraw()

    def _cal_release(self, _e) -> None:
        self._cal_active = None

    def _cal_save(self) -> None:
        data = {k: [int(n) for n in v] for k, v in self._cal.items()}
        data["_screen"] = list(self._cal_dev_size)
        self.manual = data
        self.save_settings()
        self._log(self.tr("cal_saved"))
        self._cal_close()

    def _cal_reset(self) -> None:
        self._cal = {k: list(v) for k, v in self._cal_def.items()}
        self.manual = {}
        self.save_settings()
        self._log(self.tr("cal_cleared"))
        self._cal_redraw()

    def _cal_close(self) -> None:
        win = getattr(self, "_cal_win", None); self._cal_win = None
        if win is not None:
            try: win.destroy()
            except Exception:  # noqa: BLE001
                pass

    def _apply_manual(self, cfg, mode: str):
        """Overwrite tap points / boxes with the manually-aligned device-pixel values."""
        m = self.manual
        if not m or not m.get("_screen"):
            return cfg
        if tuple(m["_screen"]) != tuple(cfg.screen):
            self._log(self.tr("cal_mismatch"))
            return cfg

        def P(name):
            v = m.get(name)
            return tuple(v) if isinstance(v, (list, tuple)) and len(v) == 2 else None

        def R(name):
            v = m.get(name)
            return tuple(v) if isinstance(v, (list, tuple)) and len(v) == 4 else None

        if mode == "catch":
            if P("nearby_slot"):
                cfg.nearby_slot = P("nearby_slot")
                cfg.require_anchor = False
                cfg.force_slot = True
            if P("ball_fallback"):
                cfg.ball_fallback = P("ball_fallback")
            if P("flee_xy"):
                cfg.flee_xy = P("flee_xy")
            if R("ball_region"):
                cfg.ball_region = R("ball_region")
            if P("pokestop_close_xy"):
                cfg.pokestop_close_xy = P("pokestop_close_xy")
            if R("out_of_balls_region"):
                cfg.out_of_balls_region = R("out_of_balls_region")
        else:
            if P("flee_xy"):
                cfg.flee_xy = P("flee_xy")
            if R("pill_region"):
                cfg.pill_region = R("pill_region")
            if R("camera_region"):
                cfg.camera_region = R("camera_region")
            if R("toast_region"):
                cfg.toast_region = R("toast_region")
        return cfg

    def on_play(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        serial = self._sel_serial()
        if not serial:
            self._log(self.tr("msg_no_device"))
            return
        self._remember_device(serial)
        self.save_settings()
        try:
            self.device = Device(serial)
            # Fixed coordinates were tuned on BASE_RESOLUTION; rescale them to this phone's
            # actual screen so detection lines up on other resolutions. If the size can't be
            # read, scale_to is skipped (config stays at base) rather than aborting the run.
            try:
                dev_size = self.device.screen_size()
                dev_dens = self.device.density()
            except Exception:  # noqa: BLE001
                dev_size = dev_dens = None
            if self.mode == "shundo":
                cfg = ShundoConfig(
                    teleport_wait=max(2.0, float(self.tp_wait.get())),
                    encounter_open_wait=max(2.0, float(self.s_enc_wait.get())),
                    shundo_action=self.shundo_action,
                    shiny_action=self.shiny_action,
                )
                if dev_size is not None:
                    cfg = cfg.scale_to(*dev_size, dev_dens)
                cfg = self._apply_manual(cfg, "shundo")
                self.routine = ShundoRoutine(self.device, cfg)
                self.routine._on_waiting = lambda s: self.log_queue.put(self.tr("msg_s_waiting").format(s))
            else:
                cfg = CatchConfig(
                    slot_offset_y=int(self.slot_offset.get()),
                    throw_dy=-abs(int(self.throw_power.get())),
                    encounter_timeout=max(2.0, float(self.wait_enc.get())),
                    catch_timeout=max(2.0, float(self.wait_catch.get())),
                    idle_before_autowalk=int(self.idle_aw.get()),
                    max_catches=int(self.max_catches.get()),
                )
                if dev_size is not None:
                    cfg = cfg.scale_to(*dev_size, dev_dens)
                cfg = self._apply_manual(cfg, "catch")
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
            if stats.last_event == "no_balls":
                self.log_queue.put(self.tr("msg_no_balls"))
                self._send_discord(self.tr("dc_no_balls"), shot=True)
                return
            if stats.last_event == "autowalk":
                self.log_queue.put(self.tr("msg_autowalk").format(stats.autowalks))
                return
            tag = self.tr("msg_throw") if threw else self.tr("msg_empty")
            self.log_queue.put(self.tr("msg_cycle").format(stats.cycles, tag, stats.throws))
            self.log_queue.put(f"__count__{stats.throws}")
            self._tick_alerts(stats, threw)

        def on_shundo_event(stats, outcome):
            self.log_queue.put("__countstr__" + self.tr("s_counts").format(stats.checked, stats.shinies, stats.shundos))
            if outcome == "shundo":
                how = self.tr("dc_shundo_pause" if self.shundo_action == "pause" else "dc_shundo_stop")
                self.log_queue.put(self.tr("msg_s_shundo").format(how))
                self._send_discord(self.tr("dc_shundo").format(how, stats.checked, stats.shinies), shot=True)
                if self.shundo_action == "pause":
                    self.log_queue.put("__paused_shundo__")
            elif outcome == "shiny":
                if self.shiny_action == "skip":
                    # Not a full shundo: the routine flees and keeps hunting. Still alert
                    # Discord with a screenshot so the user knows a shiny went by.
                    self.log_queue.put(self.tr("msg_s_shiny_skip"))
                    self._send_discord(self.tr("dc_shiny_skip").format(stats.checked), shot=True)
                else:
                    how = self.tr("dc_shundo_pause" if self.shundo_action == "pause" else "dc_shundo_stop")
                    self.log_queue.put(self.tr("msg_s_shiny").format(how))
                    self._send_discord(self.tr("dc_shiny").format(how, stats.checked), shot=True)
                    if self.shundo_action == "pause":
                        self.log_queue.put("__paused_shiny__")
            elif outcome == "blocked":
                self.log_queue.put(self.tr("msg_s_blocked").format(stats.checked, stats.shinies, stats.shundos))
            elif outcome == "miss":
                self.log_queue.put(self.tr("msg_s_miss"))
            elif outcome == "nospawn":
                self.log_queue.put(self.tr("msg_s_nospawn"))
            elif outcome == "idle":
                self.log_queue.put(self.tr("msg_s_idle"))
            self._tick_alerts(stats, outcome not in ("idle", "popup"), shundo=True)

        dim = self.dim_screen.get()
        try:
            if dim:
                self.device.enable_dim()
                self.log_queue.put(self.tr("msg_dim"))
            # Realtime H.264 capture. Shundo mode streams at native resolution with a
            # higher bitrate: the IV digits are too small to survive the half-res encode.
            if self.mode == "shundo":
                self.device.start_stream(half=False, bitrate="8M")
            else:
                self.device.start_stream()
            self.routine.run(on_event=on_shundo_event if self.mode == "shundo" else on_event)
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
                elif msg.startswith("__countstr__"):
                    self.count_var.set(msg[len("__countstr__"):])
                elif msg in ("__paused_shundo__", "__paused_shiny__"):
                    # The routine paused itself on a shiny/shundo — sync the buttons/status.
                    self.paused = True
                    self.pause_btn.config(text=self.tr("resume"))
                    self._set_status("st_shundo" if msg == "__paused_shundo__" else "st_shiny")
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
