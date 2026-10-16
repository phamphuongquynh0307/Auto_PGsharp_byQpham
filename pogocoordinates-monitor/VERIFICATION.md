# v0.3.7 verification

- 57 tests passed: system keep-awake, tab discard protection/restoration, unlimited duration, transient retry/recovery, loading page recovery, startup/deadline and fatal-error cleanup, plus existing search/Discord/UI regressions.
- Long-running behavior in actual Edge, OS sleep prevention and browser tab suspension have not been verified live.

## v0.3.6 verification

- All 51 tests passed. Information and coordinates are distinct Discord POSTs; coordinate message contains only raw coords and disabled mentions.
- Covers deduplication, rate limiting on either message, uncertain delivery and manual retry without duplicate information.
- Actual mobile copying has not been verified in this session.

## v0.3.5 verification

- All 49 extension tests passed: league/evolution species ranking, new web columns, unchanged parsed spawn data, Stats cleanup, public-only read bridge and Discord regression checks.
- Unknown forms and species absent from rankings show no rank rather than guessing.
- Live browser layout and installation have not been verified in this session.

## v0.3.4 verification

- All 45 extension tests passed. Raw coordinates are the message content; restored Pokémon details remain in an embed.
- Covered both Stats/PvP, negative coordinates, deduplication, retries and stable despawn timestamps.
- Discord mobile Copy Text has not been verified on an actual phone in this session.

## v0.3.3 verification

- All 43 extension tests passed, including coordinate-only Discord payloads for Stats/PvP and retries.
- Live browser installation, actual Discord delivery and mobile copying have not been verified in this session.

## v0.3.2 verification

- All 44 extension tests passed. Covers on-page running/stopped/disconnected status, collapsing the indicator, despawn timestamps and retry deadlines, and excluding secrets from page status replies.
- ZIP manifest and popup version verified as 0.3.2. User confirmed the local result was satisfactory; live browser installation and Discord delivery have not been independently verified in this session.

- 39 tests passed: background scheduling/delivery, parsing, IV calculations, auth gates and compact popup actions.
- Popup uses action.default_popup=panel.html; no cloned filter view, no unsolicited login tab on popup open.
- Checked local preview visually; settings/history switching and draft preservation covered by tests.
- Real Edge installation of v0.3.0 remains unverified. Previously installed v0.1.0 showed running authenticated monitor and three delivered notifications in its history.

- Discord summary: Pokédex sprite thumbnail, isolated coordinate code block, PvP 1500/2500 labels and rank fields. Stats has IV and CP/level without ranks. Payload verified in tests; new format not yet verified in actual Discord channel.

- v0.3.0: PvP league/cap, species and ranks are grouped into one bold line. All 11 core tests passed.

Bản 0.2.4: Trong tab Thông báo, bấm Xóa lịch sử & thử lại. Extension dừng lịch, xóa lịch sử và dấu đã báo; giữ nguyên cấu hình và webhook. Sau đó bấm Tìm ngay hoặc Chạy tự động. Không xóa tin trong Discord. Kiểm tra tự động: 41 passed. Chưa thực hiện xóa trên extension đang cài trong Edge.

- v0.3.0 reports skipped PvP thresholds, duplicate, expired and coordinate failures in status. All 17 background tests passed, including reset then redelivery and threshold-rejection diagnostic. No live cause confirmed for the user report yet.
