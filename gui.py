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
from dataclasses import replace
from tkinter import filedialog, ttk

import cv2
import numpy as np

from avc import diag
from avc.catch import CatchConfig, CatchRoutine
from avc.coord_shundo import CoordShundoConfig, CoordShundoRoutine
from avc.coord_source import CoordBridge, CoordQueue
from avc.device import Device
from avc.shundo import ShundoConfig, ShundoRoutine
from avc.spin import SpinRoutine

# Donate destinations shown on the Donate tab.
DONATE_KOFI = "https://ko-fi.com/qpham7286"
DISCORD_INVITE = "https://discord.gg/QXSfKKPpG6"

# Manual-alignment items shown in the calibrate window.
# (config field, kind 'point'|'region', mode 'catch'|'shundo'|'both', i18n key, colour)
CALIB_ITEMS = [
    ("nearby_slot",         "point",  "catch",  "cal_nearby",  "#ff3030"),
    ("ball_fallback",       "point",  "catch",  "cal_ball",    "#00c000"),
    ("berry_start",         "point",  "catch",  "cal_berry_start", "#7c4dff"),
    ("berry_end",           "point",  "catch",  "cal_berry_end",   "#00b894"),
    ("flee_xy",             "point",  "both",   "cal_flee",    "#ffcc00"),
    ("pokestop_close_xy",   "point",  "catch",  "cal_stop",    "#ff33cc"),
    ("out_of_balls_region", "region", "catch",  "cal_noball",  "#ff8800"),
    ("pill_region",         "region", "shundo", "cal_pill",    "#3399ff"),
    ("toast_region",        "region", "shundo", "cal_toast",   "#cc66ff"),
    ("teleport_xy",         "point",  "coord", "cal_teleport", "#00d2d3"),
    ("teleport_input_xy",   "point",  "coord", "cal_coord_input", "#54a0ff"),
    ("teleport_ok_xy",      "point",  "coord", "cal_coord_ok", "#1dd1a1"),
    ("spin_region",         "region", "catch",  "cal_spin",    "#00e5ff"),
]

