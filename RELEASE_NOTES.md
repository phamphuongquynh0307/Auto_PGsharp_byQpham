# v1.4.4

## Tiếng Việt

### Sửa lỗi bot đứng im vô hạn sau khi tap Feed

- Sau khi tap một mục trên thanh Feed, app khoá nguồn Feed lại và chờ Pokémon đó xuất hiện trên thanh Nearby. Vòng chờ này **không có giới hạn nào** — nó chỉ kết thúc khi Pokémon hiện ra hoặc người dùng bấm Dừng.
- Nếu PGSharp bỏ qua cú tap, hoặc Pokémon đã biến mất trước khi bản đồ tải xong, thì không bao giờ có gì xuất hiện và cả routine đứng im cho tới hết phiên chạy. Ghi nhận thực tế: đứng yên 11 phút, log lặp lại "vẫn chờ Pokémon hiện trên Nearby" mỗi 10 giây.
- Nay vòng chờ có hạn mức thật. Hết hạn, app nhả khoá Feed, ghi rõ lý do vào log và trả vòng lặp về Nearby + AutoWalk.
- Đây không phải đường Go Plus: bỏ qua một con vì hết giờ **không** làm tắt nguồn Feed cho cả phiên, lần khô kế tiếp vẫn được thử Feed lại bình thường.

### Thêm ô chỉnh thời gian chờ Feed, hiện ra khi bật Feed

- Thêm **Chờ Pokémon từ Feed hiện trên Nearby (giây, 0 = chờ mãi)** vào nhóm Bắt Pokémon, mặc định 45 giây.
- Ô này chỉ hiện khi đã tick **Nearby hết Pokémon: lấy 1 con từ Feed**, giống cách ô số phút chỉ hiện khi bật quay PokéStop — một ô không có tác dụng thì không nên bày ra trước mặt người dùng.
- Đặt 0 để giữ nguyên hành vi chờ mãi như các bản trước.
- Trước đây ô "Chờ Pokémon xuất hiện trên Nearby" duy nhất trong app chỉ nối vào chế độ Shundo, nên ở chế độ Bắt Pokémon người dùng hoàn toàn không có cách nào đặt giới hạn.

### Kiểm chứng

- **206 test đạt**, không có lỗi.
- Bộ test mới bao phủ: vòng chờ kết thúc khi hết hạn và nhả khoá mà không ăn thêm mục Feed nào, nguồn Feed vẫn dùng lại được ở vòng sau, giá trị 0 giữ đúng hành vi chờ mãi, và ô cài đặt ẩn/hiện theo trạng thái của checkbox.

---

## English

### Fixed the bot standing still indefinitely after tapping the Feed

- After tapping a Feed entry the app locks the Feed source and waits for that Pokémon to reach the Nearby bar. That wait had **no ceiling at all** — it ended only when the Pokémon appeared or the user pressed Stop.
- If PGSharp dropped the tap, or the spawn despawned before the map finished loading, nothing ever arrived and the whole routine stood still for the rest of the run. Observed in practice: 11 minutes motionless, with the log repeating "still waiting for the Pokémon on Nearby" every 10 seconds.
- The wait is now bounded. When the time is spent the app releases the Feed lock, states the reason in the log, and hands the cycle back to Nearby + AutoWalk.
- This is not the Go Plus path: giving up on one spawn does **not** disable the Feed source for the run, and the next dry spell may use the Feed again as normal.

### A Feed wait setting, revealed when the Feed is enabled

- Added **Wait for the Feed's Pokémon on Nearby (s, 0 = forever)** to the catching group, defaulting to 45 seconds.
- It appears only once **Nearby hết Pokémon: lấy 1 con từ Feed** is ticked, the same way the hold length appears only once PokéStop spinning is enabled — a control that does nothing should not be put in front of the user.
- Set it to 0 to keep the previous wait-forever behaviour.
- The app's only existing "wait for Pokémon on Nearby" control was wired to Shundo mode alone, so catching mode had no way to bound this wait at all.

### Verification

- **206 tests passing**, no failures.
- New tests cover the wait ending at its deadline and releasing the lock without consuming another Feed entry, the Feed source staying usable on the next cycle, 0 preserving the wait-forever behaviour, and the setting following its checkbox.
