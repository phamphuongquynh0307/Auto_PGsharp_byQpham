# v0.3.0 verification

- 39 tests passed: background scheduling/delivery, parsing, IV calculations, auth gates and compact popup actions.
- Popup uses action.default_popup=panel.html; no cloned filter view, no unsolicited login tab on popup open.
- Checked local preview visually; settings/history switching and draft preservation covered by tests.
- Real Edge installation of v0.3.0 remains unverified. Previously installed v0.1.0 showed running authenticated monitor and three delivered notifications in its history.

- Discord summary: Pokédex sprite thumbnail, isolated coordinate code block, PvP 1500/2500 labels and rank fields. Stats has IV and CP/level without ranks. Payload verified in tests; new format not yet verified in actual Discord channel.

- v0.3.0: PvP league/cap, species and ranks are grouped into one bold line. All 11 core tests passed.

Bản 0.2.4: Trong tab Thông báo, bấm Xóa lịch sử & thử lại. Extension dừng lịch, xóa lịch sử và dấu đã báo; giữ nguyên cấu hình và webhook. Sau đó bấm Tìm ngay hoặc Chạy tự động. Không xóa tin trong Discord. Kiểm tra tự động: 41 passed. Chưa thực hiện xóa trên extension đang cài trong Edge.

- v0.3.0 reports skipped PvP thresholds, duplicate, expired and coordinate failures in status. All 17 background tests passed, including reset then redelivery and threshold-rejection diagnostic. No live cause confirmed for the user report yet.