CALIB_GROUP_FIELDS = {
    "normal": ("nearby_slot", "ball_fallback", "pokestop_close_xy", "out_of_balls_region"),
    "quick": ("nearby_slot", "ball_fallback", "berry_start", "berry_end", "flee_xy",
              "pokestop_close_xy", "out_of_balls_region"),
    "shundo": ("flee_xy", "pill_region", "toast_region"),
    "coord": ("teleport_xy", "teleport_input_xy", "teleport_ok_xy"),
    # Only the scan circle: the spin mode taps what it finds inside it and needs no other
    # fixed point. Flee comes along because a Go Plus catch can drop an encounter on top of
    # the map, and leaving it is the one blind tap this mode makes.
    "spin": ("spin_region", "flee_xy"),
}

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
        "• Khi hết bóng, app tự thoát màn bắt và bật AutoWalk trong 10 phút. Ở chế độ bắt có "
        "key, có thể bật thêm tùy chọn khởi động Go Plus để quay PokéStop.\n"
        "\n"
        "⑥ THÔNG BÁO DISCORD (tab Cài đặt)\n"
        "• Dán \"Webhook URL\" của kênh Discord để nhận cảnh báo: trống spawn lâu, báo cáo "
        "định kỳ, pin yếu, hết bóng, gặp shiny…\n"
        "\n"
        "⑦ MẸO\n"
        "• Cắm sạc khi chạy lâu; app có thể tự làm tối màn hình cho đỡ nóng (game vẫn chạy nền).\n"
        "• Nếu ném lệch: chỉnh \"Lực ném\" trong tab Cài đặt.\n"
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
        "• When balls run out, the app leaves the encounter and starts AutoWalk for 10 minutes. "
        "In keyed catch mode, Go Plus can also be started through its dedicated setting.\n"
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
    "test_control":  {"vi": "Kiểm tra ADB/scrcpy", "en": "Test ADB/scrcpy"},
    "test_running":  {"vi": "Đang kiểm tra ADB, stream và scrcpy…", "en": "Testing ADB, stream, and scrcpy…"},
    "test_stop_first": {"vi": "Hãy dừng bot trước khi kiểm tra kết nối.",
                          "en": "Stop the bot before testing the connection."},
    "test_adb_ok":   {"vi": "✓ ADB hoạt động: {} ({}x{}), chụp màn hình thành công.",
                      "en": "✓ ADB works: {} ({}x{}), screenshot succeeded."},
    "test_stream_ok": {"vi": "✓ Stream realtime hoạt động: nhận frame sau {:.2f}s.",
                       "en": "✓ Realtime stream works: frame received in {:.2f}s."},
    "test_control_ok": {"vi": "✓ Socket điều khiển scrcpy hoạt động (không gửi tap).",
                        "en": "✓ scrcpy control socket works (no tap sent)."},
    "test_fail":     {"vi": "✗ Kiểm tra thất bại tại {}: {}", "en": "✗ Test failed at {}: {}"},
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
    "grp_pace":      {"vi": "Nhịp độ & an toàn tài khoản", "en": "Pacing & account safety"},
    "grp_shared":    {"vi": "Dùng chung cho cả 2 chế độ", "en": "Shared by both modes"},
    "advanced":      {"vi": "Hiện tùy chọn nâng cao (tinh chỉnh mili-giây)",
                      "en": "Show advanced options (millisecond tuning)"},
    "throw_power":   {"vi": "Lực ném (px, càng lớn càng mạnh):", "en": "Throw power (px, higher = stronger):"},
    "catch_style":   {"vi": "Kiểu bắt:", "en": "Catch style:"},
    "catch_normal":  {"vi": "Auto bắt thường", "en": "Normal auto catch"},
    "catch_quick":   {"vi": "Auto bắt nhanh (không cần PGSharp key)", "en": "Quick auto catch (no PGSharp key)"},
    "quick_flick":   {"vi": "Flick Quick Catch (giây):", "en": "Quick Catch flick (s):"},
    "touch_delay":   {"vi": "Chờ bóng sẵn sàng trước ném (giây):", "en": "Ball-ready delay before throw (s):"},
    "post_throw":    {"vi": "Chờ sau ném trước khi thoát (giây):", "en": "Wait after throw before flee (s):"},
    "flee_taps":     {"vi": "Số lần nhấn thoát:", "en": "Flee tap count:"},
    "flee_gap":      {"vi": "Khoảng cách các lần thoát (giây, shundo tối thiểu 0.45):",
                      "en": "Flee tap gap (s, Shundo enforces 0.45 min):"},
    "wait_enc":      {"vi": "Chờ mở màn bắt tối đa (giây):", "en": "Max wait for encounter (s):"},
    "wait_catch":    {"vi": "Chờ bắt xong tối đa (giây):", "en": "Max wait after throw (s):"},
    "idle_aw":       {"vi": "Trống mấy lần thì AutoWalk (0=tắt):", "en": "Empty cycles before AutoWalk (0=off):"},
    "max_catches":   {"vi": "Giới hạn số con (0=∞):", "en": "Catch limit (0=∞):"},
    # These two read almost identically in the old wording ("rest between catches" vs "minimum
    # gap between catches") while meaning opposite things: settle is a ceiling that ends the
    # moment the next Pokémon shows up, min_gap is a floor that is always served in full.
    "settle":        {"vi": "Chờ con kế tiếp, tối đa (giây):",
                      "en": "Wait for next Pokémon, at most (s):"},
    "max_throws":    {"vi": "Số bóng tối đa mỗi con:", "en": "Max throws per Pokémon:"},
    "min_gap":       {"vi": "Bắt chậm lại, cách nhau ít nhất (giây, 0=tắt):",
                      "en": "Slow down: at least this long between catches (s, 0=off):"},
    "pre_tap":       {"vi": "Chờ giữa tap đơn và tap đôi (giây):",
                      "en": "Gap between single tap and double tap (s):"},
    "cooldown":      {"vi": "Nghỉ khi PGSharp báo cooldown (tránh khoá tài khoản)",
                      "en": "Pause while PGSharp reports a cooldown (avoids soft bans)"},
    "ui_dump":       {"vi": "Đọc overlay PGSharp để soi Nearby chính xác hơn",
                      "en": "Read the PGSharp overlay for a surer Nearby check"},
    "catch_feed":    {"vi": "Nearby hết Pokémon: lấy 1 con từ Feed (mặc định tắt)",
                       "en": "When Nearby is empty: take 1 Pokémon from Feed (off by default)"},
    "no_balls_goplus": {"vi": "Hết bóng: khởi động Go Plus sau AutoWalk (chỉ bắt có key)",
                         "en": "Out of balls: start Go Plus after AutoWalk (keyed catch only)"},
    "no_balls_spin": {"vi": "Hết bóng: vừa đi vừa quay PokéStop (không cần key)",
                       "en": "Out of balls: spin PokéStops while walking (no key needed)"},
    "no_balls_min":  {"vi": "Hết bóng: quay stop bao nhiêu phút rồi bắt lại",
                       "en": "Out of balls: minutes of spinning before catching resumes"},
    "grp_spin":      {"vi": "Quay PokéStop", "en": "PokéStop spinning"},
    "spin_note":     {"vi": "Quét đúng màu xanh của PokéStop chưa quay trong vòng tròn quanh nhân vật rồi bấm. "
                            "Stop đã quay chuyển tím nên tự bị bỏ qua. Mỗi lần chạm map PGSharp sẽ hỏi "
                            "\"Stop AutoWalk?\" — bot luôn bấm CANCEL.",
                      "en": "Scans the unspun-PokéStop blue inside the circle around your avatar and taps it. "
                            "A spun stop turns violet, so it drops out by itself. Every map touch makes PGSharp "
                            "ask \"Stop AutoWalk?\" — the bot always answers CANCEL."},
    "spin_radius":   {"vi": "Bán kính vòng quét quanh nhân vật (px)", "en": "Scan circle radius around avatar (px)"},
    "spin_interval": {"vi": "Giãn cách giữa 2 lần bấm stop (giây)", "en": "Gap between stop taps (s)"},
    "spin_min_area": {"vi": "Đốm xanh nhỏ nhất tính là stop (px²)", "en": "Smallest blue blob counted as a stop (px²)"},
    "trace":         {"vi": "Ghi log thời gian từng bước (gỡ lỗi, tạo timing.log)",
                      "en": "Log per-step timings for debugging (writes timing.log)"},
    "dim":           {"vi": "Tắt sáng màn hình khi chạy (giảm nóng)", "en": "Screen off while running (less heat)"},
    "mode":          {"vi": "Chế độ:", "en": "Mode:"},
    "preview":       {"vi": "👁 Xem bot nhìn", "en": "👁 Live view"},
    "calibrate":     {"vi": "🎯 Căn chỉnh tay", "en": "🎯 Manual align"},
    "export":        {"vi": "🧾 Xuất báo cáo lỗi", "en": "🧾 Export bug report"},
    "export_ok":     {"vi": "Đã lưu báo cáo lỗi: {} — gửi file này khi báo lỗi.",
                      "en": "Bug report saved: {} — send this file when reporting."},
    "export_fail":   {"vi": "Không xuất được báo cáo: {}", "en": "Could not export report: {}"},
    "cal_title":     {"vi": "Căn chỉnh tay — kéo các điểm/khung vào đúng chỗ",
                      "en": "Manual alignment — drag points/boxes into place"},
    "cal_group_catch": {"vi": "Bắt Pokémon", "en": "Catching"},
    "cal_group_both":  {"vi": "Dùng chung", "en": "Shared"},
    "cal_group_shundo":{"vi": "Shundo", "en": "Shundo"},
    "cal_group_coord": {"vi": "Discord Coord", "en": "Discord Coord"},
    "cal_group_normal": {"vi": "Bắt thường (có key)", "en": "Normal catch (with key)"},
    "cal_group_quick":  {"vi": "Bắt nhanh (không key)", "en": "Quick catch (no key)"},
    "cal_hint":      {"vi": "Kéo dấu (+) tới đúng nút/pokémon; kéo góc khung để đổi kích thước. "
                            "Lưu xong bot dùng đúng các điểm này (tắt dò '@').",
                      "en": "Drag each (+) onto the right button/pokémon; drag a box corner to resize. "
                            "After saving, the bot uses these exact spots (auto-detect off)."},
    "cal_center_tip": {"vi": "Đưa dấu này ra giữa màn hình (dùng khi nó lệch ra ngoài, không kéo được).",
                       "en": "Drop this marker in the middle of the screen (use when it sits off-screen and can't be dragged)."},
    "cal_center_all": {"vi": "⌖ Đưa tất cả ra giữa màn hình",
                       "en": "⌖ Bring all markers to centre"},
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
    "cal_berry_start": {"vi": "Quick Catch: nút Berry", "en": "Quick Catch: Berry button"},
    "cal_pg_menu": {"vi": "Nút mở menu PGSharp", "en": "Open PGSharp menu"},
    "cal_teleport": {"vi": "Dòng Teleport", "en": "Teleport row"},
    "cal_coord_input": {"vi": "Ô nhập Coordinates", "en": "Coordinates input"},
    "cal_coord_ok": {"vi": "Nút OK Teleport", "en": "Teleport OK button"},
    "cal_berry_end": {"vi": "Quick Catch: kéo Berry tới", "en": "Quick Catch: Berry drag target"},
    "cal_flee":      {"vi": "Nút Flee (thoát)", "en": "Flee button"},
    "cal_camera":    {"vi": "Khung quét camera (chung)", "en": "Camera scan box (shared)"},
    "cal_pill":      {"vi": "Khung IV pill (Shundo)", "en": "IV pill box (Shundo)"},
    "cal_stop":      {"vi": "Nút đóng Pokéstop (X)", "en": "Pokéstop close (X)"},
    "cal_noball":    {"vi": "Khung 'hết bóng' (x0)", "en": "Out-of-balls box (x0)"},
    "cal_toast":     {"vi": "Khung toast (Shundo)", "en": "Toast box (Shundo)"},
    "cal_spin":      {"vi": "Vòng quét PokéStop (kéo ôm quanh nhân vật)",
                      "en": "PokéStop scan circle (drag it around your avatar)"},
    "cal_group_spin": {"vi": "Quay stop", "en": "Spin stops"},
    "pv_legend":     {"vi": "Bắt: vàng = ô Nearby sẽ bấm • xanh lá = điểm ném + hướng ném • cam = thanh feed "
                            "(chỉ khi Nearby trống) • đỏ = khung nhận encounter • hồng = nút thoát.   "
                            "Shundo: xanh lá = ô feed • vàng nhạt = thanh @ • cam = vùng đọc IV • trắng = vùng toast.",
                      "en": "Catch: yellow = Nearby slot it will tap • green = throw point + direction • orange = "
                            "feed bar (only when Nearby is empty) • red = encounter box • pink = flee button.   "
                            "Shundo: green = feed slot • pale yellow = @ bar • orange = IV area • white = toast area."},
    "pv_err":        {"vi": "Không mở được xem trực tiếp: {}", "en": "Could not open live view: {}"},
    "pv_overlay":    {"vi": "Vẽ vùng bot nhìn", "en": "Draw what the bot sees"},
    "pv_control":    {"vi": "Điều khiển bằng chuột", "en": "Control with mouse"},
    "pv_back":       {"vi": "◀ Back", "en": "◀ Back"},
    "pv_home":       {"vi": "⌂ Home", "en": "⌂ Home"},
    "pv_zoom":       {"vi": "⤢", "en": "⤢"},
    "pv_on":         {"vi": "bật", "en": "on"},
    "pv_off":        {"vi": "tắt", "en": "off"},
    "pv_status":     {"vi": "{:.1f} fps • màn hình {}x{} • điều khiển: {}",
                      "en": "{:.1f} fps • screen {}x{} • control: {}"},
    "pv_hint":       {"vi": "Kéo chuột trên ảnh để vuốt/điều khiển máy như scrcpy. "
                            "Tắt 'Điều khiển bằng chuột' nếu chỉ muốn xem.",
                      "en": "Drag on the image to swipe/control the phone like scrcpy. "
                            "Untick 'Control with mouse' to just watch."},
    "mode_catch":    {"vi": "Auto bắt Pokémon", "en": "Auto catch"},
    "mode_shundo":   {"vi": "Chấm shundo (shiny 100 IV)", "en": "Shundo check (shiny 100 IV)"},
    "mode_coord_shundo": {"vi": "Shundo từ Discord Coord", "en": "Shundo from Discord coords"},
    "mode_spin":     {"vi": "Quay PokéStop khi đi đường", "en": "Spin PokéStops while walking"},
    "grp_shundo":    {"vi": "Chấm shundo", "en": "Shundo check"},
    "shundo_note":   {"vi": "Cần bật chặn không-shiny trong PGSharp (encounter chỉ mở khi shiny).",
                      "en": "Requires PGSharp's non-shiny block (encounters only open for shinies)."},
    "tp_wait":       {"vi": "Chờ Pokémon xuất hiện trên Nearby (giây, 0 = mãi):",
                      "en": "Wait for Pokémon on Nearby (s, 0 = forever):"},
    "s_enc_wait":    {"vi": "Chờ máy ảnh hiện tối đa (giây):", "en": "Wait for camera icon (s):"},
    "alert_shiny":   {"vi": "Báo Discord khi gặp shiny chưa đủ 100 IV", "en": "Discord alert on shiny below 100 IV"},
    "shundo_action": {"vi": "Khi thấy shundo:", "en": "On shundo:"},
    "shiny_action":  {"vi": "Khi shiny (chưa 100 IV):", "en": "On shiny (below 100 IV):"},
    "act_pause":     {"vi": "Tạm dừng chờ tôi bắt", "en": "Pause and wait for me"},
    "act_stop":      {"vi": "Dừng hẳn bot", "en": "Stop the bot"},
    "act_skip":      {"vi": "Thoát, soi con khác", "en": "Flee and keep hunting"},
    "msg_s_shiny_skip": {"vi": "✨ Phát hiện shiny (chưa đủ 100 IV) — đang bấm Flee.",
                         "en": "✨ Shiny detected (below 100 IV) — attempting Flee."},
    "msg_s_fled":      {"vi": "✓ Đã bấm Flee và xác nhận trở về map — tiếp tục soi.",
                         "en": "✓ Flee succeeded and the map is back — continuing."},
    "msg_s_flee_failed": {"vi": "⛔ Flee chưa đưa về map; đã dừng để không bấm nhầm Pokémon kế tiếp.",
                           "en": "⛔ Flee did not return to the map; stopped before tapping the next Pokémon."},
    "dc_shiny_skip": {"vi": "✨ SHINY (chưa đủ 100 IV) — đã bỏ qua, soi tiếp. (đã soi {} con)",
                      "en": "✨ SHINY (below 100 IV) — skipped, still hunting. ({} checked)"},
    "s_counts":      {"vi": "Soi: {} | shiny: {} | shundo: {}", "en": "Checked: {} | shiny: {} | shundo: {}"},
    "msg_s_blocked": {"vi": "soi {}: không shiny (bị chặn) | shiny {} | shundo {}",
                      "en": "check {}: not shiny (blocked) | shiny {} | shundo {}"},
    "msg_s_shiny":   {"vi": "✨ SHINY! Bot {} — vào máy xử lý!", "en": "✨ SHINY! Bot {} — go handle it!"},
    "st_shiny":      {"vi": "✨ SHINY — chờ bạn xử lý!", "en": "✨ SHINY — waiting for you!"},
    "msg_s_shundo":  {"vi": "🌟💯 SHUNDO!!! Bot {} — vào máy bắt ngay!", "en": "🌟💯 SHUNDO!!! Bot {} — go catch it now!"},
    "msg_s_idle":    {"vi": "(không thấy thanh feed / thanh @ — kiểm tra PGSharp)", "en": "(feed / @ bar not found — check PGSharp)"},
    "msg_coord_idle": {"vi": "(đang chờ coord từ extension — hàng đợi hiện trống)",
                         "en": "(waiting for a coordinate from the extension — queue is empty)"},
    "msg_coord_using": {"vi": "→ Đang chấm {}{} | còn {} coord", "en": "→ Checking {}{} | {} coords left"},
    "msg_coord_bridge": {"vi": "✓ Bộ nhận Discord Coord đang chạy tại 127.0.0.1:{}.",
                           "en": "✓ Discord Coord receiver is listening on 127.0.0.1:{}."},
    "msg_coord_bridge_fail": {"vi": "✗ Không mở được bộ nhận Discord Coord: {}",
                                "en": "✗ Could not start the Discord Coord receiver: {}"},
    "msg_s_miss":    {"vi": "(chưa xác nhận được trạng thái — giữ nguyên Pokémon để kiểm tra lại)",
                       "en": "(state not confirmed — keeping the same Pokémon for another check)"},
    # Not an answer about the Pokémon — the bot simply cannot see it to tap. Says so, instead
    # of the line above, which reads as if an IV/shiny check were in progress.
    "msg_s_recheck": {"vi": "(ảnh nét chưa thấy Pokémon trên thanh @ — nhìn lại, chưa bấm)",
                      "en": "(the crisp capture cannot see the Pokémon on the @ bar — looking again, no tap yet)"},
    "msg_s_lost":    {"vi": "(thanh @ không còn con này — bỏ qua, đi tiếp mục feed kế)",
                      "en": "(the @ bar no longer shows this one — giving it up, moving to the next feed entry)"},
    "msg_s_nospawn": {"vi": "(pokemon chưa hiện lên thanh @ sau khi dịch chuyển — thử lại)",
                      "en": "(pokémon never showed in the @ bar after teleport — retrying)"},
    "msg_s_waiting": {"vi": "… đang chờ pokemon load ({}s)", "en": "… waiting for pokémon to load ({}s)"},
    "msg_s_goplus":  {"vi": "⛔ Dừng Shundo: Go Plus đang kết nối nên PGSharp chặn mọi lần dịch chuyển "
                            "(đã bấm CANCEL để tránh softban). Hãy ngắt Go Plus rồi chạy lại.",
                      "en": "⛔ Shundo stopped: Go Plus is connected so PGSharp blocks every teleport "
                            "(answered CANCEL to avoid a softban). Disconnect Go Plus and run again."},
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
    "alert_report":  {"vi": "Báo cáo định kỳ (giây, 0=tắt):", "en": "Status report every (s, 0=off):"},
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
    "msg_spin":      {"vi": "→ Đã bấm PokéStop (lần {})", "en": "→ Tapped a PokéStop (#{})"},
    "msg_spin_idle": {"vi": "chu kỳ {}: chưa có PokéStop xanh nào trong vùng quét",
                      "en": "cycle {}: no unspun PokéStop inside the scan circle"},
    "spun":          {"vi": "Đã bấm stop: {}", "en": "Stops tapped: {}"},
    "msg_no_balls":  {"vi": "→ Hết Poké Ball! Thoát màn bắt, tạm ngừng 10 phút (vẫn tự di chuyển).", "en": "→ Out of Poké Balls! Left the encounter, holding off 10 min (still auto-walking)."},
    "msg_no_balls_goplus": {"vi": "→ Hết Poké Ball! Đang bật AutoWalk rồi khởi động Go Plus trong 10 phút.",
                             "en": "→ Out of Poké Balls! Starting AutoWalk then Go Plus for the 10-minute refill."},
    "msg_goplus_started": {"vi": "→ Đã bật AutoWalk và bấm khởi động Go Plus.",
                            "en": "→ AutoWalk is active and Go Plus was started."},
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
    "dc_no_balls_goplus": {"vi": "🎱 AutoClick: Hết Poké Ball! Đã thoát màn bắt; đang bật AutoWalk rồi khởi động Go Plus để quay PokéStop trong 10 phút.",
                            "en": "🎱 AutoClick: Out of Poké Balls! Left the catch screen; starting AutoWalk then Go Plus to spin PokéStops for 10 min."},
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
        self.coord_queue = CoordQueue()
        self.coord_bridge = CoordBridge(self.coord_queue)
        self._coord_bridge_error = ""
        self._coord_idle_logged = False
        self.device: Device | None = None
        self.worker: threading.Thread | None = None
        self.paused = False
        self._i18n: list[tuple] = []       # (widget, key) pairs retranslated on language switch
        # Settings rows keyed by i18n key -> (widgets, advanced?), so a row can be hidden when
        # it does nothing in the current mode. See _sync_settings_visibility.
        self._rows: dict[str, tuple] = {}
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
        self._sync_settings_visibility()
        self._retranslate()
        try:
            port = self.coord_bridge.start()
            self._log(self.tr("msg_coord_bridge").format(port))
        except OSError as error:
            self._coord_bridge_error = str(error)
            self._log(self.tr("msg_coord_bridge_fail").format(error))
        self.refresh_devices()
        self.root.after(100, self._drain_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Destroy>", self._on_root_destroy, add="+")

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
        test_row = ttk.Frame(self.tab_main)
        test_row.pack(fill="x", padx=8, pady=(0, 2))
        self.test_control_btn = ttk.Button(
            test_row, text=self.tr("test_control"), command=self._test_device_control,
        )
        self.test_control_btn.pack(side="right")
        self._i18n.append((self.test_control_btn, "test_control"))

        mode_row = ttk.Frame(self.tab_main)
        mode_row.pack(fill="x", **pad)
        self._label(mode_row, "mode").pack(side="left")
        self.mode = "catch"            # "catch" | "shundo" | "coord_shundo" | "spin"
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

        report_row = ttk.Frame(self.tab_main)
        report_row.pack(fill="x", padx=8, pady=(0, 6))
        self.export_btn = ttk.Button(report_row, text=self.tr("export"), command=self.export_report)
        self.export_btn.pack(side="right")
        self._i18n.append((self.export_btn, "export"))

        # ---- Settings tab ----
        settings_wrap = ttk.Frame(self.tab_settings)
        settings_wrap.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        settings_canvas = tk.Canvas(settings_wrap, highlightthickness=0)
        settings_scroll = ttk.Scrollbar(settings_wrap, orient="vertical", command=settings_canvas.yview)
        settings_canvas.configure(yscrollcommand=settings_scroll.set)
        settings_scroll.pack(side="right", fill="y")
        settings_canvas.pack(side="left", fill="both", expand=True)
        settings_body = ttk.Frame(settings_canvas)
        settings_window = settings_canvas.create_window((0, 0), window=settings_body, anchor="nw")
        settings_body.bind("<Configure>", lambda _e: settings_canvas.configure(
            scrollregion=settings_canvas.bbox("all")))
        settings_canvas.bind("<Configure>", lambda e: settings_canvas.itemconfigure(
            settings_window, width=e.width))
        settings_canvas.bind("<MouseWheel>", lambda e: settings_canvas.yview_scroll(
            int(-e.delta / 120), "units"))

        self.show_advanced = tk.BooleanVar(value=False)
        adv_chk = ttk.Checkbutton(settings_body, text=self.tr("advanced"),
                                  variable=self.show_advanced,
                                  command=self._on_advanced_toggle)
        adv_chk.pack(anchor="w", padx=14, pady=(2, 0))
        self._i18n.append((adv_chk, "advanced"))

        catch_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_catch"))
        self._grp_catch = catch_grp
        catch_grp.pack(fill="x", **pad)
        self._i18n.append((catch_grp, "grp_catch"))
        self.throw_power = self._spin(catch_grp, "throw_power", 1, 100, 1400, 700)
        self._label(catch_grp, "catch_style", row=0, column=0, sticky="w", padx=6, pady=2)
        self.catch_style = "normal"
        self.catch_style_var = tk.StringVar()
        self.catch_style_combo = ttk.Combobox(catch_grp, textvariable=self.catch_style_var,
                                               state="readonly", width=30)
        self.catch_style_combo.grid(row=0, column=1, sticky="e", padx=6, pady=2)
        self.catch_style_combo.bind("<<ComboboxSelected>>", self._on_catch_style_change)
        # Not "advanced": this is the main knob of Quick Catch, so hiding it behind a toggle in
        # the very mode it belongs to would be the same mistake as showing it in the mode it
        # does nothing in.
        self.quick_flick = self._spin(catch_grp, "quick_flick", 8, 0.05, 0.5, 0.1,
                                      is_float=True, increment=0.05)
        self.wait_enc = self._spin(catch_grp, "wait_enc", 4, 2, 15, 3.0, is_float=True)
        self.wait_catch = self._spin(catch_grp, "wait_catch", 6, 2, 20, 6.0, is_float=True)
        self.idle_aw = self._spin(catch_grp, "idle_aw", 3, 0, 20, 3)
        self.max_catches = self._spin(catch_grp, "max_catches", 2, 0, 9999, 0)
        self.settle = self._spin(catch_grp, "settle", 7, 0, 15, 1.2, is_float=True,
                                 advanced=True)
        self.touch_delay = self._spin(catch_grp, "touch_delay", 5, 0, 1, 0.2,
                                      is_float=True, increment=0.05, advanced=True)
        # Floor starts at the one the routine enforces: `commit_wait = max(1.0, …)` in
        # avc/catch.py means anything under a second is silently rounded up to one, so the old
        # 0-to-3 range let the box show a number the bot never used.
        self.post_throw = self._spin(catch_grp, "post_throw", 9, 1.0, 3, 1.0,
                                     is_float=True, increment=0.05, advanced=True)
        self.max_throws = self._spin(catch_grp, "max_throws", 12, 1, 10, 3)
        # Opt-in only. One Feed item remains locked until it loads into Nearby and its encounter
        # is handled, so this cannot advance through the Feed while the map is still loading.
        self.catch_use_feed = tk.BooleanVar(value=False)
        feed_chk = ttk.Checkbutton(
            catch_grp,
            text=self.tr("catch_feed"),
            variable=self.catch_use_feed,
        )
        feed_chk.grid(row=14, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((feed_chk, "catch_feed"))
        self.no_balls_goplus = tk.BooleanVar(value=True)
        goplus_chk = ttk.Checkbutton(
            catch_grp,
            text=self.tr("no_balls_goplus"),
            variable=self.no_balls_goplus,
        )
        goplus_chk.grid(row=15, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((goplus_chk, "no_balls_goplus"))
        self._register_row("no_balls_goplus", goplus_chk)
        # The bag refills from PokéStops, so spinning them is the one thing that actually
        # shortens an empty-bag hold — and unlike Go Plus it needs no PGSharp key, which is why
        # this box stays visible in Quick Catch where the Go Plus one is hidden.
        self.no_balls_spin = tk.BooleanVar(value=False)
        spin_chk = ttk.Checkbutton(
            catch_grp,
            text=self.tr("no_balls_spin"),
            variable=self.no_balls_spin,
            command=self._sync_settings_visibility,
        )
        spin_chk.grid(row=16, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((spin_chk, "no_balls_spin"))
        self._register_row("no_balls_spin", spin_chk)
        # How long the hold lasts. It was a fixed ten minutes in avc/catch.py; the spinning walk
        # makes the right length a judgement call (how dense the stops are), so it is a setting.
        self.no_balls_min = self._spin(catch_grp, "no_balls_min", 17, 1, 120, 10, is_float=True,
                                       increment=1)

        # Settings both modes read. They used to sit in the Catching group, which made the flee
        # taps look like a catching option even though normal catching taps flee exactly once
        # and Shundo is their main consumer.
        shared_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_shared"))
        self._grp_shared = shared_grp
        shared_grp.pack(fill="x", **pad)
        self._i18n.append((shared_grp, "grp_shared"))
        self.flee_taps = self._spin(shared_grp, "flee_taps", 0, 1, 6, 2)
        # 0.25 is the floor avc/catch.py applies; Shundo raises it to 0.45, which the label says
        # rather than pretending one number means one thing.
        self.flee_gap = self._spin(shared_grp, "flee_gap", 1, 0.25, 1, 0.25,
                                   is_float=True, increment=0.05, advanced=True)
        self.dim_screen = tk.BooleanVar(value=False)
        dim_chk = ttk.Checkbutton(shared_grp, text=self.tr("dim"), variable=self.dim_screen)
        dim_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((dim_chk, "dim"))

        # Pacing and safety. Kept apart from the catching group because these do not make a catch
        # better or worse — they decide how hard the bot is allowed to push the account.
        pace_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_pace"))
        self._grp_pace = pace_grp
        pace_grp.pack(fill="x", **pad)
        self._i18n.append((pace_grp, "grp_pace"))
        self.min_gap = self._spin(pace_grp, "min_gap", 0, 0, 30, 3.0,
                                  is_float=True, increment=0.5)
        self.pre_tap = self._spin(pace_grp, "pre_tap", 1, 0, 5, 0.8,
                                  is_float=True, increment=0.1, advanced=True)
        self.respect_cd = tk.BooleanVar(value=True)
        cd_chk = ttk.Checkbutton(pace_grp, text=self.tr("cooldown"), variable=self.respect_cd)
        cd_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((cd_chk, "cooldown"))
        self.use_ui_dump = tk.BooleanVar(value=True)
        # The cooldown is read out of the PGSharp overlay, so without the dump there is nothing
        # to read it from. The routine already refuses that combination; grey the box out so the
        # setting cannot look enabled while doing nothing.
        self._sync_cd_state = lambda: cd_chk.config(
            state="normal" if self.use_ui_dump.get() else "disabled")
        ud_chk = ttk.Checkbutton(pace_grp, text=self.tr("ui_dump"), variable=self.use_ui_dump,
                                 command=lambda: self._sync_cd_state())
        ud_chk.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((ud_chk, "ui_dump"))
        self.trace_timing = tk.BooleanVar(value=False)
        tr_chk = ttk.Checkbutton(pace_grp, text=self.tr("trace"), variable=self.trace_timing)
        tr_chk.grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        self._i18n.append((tr_chk, "trace"))
        self._register_row("trace", tr_chk, advanced=True)

        # Spinning knobs live in their own group because two different things read them: the
        # "Quay PokéStop" mode, and the out-of-balls hold of either catch style. Putting them in
        # the Catching group would have tied them to a mode they outlive.
        spin_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_spin"))
        self._grp_spin = spin_grp
        spin_grp.pack(fill="x", **pad)
        self._i18n.append((spin_grp, "grp_spin"))
        spin_note = ttk.Label(spin_grp, text=self.tr("spin_note"), wraplength=400,
                              foreground="#666")
        spin_note.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 4))
        self._i18n.append((spin_note, "spin_note"))
        # 450 is half the box the player drew around their own avatar once the handle became
        # draggable. It sits between the ~220 px ring the game paints (too tight once the pole a
        # cube stands on is counted) and the 900 px first guess (which tapped stops streets away,
        # opened their info screen, and closed it again).
        self.spin_radius = self._spin(spin_grp, "spin_radius", 1, 150, 1200, 450, increment=20)
        self.spin_gap = self._spin(spin_grp, "spin_interval", 2, 0.5, 15, 2.0,
                                   is_float=True, increment=0.5)
        self.spin_min_area = self._spin(spin_grp, "spin_min_area", 3, 200, 12000, 700,
                                        increment=100, advanced=True)

        sh_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_shundo"))
        self._grp_shundo = sh_grp
        sh_grp.pack(fill="x", **pad)
        self._i18n.append((sh_grp, "grp_shundo"))
        note = ttk.Label(sh_grp, text=self.tr("shundo_note"), wraplength=400, foreground="#666")
        note.grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=(2, 4))
        self._i18n.append((note, "shundo_note"))
        self.tp_wait = self._spin(sh_grp, "tp_wait", 1, 0, 3600, 0.0, is_float=True)
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

        dc_grp = ttk.LabelFrame(settings_body, text=self.tr("grp_discord"))
        self._grp_discord = dc_grp
        dc_grp.pack(fill="x", **pad)
        self._i18n.append((dc_grp, "grp_discord"))
        self._label(dc_grp, "webhook", row=0, column=0, sticky="w", padx=6, pady=2)
        self.webhook_url = tk.StringVar()
        ttk.Entry(dc_grp, textvariable=self.webhook_url, width=34).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        self.alert_idle = self._spin(dc_grp, "alert_idle", 1, 0, 200, 10)
        self.alert_report = self._spin(dc_grp, "alert_report", 2, 0, 43200, 1800)
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

    def _spin(self, parent, key, row, lo, hi, default, is_float=False, increment=None,
              advanced=False):
        lbl = self._label(parent, key, row=row, column=0, sticky="w", padx=6, pady=2)
        var = tk.DoubleVar(value=default) if is_float else tk.IntVar(value=default)
        inc = increment if increment is not None else (0.5 if is_float else 1)
        spin = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10, increment=inc)
        spin.grid(row=row, column=1, sticky="e", padx=6, pady=2)
        parent.columnconfigure(1, weight=1)
        self._rows[key] = ((lbl, spin), advanced)
        return var

    def _register_row(self, key: str, *widgets, advanced: bool = False) -> None:
        """Track a non-spinbox control so it can be hidden with the rest of its group."""
        self._rows[key] = (widgets, advanced)

    def _set_row_visible(self, key: str, visible: bool) -> None:
        entry = self._rows.get(key)
        if entry is None:
            return
        widgets, advanced = entry
        if visible and advanced and not self.show_advanced.get():
            visible = False
        for widget in widgets:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def _sync_settings_visibility(self) -> None:
        """Show only the settings that do something in the current mode and catch style.

        Every control here was always visible, which put eight dead ones in front of a user
        catching normally: the four Shundo rows, plus the Quick Catch flick, the post-throw wait
        and the two flee-tap rows — all four of those are read only inside `_quick_throw`
        (avc/catch.py) or by the Shundo routine, so in normal catching they change nothing.
        A control that does nothing is worse than a missing one: it invites tuning that has no
        effect, and the effect is then looked for in the wrong place.
        """
        catching = self.mode == "catch"
        quick = self.catch_style == "quick"
        spinning = self.mode == "spin"
        # The spin knobs are read by the spin mode *and* by a catching run that was told to
        # spin when the bag empties, so they follow the option rather than the mode.
        spin_used = spinning or (catching and bool(self.no_balls_spin.get()))
        for frame, visible in (
            (self._grp_catch, catching),
            (self._grp_pace, catching),
            (self._grp_shared, True),
            (self._grp_spin, spin_used),
            (self._grp_shundo, self.mode in ("shundo", "coord_shundo")),
            (self._grp_discord, True),
        ):
            frame.pack_forget()
            if visible:
                frame.pack(fill="x", padx=8, pady=4)
        # Quick Catch owns the flick and the post-throw wait outright.
        for key in ("quick_flick", "post_throw"):
            self._set_row_visible(key, catching and quick)
        # Go Plus automation belongs to PGSharp's keyed catcher. Quick Catch explicitly exists
        # for users without that key, so presenting this checkbox there would promise a feature
        # their mode cannot use.
        self._set_row_visible("no_balls_goplus", catching and not quick)
        # Spinning to refill needs no key, so it stays on offer in both catch styles. Its
        # length only means anything once the box is ticked.
        self._set_row_visible("no_balls_spin", catching)
        self._set_row_visible("no_balls_min", catching and bool(self.no_balls_spin.get()))
        # The flee taps are spent by Quick Catch, by Shundo and by the spin mode leaving an
        # encounter Go Plus opened; normal catching taps flee once.
        for key in ("flee_taps", "flee_gap"):
            self._set_row_visible(key, (catching and quick) or not catching)
        for key in ("throw_power", "max_catches", "idle_aw", "wait_enc", "wait_catch",
                    "settle", "touch_delay", "max_throws", "min_gap", "pre_tap", "trace"):
            self._set_row_visible(key, catching)

    def _on_advanced_toggle(self) -> None:
        self._sync_settings_visibility()
        self.save_settings()

    # -- mode / shundo action selectors ----------------------------------------
    MODES = (("catch", "mode_catch"), ("shundo", "mode_shundo"),
             ("coord_shundo", "mode_coord_shundo"), ("spin", "mode_spin"))
    CATCH_STYLES = (("normal", "catch_normal"), ("quick", "catch_quick"))
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
        self._sync_settings_visibility()
        self.save_settings()

    def _on_catch_style_change(self, _event=None) -> None:
        self.catch_style = self._code_from_choice(
            self.catch_style_var, self.CATCH_STYLES, self.catch_style)
        self._sync_settings_visibility()
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
        self._refresh_choice(self.catch_style_combo, self.catch_style_var,
                             self.CATCH_STYLES, self.catch_style)
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
        seconds_format = data.get("timing_unit") == "seconds"

        def timing(name: str, legacy_default: float, seconds_default: float) -> float:
            value = float(data.get(name, seconds_default if seconds_format else legacy_default))
            return value if seconds_format else value / 1000.0

        self.throw_power.set(data.get("throw_power", int(self.throw_power.get())))
        self.quick_flick.set(timing("quick_flick", 100.0, 0.1))
        # Encounters take ~2-3s to open; a stored wait below that makes the routine give up
        # mid-load and re-tap from scratch every cycle, so clamp old too-low values.
        self.wait_enc.set(max(2.0, float(data.get("wait_enc", self.wait_enc.get()))))
        self.wait_catch.set(max(2.0, float(data.get("wait_catch", self.wait_catch.get()))))
        self.idle_aw.set(data.get("idle_aw", int(self.idle_aw.get())))
        self.max_catches.set(data.get("max_catches", int(self.max_catches.get())))
        self.settle.set(max(0.0, float(data.get("settle", self.settle.get()))))
        self.touch_delay.set(timing("touch_delay", 200.0, 0.2))
        # Clamp both to the floor the routine actually enforces, so a settings file written
        # before those floors existed stops displaying a number the bot never used. Purely a
        # display correction: these values were already being raised at the point of use.
        self.post_throw.set(max(1.0, timing("post_throw", 350.0, 0.35)))
        self.flee_taps.set(data.get("flee_taps", int(self.flee_taps.get())))
        self.flee_gap.set(max(0.25, timing("flee_gap", 250.0, 0.25)))
        self.max_throws.set(max(1, int(data.get("max_throws", int(self.max_throws.get())))))
        self.dim_screen.set(data.get("dim_screen", False))
        self.catch_use_feed.set(data.get("catch_use_feed", False))
        self.no_balls_goplus.set(data.get("no_balls_goplus", True))
        self.no_balls_spin.set(data.get("no_balls_spin", False))
        self.no_balls_min.set(max(1.0, float(data.get("no_balls_min", self.no_balls_min.get()))))
        self.spin_radius.set(max(300, int(data.get("spin_radius", int(self.spin_radius.get())))))
        self.spin_gap.set(max(0.5, float(data.get("spin_interval", self.spin_gap.get()))))
        self.spin_min_area.set(max(800, int(data.get("spin_min_area",
                                                     int(self.spin_min_area.get())))))
        self.min_gap.set(max(0.0, float(data.get("min_gap", self.min_gap.get()))))
        self.pre_tap.set(max(0.0, float(data.get("pre_tap", self.pre_tap.get()))))
        self.respect_cd.set(data.get("respect_cooldown", True))
        self.use_ui_dump.set(data.get("use_ui_dump", True))
        self._sync_cd_state()
        # Deliberately not persisted as on: tracing is a debugging aid, and a settings file that
        # silently keeps it enabled grows a timing.log for the rest of the user's life.
        self.trace_timing.set(data.get("trace_timing", False))
        self.show_advanced.set(bool(data.get("show_advanced", False)))
        if data.get("mode") in ("catch", "shundo", "coord_shundo", "spin"):
            self.mode = data["mode"]
        if data.get("catch_style") in ("normal", "quick"):
            self.catch_style = data["catch_style"]
        self.tp_wait.set(max(0.0, float(data.get("tp_wait", self.tp_wait.get()))))
        self.s_enc_wait.set(max(2.0, float(data.get("s_enc_wait", self.s_enc_wait.get()))))
        if data.get("shundo_action") in ("pause", "stop"):
            self.shundo_action = data["shundo_action"]
        if data.get("shiny_action") in ("skip", "pause"):
            self.shiny_action = data["shiny_action"]
        self.alert_shiny.set(data.get("alert_shiny", True))
        self.webhook_url.set(data.get("webhook", ""))
        self.alert_idle.set(data.get("alert_idle", int(self.alert_idle.get())))
        report_value = float(data.get("alert_report", 30 if not seconds_format else 1800))
        self.alert_report.set(int(report_value if seconds_format else report_value * 60))
        self.alert_batt.set(data.get("alert_batt", int(self.alert_batt.get())))
        if data.get("device"):
            self.device_var.set(data["device"])

    def save_settings(self) -> None:
        data = {
            "timing_unit": "seconds",
            "throw_power": int(self.throw_power.get()),
            "quick_flick": float(self.quick_flick.get()),
            "wait_enc": float(self.wait_enc.get()),
            "wait_catch": float(self.wait_catch.get()),
            "idle_aw": int(self.idle_aw.get()),
            "max_catches": int(self.max_catches.get()),
            "settle": float(self.settle.get()),
            "touch_delay": float(self.touch_delay.get()),
            "post_throw": float(self.post_throw.get()),
            "show_advanced": bool(self.show_advanced.get()),
            "flee_taps": int(self.flee_taps.get()),
            "flee_gap": float(self.flee_gap.get()),
            "max_throws": int(self.max_throws.get()),
            "dim_screen": bool(self.dim_screen.get()),
            "catch_use_feed": bool(self.catch_use_feed.get()),
            "no_balls_goplus": bool(self.no_balls_goplus.get()),
            "no_balls_spin": bool(self.no_balls_spin.get()),
            "no_balls_min": float(self.no_balls_min.get()),
            "spin_radius": int(self.spin_radius.get()),
            "spin_interval": float(self.spin_gap.get()),
            "spin_min_area": int(self.spin_min_area.get()),
            "min_gap": float(self.min_gap.get()),
            "pre_tap": float(self.pre_tap.get()),
            "respect_cooldown": bool(self.respect_cd.get()),
            "use_ui_dump": bool(self.use_ui_dump.get()),
            "trace_timing": bool(self.trace_timing.get()),
            "mode": self.mode,
            "catch_style": self.catch_style,
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
            try:
                self.device.close_control()
            except Exception:  # noqa: BLE001
                pass
            # Frozen one-file build: the adb daemon's image lives in PyInstaller's _MEI temp dir;
            # kill it so that dir can be removed on exit (otherwise Windows shows a
            # 'Failed to remove temporary directory' warning).
            try:
                self.device.kill_server()
            except Exception:  # noqa: BLE001
                pass
        self.coord_bridge.stop()
        self.save_settings()
        self.root.destroy()

    def _on_root_destroy(self, event) -> None:
        if event.widget is self.root:
            self.coord_bridge.stop()

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
        if cur in attached:
            self.device_var.set(cur)
        elif attached:
            # Prefer a device that is online now over a stale remembered Wi-Fi phone.
            # This is especially important when MuMu is first discovered on localhost.
            self.device_var.set(attached[0])
        elif cur and cur in self.known:
            self.device_var.set(cur + self.OFFLINE_TAG)
        elif options:
            self.device_var.set(options[0])
        else:
            self.device_var.set("")
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

    def _test_device_control(self) -> None:
        """Verify capture, realtime frames, and scrcpy control without touching the screen."""
        if self.worker and self.worker.is_alive():
            self._log(self.tr("test_stop_first"))
            return
        serial = self._sel_serial()
        if not serial:
            self._log(self.tr("msg_no_device"))
            return

        self.test_control_btn.config(state="disabled")
        self._log(self.tr("test_running"))

        def run_test() -> None:
            dev = Device(serial)
            stage = "ADB"
            try:
                state = str(dev._run(["get-state"], timeout=5.0)).strip()
                if state != "device":
                    raise RuntimeError(f"get-state={state or 'empty'}")
                frame = dev.screenshot(fresh=True)
                height, width = frame.shape[:2]
                self.log_queue.put(self.tr("test_adb_ok").format(serial, width, height))

                stage = "stream realtime"
                started_at = time.monotonic()
                dev.start_stream(half=True, bitrate="2M")
                stream_frame = dev._stream.latest(timeout=7.0)
                if stream_frame is None or stream_frame.size == 0:
                    raise RuntimeError("không nhận được frame trong 7 giây")
                self.log_queue.put(
                    self.tr("test_stream_ok").format(time.monotonic() - started_at)
                )
                dev.stop_stream()

                stage = "scrcpy control"
                dev._ensure_control()
                if dev._control_socket is None:
                    raise RuntimeError("socket không được tạo")
                self.log_queue.put(self.tr("test_control_ok"))
            except Exception as exc:  # noqa: BLE001
                self.log_queue.put(self.tr("test_fail").format(stage, exc))
            finally:
                try:
                    dev.stop_stream()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    dev.close_control()
                except Exception:  # noqa: BLE001
                    pass
                self.root.after(0, lambda: self.test_control_btn.config(state="normal"))

        threading.Thread(target=run_test, daemon=True).start()

    def _connect_smart(self) -> None:
        """One-tap connect, no USB/Wi-Fi question asked.
        • First time (USB cable plugged in): switch the phone to adb-over-Wi-Fi and remember that
          wireless serial, so the cable can then be unplugged.
        • Later (no cable): reconnect the remembered Wi-Fi device — the same thing that picking
          it from the list does.
        If Wi-Fi can't be enabled it still connects over the cable, so you're never stuck."""
        # A single discovery pass also auto-registers MuMu's localhost ADB endpoint.
        # Adopt an online TCP device directly instead of showing the phone/USB instructions.
        try:
            attached = Device.list_devices()
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("msg_dev_err").format(e))
            attached = []

        tcp_devices = [s for s in attached if ":" in s]
        if tcp_devices:
            current = self._sel_serial()
            serial = current if current in tcp_devices else (
                Device.MUMU_SERIAL if Device.MUMU_SERIAL in tcp_devices else tcp_devices[0]
            )
            self.device_var.set(serial)
            self._remember_device(serial)
            self.refresh_devices()
            self._log(self.tr("conn_re_ok").format(serial))
            return

        if any(":" not in s for s in attached):
            # Cable plugged in → set up (or refresh) Wi-Fi so future connects are cable-free.
            self._connect_wifi(attached)
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

    def _connect_wifi(self, attached: list[str] | None = None) -> None:
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

        # Reuse the discovery result from Connect to avoid another adb round-trip.
        usb = [s for s in attached if ":" not in s] if attached is not None else None
        if usb is None or len(usb) > 1:
            self._pick_usb(start)
        elif usb:
            start(usb[0])
        else:
            self._log(self.tr("conn_need_usb"))
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
        report_seconds = 0 if shundo else int(self.alert_report.get())
        if report_seconds > 0 and now - self._last_report >= report_seconds:
            self._last_report = now
            up_min = int((now - self._run_started) / 60)
            rate = round(done / max((now - self._run_started) / 3600, 1 / 60))
            part = ""
            if self._batt_last.get("level") is not None:
                part = self.tr("dc_batt_part").format(self._batt_last["level"], self._batt_last.get("temp", "?"))
            self._send_discord(self.tr("dc_report").format(up_min, done, rate, stats.cycles, part))

    # -- live view -------------------------------------------------------------
    # -- live view -------------------------------------------------------------
    PV_WIDTHS = (340, 460, 600)

    def toggle_preview(self) -> None:
        """Mirror the phone in real time, with the running mode's own detections drawn over
        it, and let the mouse drive the phone through the same scrcpy control socket the
        routines use. Frames come from the H.264 stream, so this is a live mirror rather than
        the old one-shot screenshot every 800 ms."""
        if getattr(self, "_pv_win", None):
            self._close_preview()
            return
        try:
            dev = self.device or Device(self._sel_serial() or None)
            if not (self._sel_serial() or self.device):
                raise RuntimeError(self.tr("msg_no_device"))
            self._pv_dev = dev
            self._pv_size = dev.screen_size()
            dens = dev.density()
            # One detector per mode, scaled to this phone so the drawn boxes line up. The
            # overlay must show what the *running* mode sees, not always shundo's boxes.
            catch_cfg = self._apply_manual(CatchConfig().scale_to(*self._pv_size, dens), "catch")
            shundo_cfg = self._apply_manual(ShundoConfig().scale_to(*self._pv_size, dens), "shundo")
            spin_cfg = self._apply_manual(
                self._spin_config(CatchConfig()).scale_to(*self._pv_size, dens), "catch")
            self._pv_dets = {"catch": CatchRoutine(dev, catch_cfg),
                              "shundo": ShundoRoutine(dev, shundo_cfg),
                              "coord_shundo": ShundoRoutine(dev, shundo_cfg),
                              "spin": SpinRoutine(dev, spin_cfg)}
            # Only stop the stream on close if we were the ones who started it; while the bot
            # runs it owns the stream and pulling it out from under the routine would stall it.
            self._pv_owns_stream = dev._stream is None
            if self._pv_owns_stream:
                dev.start_stream(half=True, bitrate="2M")
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("pv_err").format(e))
            return

        win = tk.Toplevel(self.root)
        win.title(self.tr("preview"))
        self._pv_win = win
        win.protocol("WM_DELETE_WINDOW", self._close_preview)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=6, pady=(6, 2))
        self.pv_overlay = tk.BooleanVar(value=True)
        self.pv_control = tk.BooleanVar(value=True)
        # Tk variables must not be read from the worker threads (tkinter is not thread-safe —
        # doing so silently killed every frame), so mirror them into plain flags here, on the
        # UI thread, and let the threads read those.
        self._pv_overlay_on = True
        self._pv_control_on = True

        def sync_flags() -> None:
            self._pv_overlay_on = bool(self.pv_overlay.get())
            self._pv_control_on = bool(self.pv_control.get())

        ov = ttk.Checkbutton(bar, text=self.tr("pv_overlay"), variable=self.pv_overlay,
                             command=sync_flags)
        ov.pack(side="left")
        ct = ttk.Checkbutton(bar, text=self.tr("pv_control"), variable=self.pv_control,
                             command=sync_flags)
        ct.pack(side="left", padx=(10, 0))
        ttk.Button(bar, text=self.tr("pv_back"), width=7,
                   command=lambda: self._pv_key("KEYCODE_BACK")).pack(side="right", padx=2)
        ttk.Button(bar, text=self.tr("pv_home"), width=7,
                   command=lambda: self._pv_key("KEYCODE_HOME")).pack(side="right", padx=2)
        ttk.Button(bar, text=self.tr("pv_zoom"), width=4,
                   command=self._pv_cycle_size).pack(side="right", padx=(10, 2))

        self._pv_label = ttk.Label(win, cursor="hand2")
        self._pv_label.pack(padx=4, pady=4)
        self._pv_status = tk.StringVar(value="…")
        ttk.Label(win, textvariable=self._pv_status, foreground="#666").pack(anchor="w", padx=8)
        ttk.Label(win, text=self.tr("pv_hint"), wraplength=self.PV_WIDTHS[-1],
                  justify="left", foreground="#555").pack(anchor="w", padx=8, pady=(2, 0))
        ttk.Label(win, text=self.tr("pv_legend"), wraplength=self.PV_WIDTHS[-1],
                  justify="left").pack(padx=8, pady=(4, 8))

        for seq, handler in (("<ButtonPress-1>", self._pv_press),
                             ("<B1-Motion>", self._pv_drag),
                             ("<ButtonRelease-1>", self._pv_release)):
            self._pv_label.bind(seq, handler)

        self._pv_width = self.PV_WIDTHS[0]
        self._pv_img = None
        self._pv_layer = None          # (layer, mask) at full device resolution
        self._pv_error = None
        self._pv_queue: queue.Queue = queue.Queue(maxsize=1)
        self._pv_stop = threading.Event()
        self._pv_threads = [threading.Thread(target=t, daemon=True)
                            for t in (self._pv_loop, self._pv_overlay_loop)]
        for t in self._pv_threads:
            t.start()
        self._pv_pump()

    def _pv_pump(self) -> None:
        """Drain the newest mirrored frame onto the window. Runs on the UI thread."""
        if getattr(self, "_pv_win", None) is None:
            return
        try:
            data, shown, status = self._pv_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            img = tk.PhotoImage(data=data)
            self._pv_img = img              # keep a reference or Tk drops it
            self._pv_shown = shown
            self._pv_label.config(image=img)
            self._pv_status.set(f"{status}   ⚠ {self._pv_error}" if self._pv_error else status)
        self.root.after(30, self._pv_pump)

    def _close_preview(self) -> None:
        win = getattr(self, "_pv_win", None)
        self._pv_win = None
        stop = getattr(self, "_pv_stop", None)
        if stop is not None:
            stop.set()
        for thread in getattr(self, "_pv_threads", []) or []:
            thread.join(timeout=2.0)
        self._pv_threads = []
        self._pv_layer = None
        if getattr(self, "_pv_owns_stream", False) and getattr(self, "_pv_dev", None) is not None:
            try:
                self._pv_dev.stop_stream()
            except Exception:  # noqa: BLE001
                pass
        self._pv_owns_stream = False
        if win is not None:
            try:
                win.destroy()
            except Exception:  # noqa: BLE001
                pass

    def _pv_cycle_size(self) -> None:
        widths = self.PV_WIDTHS
        self._pv_width = widths[(widths.index(self._pv_width) + 1) % len(widths)]

    # -- live view: pointer forwarding ----------------------------------------
    def _pv_to_device(self, event) -> tuple[int, int] | None:
        """Map a click on the mirrored image to real device pixels."""
        shown = getattr(self, "_pv_shown", None)
        if shown is None:
            return None
        disp_w, disp_h = shown
        dev_w, dev_h = self._pv_size
        if disp_w <= 0 or disp_h <= 0:
            return None
        x = int(event.x * dev_w / disp_w)
        y = int(event.y * dev_h / disp_h)
        if not (0 <= x < dev_w and 0 <= y < dev_h):
            return None
        return x, y

    def _pv_device(self):
        return self.device if self.device is not None else self._pv_dev

    def _pv_press(self, event) -> None:
        if not self.pv_control.get():
            return
        pt = self._pv_to_device(event)
        if pt is None:
            return
        self._pv_last_pt = pt
        try:
            self._pv_device().touch_down(*pt)
        except Exception as e:  # noqa: BLE001
            self._pv_status.set(self.tr("pv_err").format(e))

    def _pv_drag(self, event) -> None:
        if not self.pv_control.get():
            return
        pt = self._pv_to_device(event)
        if pt is None:
            return
        self._pv_last_pt = pt
        try:
            self._pv_device().touch_move(*pt)
        except Exception:  # noqa: BLE001
            pass

    def _pv_release(self, event) -> None:
        if not self.pv_control.get():
            return
        pt = self._pv_to_device(event) or getattr(self, "_pv_last_pt", None)
        if pt is None:
            return
        try:
            self._pv_device().touch_up(*pt)
        except Exception:  # noqa: BLE001
            pass

    def _pv_key(self, keycode: str) -> None:
        try:
            self._pv_device().key(keycode)
        except Exception as e:  # noqa: BLE001
            self._pv_status.set(self.tr("pv_err").format(e))

    # -- live view: frame pump -------------------------------------------------
    def _pv_overlay_loop(self) -> None:
        """Recompute the detection overlay on its own slow cadence.

        A full annotate pass costs ~200 ms because it runs the real detectors; doing that per
        displayed frame would drop the mirror to 4 fps and make it useless for control. Instead
        it is drawn onto a blank canvas here, and the display loop composites that layer onto
        live frames — so the overlay lags by up to a second while the video stays smooth.
        """
        while not self._pv_stop.is_set():
            if not self._pv_overlay_on:
                self._pv_layer = None
                self._pv_stop.wait(0.2)
                continue
            try:
                frame = self._pv_device().screenshot()
                det = self._pv_dets.get(self.mode) or self._pv_dets["catch"]
                layer = np.zeros_like(frame)
                det.annotate(frame, canvas=layer)
                # Anything the annotate pass drew is non-black; that is the composite mask.
                mask = layer.any(axis=2)
                self._pv_layer = (layer, mask)
            except Exception as e:  # noqa: BLE001
                self._pv_layer = None
                self._pv_error = f"overlay {type(e).__name__}: {e}"
            self._pv_stop.wait(0.8)

    def _pv_loop(self) -> None:
        """Pump stream frames to the UI, compositing the cached overlay layer onto each one."""
        frames = 0
        fps_since = time.monotonic()
        fps = 0.0
        while not self._pv_stop.is_set():
            try:
                frame = self._pv_device().screenshot(next_frame=True)
                h, w = frame.shape[:2]
                target_w = self._pv_width
                small = cv2.resize(frame, (target_w, int(h * target_w / w)))
                layer = self._pv_layer if self._pv_overlay_on else None
                if layer is not None:
                    # Composite after downscaling: a few hundred KB instead of 10 MB per frame.
                    lay, mask = layer
                    size = (small.shape[1], small.shape[0])
                    lay_s = cv2.resize(lay, size, interpolation=cv2.INTER_NEAREST)
                    mask_s = cv2.resize(mask.astype(np.uint8), size,
                                        interpolation=cv2.INTER_NEAREST).astype(bool)
                    small[mask_s] = lay_s[mask_s]
                ok, png = cv2.imencode(".png", small)
                if not ok:
                    continue
                data = base64.b64encode(png.tobytes())
                shown = (small.shape[1], small.shape[0])
                frames += 1
                if time.monotonic() - fps_since >= 1.0:
                    fps = frames / (time.monotonic() - fps_since)
                    frames, fps_since = 0, time.monotonic()
                status = self.tr("pv_status").format(
                    fps, self._pv_size[0], self._pv_size[1],
                    self.tr("pv_on") if self._pv_control_on else self.tr("pv_off"))
                # Hand the finished frame over through a queue drained on the UI thread,
                # the way the log already works. Touching Tk from here (even via after())
                # is not safe, and a slow UI would otherwise pile up callbacks.
                try:
                    self._pv_queue.get_nowait()     # only the newest frame is worth showing
                except queue.Empty:
                    pass
                self._pv_queue.put_nowait((data, shown, status))
            except Exception as e:  # noqa: BLE001
                # A mirror that silently shows nothing is impossible to diagnose; keep the
                # last failure where the status line (and a bug report) can see it.
                self._pv_error = f"{type(e).__name__}: {e}"
                self._pv_stop.wait(0.3)

    # -- run control ----------------------------------------------------------
    # -- manual alignment -----------------------------------------------------
    def _cal_defaults(self, w: int, h: int, dens) -> dict:
        """Auto positions (device px) for this screen, used as starting handles."""
        c = CatchConfig().scale_to(w, h, dens)
        s = ShundoConfig().scale_to(w, h, dens)
        cs = CoordShundoConfig().scale_to(w, h, dens)
        # Through _spin_config so the handle opens on the circle the radius setting describes,
        # rather than on the bare dataclass default the user never chose.
        spin = self._spin_config(CatchConfig()).scale_to(w, h, dens)
        return {
            "nearby_slot":         list(c.nearby_slot),
            "ball_fallback":       list(c.ball_fallback),
            "berry_start":         list(c.berry_start),
            "berry_end":           list(c.berry_end),
            "flee_xy":             list(c.flee_xy),
            "pokestop_close_xy":   list(c.pokestop_close_xy),
            "out_of_balls_region": list(c.out_of_balls_region),
            "pill_region":         list(s.pill_region),
            "toast_region":        list(s.toast_region),
            "teleport_xy":         list(cs.teleport_xy),
            "teleport_input_xy":   list(cs.teleport_input_xy),
            "teleport_ok_xy":      list(cs.teleport_ok_xy),
            "spin_region":         list(spin.spin_region),
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

        win = tk.Toplevel(self.root); win.title(self.tr("cal_title")); win.resizable(True, True)
        self._cal_win = win
        win.protocol("WM_DELETE_WINDOW", self._cal_close)
        ttk.Label(win, text=self.tr("cal_hint"), wraplength=disp_w + 200,
                  foreground="#555", justify="left").pack(anchor="w", padx=8, pady=(8, 4))
        # Keep the actions visible at the top even when a tall phone screenshot extends
        # below the desktop.  The window itself can now be maximized or resized.
        btns = ttk.Frame(win); btns.pack(fill="x", padx=8, pady=(2, 6))
        ttk.Button(btns, text=self.tr("cal_save"), command=self._cal_save).pack(side="right", padx=3)
        ttk.Button(btns, text=self.tr("cal_reset"), command=self._cal_reset).pack(side="right", padx=3)
        ttk.Button(btns, text=self.tr("cal_cancel"), command=self._cal_close).pack(side="right", padx=3)
        body = ttk.Frame(win); body.pack(fill="both", expand=True, padx=8, pady=4)
        cv = tk.Canvas(body, width=disp_w, height=disp_h, highlightthickness=1,
                       highlightbackground="#888", cursor="crosshair")
        cv.pack(side="left", fill="both", expand=True)
        self._cal_canvas = cv
        if self._cal_photo is not None:
            cv.create_image(0, 0, anchor="nw", image=self._cal_photo)
        groups = ttk.Notebook(body); groups.pack(side="left", fill="y", padx=(10, 0))
        for mode, title in (("normal", "cal_group_normal"), ("quick", "cal_group_quick"),
                            ("shundo", "cal_group_shundo"), ("coord", "cal_group_coord"),
                            ("spin", "cal_group_spin")):
            page = ttk.Frame(groups)
            groups.add(page, text=self.tr(title))
            for field, kind, item_mode, key, color in self._cal_items(mode):
                row = ttk.Frame(page); row.pack(anchor="w", fill="x", padx=6, pady=4)
                sw = tk.Canvas(row, width=16, height=16, highlightthickness=0)
                sw.pack(side="left"); sw.create_rectangle(2, 2, 14, 14, fill=color, outline=color)
                # A default that scales off-screen (or under the phone's own bottom bar) leaves
                # its handle impossible to grab. This drops it back in the middle of the screen
                # so it can be dragged from somewhere reachable.
                btn = ttk.Button(row, text="⌖", width=3,
                                 command=lambda f=field: self._cal_center(f))
                btn.pack(side="right", padx=(4, 0))
                self._cal_tip(btn, "cal_center_tip")
                ttk.Label(row, text=self.tr(key), wraplength=175).pack(side="left", padx=4)
            allrow = ttk.Frame(page); allrow.pack(anchor="w", fill="x", padx=6, pady=(10, 4))
            ttk.Button(allrow, text=self.tr("cal_center_all"),
                       command=lambda g=mode: self._cal_center_all(g)).pack(fill="x")
        self._cal_groups = groups
        self._cal_group = ({"shundo": "shundo", "coord_shundo": "coord", "spin": "spin"}.get(self.mode)
                            or self.catch_style)
        groups.select({"normal": 0, "quick": 1, "shundo": 2, "coord": 3, "spin": 4}[self._cal_group])
        groups.bind("<<NotebookTabChanged>>", self._cal_group_changed)
        self._cal_active = None
        cv.bind("<ButtonPress-1>", self._cal_press)
        cv.bind("<B1-Motion>", self._cal_drag)
        cv.bind("<ButtonRelease-1>", self._cal_release)
        self._cal_redraw()

    def _cal_redraw(self) -> None:
        c = self._cal_canvas; sf = self._cal_sf
        c.delete("ov")
        # Show the Quick Catch drag direction underneath its two draggable handles.
        if self._cal_group == "quick" and "berry_start" in self._cal and "berry_end" in self._cal:
            x1, y1 = (n * sf for n in self._cal["berry_start"])
            x2, y2 = (n * sf for n in self._cal["berry_end"])
            c.create_line(x1, y1, x2, y2, fill="#7c4dff", width=4,
                          arrow="last", dash=(7, 4), tags="ov")
        for field, kind, mode, key, color in self._cal_items():
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
        for field, kind, item_mode, *_ in self._cal_items():  # points + resize handles first
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
            for field, kind, item_mode, *_ in self._cal_items():
                if kind != "region":
                    continue
                v = self._cal[field]; x, y, ww, hh = v[0] * sf, v[1] * sf, v[2] * sf, v[3] * sf
                if x <= mx <= x + ww and y <= my <= y + hh:
                    pick = (field, "move", mx - x, my - y); break
        self._cal_active = pick

    def _cal_tip(self, widget, key: str) -> None:
        """Plain hover tooltip — ttk has none built in and this is the only place we need one."""
        tip = {"win": None}

        def show(_e=None):
            if tip["win"] is not None:
                return
            x = widget.winfo_rootx() + widget.winfo_width() + 6
            y = widget.winfo_rooty()
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            tk.Label(win, text=self.tr(key), background="#ffffe0", relief="solid",
                     borderwidth=1, justify="left", wraplength=260,
                     font=("Segoe UI", 8)).pack()
            tip["win"] = win

        def hide(_e=None):
            if tip["win"] is not None:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _cal_center(self, field: str) -> None:
        """Move one handle to the middle of the screen so it can be reached and dragged."""
        w, h = self._cal_dev_size
        v = self._cal[field]
        if len(v) == 2:
            v[0], v[1] = w // 2, h // 2
        else:
            v[0], v[1] = max(0, w // 2 - v[2] // 2), max(0, h // 2 - v[3] // 2)
        self._cal_redraw()

    def _cal_center_all(self, group: str) -> None:
        """Same for every handle in the current tab — the quick way out when a whole group
        scaled off the bottom of the screen."""
        for field, _kind, _mode, _key, _color in self._cal_items(group):
            self._cal_center(field)

    def _cal_group_changed(self, _event=None) -> None:
        self._cal_group = ("normal", "quick", "shundo", "coord", "spin")[self._cal_groups.index("current")]
        self._cal_active = None
        self._cal_redraw()

    def _cal_items(self, group: str | None = None):
        """Handles for one tab. A field with no entry in `_cal` is dropped rather than raised
        on: every caller loops over these, so one missing default used to abort the redraw
        part-way and leave a window with some markers drawn, some silently absent, and no
        error anywhere — which is how a new handle can look like a broken drag."""
        fields = set(CALIB_GROUP_FIELDS[group or self._cal_group])
        have = getattr(self, "_cal", {})
        return [item for item in CALIB_ITEMS if item[0] in fields and item[0] in have]

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

    def _spin_config(self, cfg):
        """Fold the spinning settings into a CatchConfig, in BASE_RESOLUTION coordinates.

        Applied *before* scale_to so the scan circle is re-anchored onto the phone by the same
        code path as every other coordinate — writing device pixels here instead would mean the
        circle alone never followed a measured render scale. Manual alignment still wins, since
        it is laid over the result afterwards.
        """
        r = max(50, int(self.spin_radius.get()))
        # Centred on the avatar's feet, with a radius big enough to swallow the pole a stop's
        # cube stands on (measured 179 px and 164 px above its own ground disc). Lifting the
        # circle instead was the tidier theory and the worse default: it drops stops standing
        # just below the avatar, which are as reachable as the ones above. Radius from the box
        # the player drew over their own map — the only measurement here made by someone who
        # can see which stops are actually in range.
        cx, cy = 610, 1750
        return replace(
            cfg,
            spin_region=(cx - r, cy - r, 2 * r, 2 * r),
            spin_interval=max(0.5, float(self.spin_gap.get())),
            spin_min_area=max(200, int(self.spin_min_area.get())),
            spin_on_no_balls=bool(self.no_balls_spin.get()),
            no_balls_pause=max(60.0, float(self.no_balls_min.get()) * 60.0),
        )

    def _apply_manual(self, cfg, mode: str):
        """Overwrite tap points / boxes with the manually-aligned device-pixel values."""
        m = self.manual
        if not m or not m.get("_screen"):
            return cfg
        source_w, source_h = (int(v) for v in m["_screen"])
        target_w, target_h = cfg.screen
        scale_x = target_w / source_w if source_w else 1.0
        scale_y = target_h / source_h if source_h else 1.0

        def P(name):
            v = m.get(name)
            if not isinstance(v, (list, tuple)) or len(v) != 2:
                return None
            return (int(round(v[0] * scale_x)), int(round(v[1] * scale_y)))

        def R(name):
            v = m.get(name)
            if not isinstance(v, (list, tuple)) or len(v) != 4:
                return None
            return (
                int(round(v[0] * scale_x)), int(round(v[1] * scale_y)),
                int(round(v[2] * scale_x)), int(round(v[3] * scale_y)),
            )

        if mode == "catch":
            if P("nearby_slot"):
                cfg.nearby_slot = P("nearby_slot")
                cfg.require_anchor = False
                cfg.force_slot = True
            if P("ball_fallback"):
                cfg.ball_fallback = P("ball_fallback")
            if P("berry_start"):
                cfg.berry_start = P("berry_start")
            if P("berry_end"):
                cfg.berry_end = P("berry_end")
            if P("flee_xy"):
                cfg.flee_xy = P("flee_xy")
            if P("pokestop_close_xy"):
                cfg.pokestop_close_xy = P("pokestop_close_xy")
            if R("out_of_balls_region"):
                cfg.out_of_balls_region = R("out_of_balls_region")
            if R("spin_region"):
                cfg.spin_region = R("spin_region")
        else:
            if P("flee_xy"):
                cfg.flee_xy = P("flee_xy")
            if R("pill_region"):
                cfg.pill_region = R("pill_region")
            if R("toast_region"):
                cfg.toast_region = R("toast_region")
            if mode == "coord_shundo":
                if P("teleport_xy"):
                    cfg.teleport_xy = P("teleport_xy")
                if P("teleport_input_xy"):
                    cfg.teleport_input_xy = P("teleport_input_xy")
                if P("teleport_ok_xy"):
                    cfg.teleport_ok_xy = P("teleport_ok_xy")
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
            if self.mode in ("shundo", "coord_shundo"):
                config_type = CoordShundoConfig if self.mode == "coord_shundo" else ShundoConfig
                cfg = config_type(
                    # Discord Coord must never consume another coordinate merely because
                    # this spawn is slow. It waits until the current spawn can be checked.
                    spawn_timeout=(0.0 if self.mode == "coord_shundo"
                                   else max(0.0, float(self.tp_wait.get()))),
                    encounter_open_wait=max(2.0, float(self.s_enc_wait.get())),
                    shundo_action=self.shundo_action,
                    shiny_action=self.shiny_action,
                    flee_taps=max(1, int(self.flee_taps.get())),
                    flee_gap_ms=max(0, int(round(float(self.flee_gap.get()) * 1000))),
                )
                if dev_size is not None:
                    cfg = cfg.scale_to(*dev_size, dev_dens)
                manual_mode = "coord_shundo" if self.mode == "coord_shundo" else "shundo"
                cfg = self._apply_manual(cfg, manual_mode)
                if self.mode == "coord_shundo":
                    self.routine = CoordShundoRoutine(self.device, self.coord_queue, cfg)
                else:
                    self.routine = ShundoRoutine(self.device, cfg)
                self.routine._on_waiting = lambda s: self.log_queue.put(self.tr("msg_s_waiting").format(s))
                # If the routine re-derives coordinates from a measured render scale, the
                # hand-aligned points must be laid back over the result — they are the user's
                # own correction and outrank any measurement.
                self.routine._on_rescale = lambda c, m=manual_mode: self._apply_manual(c, m)
            elif self.mode == "spin":
                # A CatchConfig without the catching: SpinRoutine is a CatchRoutine that spins
                # instead of throwing, so it inherits the popup handling, the AutoWalk restarts
                # and the calibration wholesale — and reads them out of the same config.
                cfg = self._spin_config(CatchConfig(
                    flee_taps=max(1, int(self.flee_taps.get())),
                    flee_gap_ms=max(0, int(round(float(self.flee_gap.get()) * 1000))),
                ))
                if dev_size is not None:
                    cfg = cfg.scale_to(*dev_size, dev_dens)
                cfg = self._apply_manual(cfg, "catch")
                self.routine = SpinRoutine(self.device, cfg)
                self.routine._on_trace = self.log_queue.put
                self.routine._on_rescale = lambda c: self._apply_manual(c, "catch")
            else:
                throw_power = abs(int(self.throw_power.get()))
                cfg = CatchConfig(
                    throw_dy=-throw_power,
                    encounter_timeout=max(2.0, float(self.wait_enc.get())),
                    catch_timeout=max(2.0, float(self.wait_catch.get())),
                    idle_before_autowalk=int(self.idle_aw.get()),
                    max_catches=int(self.max_catches.get()),
                    settle_after_catch=max(0.0, float(self.settle.get())),
                    quick_catch=self.catch_style == "quick",
                    quick_flick_ms=max(50, int(round(float(self.quick_flick.get()) * 1000))),
                    encounter_touch_delay_ms=max(0, int(round(float(self.touch_delay.get()) * 1000))),
                    post_throw_wait_ms=max(0, int(round(float(self.post_throw.get()) * 1000))),
                    flee_taps=max(1, int(self.flee_taps.get())),
                    flee_gap_ms=max(0, int(round(float(self.flee_gap.get()) * 1000))),
                    max_throws_per_encounter=max(1, int(self.max_throws.get())),
                    use_feed_bar=bool(self.catch_use_feed.get()),
                    start_goplus_on_no_balls=(
                        self.catch_style == "normal" and bool(self.no_balls_goplus.get())
                    ),
                    min_catch_interval=max(0.0, float(self.min_gap.get())),
                    pre_tap_delay=max(0.0, float(self.pre_tap.get())),
                    respect_cooldown=bool(self.respect_cd.get()),
                    use_ui_dump=bool(self.use_ui_dump.get()),
                    trace_timing=bool(self.trace_timing.get()),
                )
                cfg = self._spin_config(cfg)
                if dev_size is not None:
                    cfg = cfg.scale_to(*dev_size, dev_dens)
                cfg = self._apply_manual(cfg, "catch")
                self.routine = CatchRoutine(self.device, cfg)
                self.routine._on_trace = self.log_queue.put
                self.routine._on_rescale = lambda c: self._apply_manual(c, "catch")
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("msg_no_init").format(e))
            return

        # Stamp the log with what this run is running on, before the run produces a single line.
        # Without it the trace that follows cannot be read: the same message means different
        # things on a 1220x2712 phone over USB and on a smaller one over a slow Wi-Fi link.
        try:
            diag.session_banner(diag.device_info(self.device, {
                "che_do": self.mode,
                "kieu_bat": getattr(self, "catch_style", "?"),
                "can_chinh_tay": "co" if self.manual else "khong",
            }))
        except Exception:  # noqa: BLE001
            pass

        self.paused = False
        self._empty_streak = 0
        self._alert_fired = False
        self._coord_idle_logged = False
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
                # on_event runs on the worker thread; read the plain config value captured at
                # startup, never a tkinter variable from here.
                with_goplus = bool(getattr(
                    getattr(self.routine, "config", None),
                    "start_goplus_on_no_balls",
                    False,
                ))
                self.log_queue.put(self.tr("msg_no_balls_goplus" if with_goplus else "msg_no_balls"))
                self._send_discord(
                    self.tr("dc_no_balls_goplus" if with_goplus else "dc_no_balls"),
                    shot=True,
                )
                return
            if stats.last_event == "goplus_started":
                self.log_queue.put(self.tr("msg_goplus_started"))
                return
            if stats.last_event == "autowalk":
                self.log_queue.put(self.tr("msg_autowalk").format(stats.autowalks))
                return
            if stats.last_event == "spin":
                self.log_queue.put(self.tr("msg_spin").format(stats.spins))
                # Not __count__: that counter is labelled "Thrown", and this mode never throws.
                self.log_queue.put("__countstr__" + self.tr("spun").format(stats.spins))
                return
            # An empty cycle means different things in different modes, and the catch line below
            # says "no Pokémon" — which is nonsense while spinning stops, and worse, reads as a
            # fault when the mode is working exactly as intended.
            if self.mode == "spin":
                self.log_queue.put(self.tr("msg_spin_idle").format(stats.cycles))
                self.log_queue.put("__countstr__" + self.tr("spun").format(stats.spins))
                return
            tag = self.tr("msg_throw") if threw else self.tr("msg_empty")
            self.log_queue.put(self.tr("msg_cycle").format(stats.cycles, tag, stats.throws))
            self.log_queue.put(f"__count__{stats.throws}")
            self._tick_alerts(stats, threw)

        def on_shundo_event(stats, outcome):
            self.log_queue.put("__countstr__" + self.tr("s_counts").format(stats.checked, stats.shinies, stats.shundos))
            if outcome != "coord_idle":
                self._coord_idle_logged = False
            if self.mode == "coord_shundo" and outcome in ("blocked", "shiny", "shundo"):
                # A confirmed result releases exactly one new-coordinate credit to Edge.
                # Ambiguous miss/recheck cycles keep the same item and release nothing.
                self.coord_queue.mark_completed()
            if self.mode == "coord_shundo" and outcome in ("blocked", "shiny", "shundo", "nospawn", "lost"):
                item = getattr(self.routine, "current_coord", None)
                if item is not None:
                    name = f" ({item.pokemon})" if item.pokemon else ""
                    self.log_queue.put(self.tr("msg_coord_using").format(
                        item.coordinate, name, self.coord_queue.qsize()))
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
            elif outcome == "goplus":
                # Shundo teleports every cycle and Go Plus refuses every teleport; the
                # routine ends itself, so say plainly why rather than looking like a crash.
                self.log_queue.put(self.tr("msg_s_goplus"))
                self._send_discord(self.tr("msg_s_goplus"))
            elif outcome == "blocked":
                self.log_queue.put(self.tr("msg_s_blocked").format(stats.checked, stats.shinies, stats.shundos))
            elif outcome == "fled":
                self.log_queue.put(self.tr("msg_s_fled"))
            elif outcome == "flee_failed":
                self.log_queue.put(self.tr("msg_s_flee_failed"))
            elif outcome == "miss":
                self.log_queue.put(self.tr("msg_s_miss"))
            elif outcome == "recheck":
                self.log_queue.put(self.tr("msg_s_recheck"))
            elif outcome == "lost":
                self.log_queue.put(self.tr("msg_s_lost"))
            elif outcome == "nospawn":
                self.log_queue.put(self.tr("msg_s_nospawn"))
            elif outcome == "idle":
                self.log_queue.put(self.tr("msg_s_idle"))
            elif outcome == "coord_idle":
                if not self._coord_idle_logged:
                    self.log_queue.put(self.tr("msg_coord_idle"))
                    self._coord_idle_logged = True
            # A recheck is the bot standing still waiting to see the bar again, so it must not
            # count as activity — otherwise a run stuck looking at nothing never trips the
            # idle alert. Giving the entry up does advance the feed, so that one does.
            self._tick_alerts(
                stats, outcome not in ("idle", "coord_idle", "popup", "recheck"), shundo=True)

        dim = self.dim_screen.get()
        try:
            if dim:
                self.device.enable_dim()
                self.log_queue.put(self.tr("msg_dim"))
            # Keep the continuous stream light in both modes. Shundo requests a crisp
            # one-shot capture only when an encounter opens and IV digits must be read.
            if self.mode in ("shundo", "coord_shundo"):
                self.device.start_stream(half=True, bitrate="2M")
            else:
                self.device.start_stream()
            self.routine.run(
                on_event=on_shundo_event if self.mode in ("shundo", "coord_shundo") else on_event)
            # A safety stop already has a precise error in the log. Do not immediately
            # overwrite its meaning with the generic "Done." message.
            if self.mode in ("shundo", "coord_shundo") and self.routine.stats.last_event == "flee_failed":
                self.log_queue.put("__done__")
            else:
                self.log_queue.put("__done__" + self.tr("msg_done"))
        except Exception as e:  # noqa: BLE001
            self.log_queue.put("__done__" + self.tr("msg_err").format(e))
            # The bot died while unattended — this is the alert that matters most.
            self._send_discord(self.tr("dc_stopped").format(e), shot=True)
        finally:
            self.device.stop_stream()
            self.device.close_control()
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
        if message:
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
        # Every line the pane shows also goes to disk. The pane holds the last few hundred lines
        # and is gone the moment the window closes, which is why a "it stops working sometimes"
        # report never arrived with anything attached to it.
        diag.write(text)
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def export_report(self) -> None:
        """Bundle the log, the redacted settings and a screenshot into one zip to send back."""
        default = f"baocao-{time.strftime('%Y%m%d-%H%M')}.zip"
        dest = filedialog.asksaveasfilename(
            parent=self.root, defaultextension=".zip", initialfile=default,
            filetypes=[("Zip", "*.zip")],
        )
        if not dest:
            return
        screenshot = None
        notes: dict = {}
        if self.device is not None:
            try:
                screenshot = self.device.screenshot(fresh=True)
            except Exception:  # noqa: BLE001
                pass
            try:
                notes = diag.device_info(self.device)
            except Exception:  # noqa: BLE001
                pass
        routine = self.routine
        if routine is not None:
            # The measured render scale is the one number that says whether detection is running
            # on a calibrated device or on the wide fallback bracket — see _ensure_calibrated.
            notes["scale_do_duoc"] = getattr(routine, "_cal_scale", None) or "(chua khoa duoc)"
            notes["che_do"] = self.mode
        try:
            diag.export(dest, settings_path=_settings_path(),
                        screenshot=screenshot, notes=notes)
        except Exception as e:  # noqa: BLE001
            self._log(self.tr("export_fail").format(e))
            return
        self._log(self.tr("export_ok").format(dest))


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
