# v1.1.13

## Tiếng Việt

### Shundo không còn báo shiny giả

- Xác nhận encounter bằng **nút Berry ở góc dưới trái**, không còn dùng camera AR hoặc Poké Ball — hai tín hiệu từng bị lưu frame/hiệu ứng trên map làm báo shiny sai.
- Vị trí Berry được **tự tìm trên từng frame**, không lấy tọa độ căn tay. Vòng nhận diện luôn bám đúng tâm nút dù giao diện bị lệch.
- Hai lần double-tap không có phản hồi mới được tính là non-shiny im lặng; một lần timeout không còn làm bot bỏ Pokémon đang chờ để nhảy sang mục QuickSniper kế tiếp.

### Flee chắc chắn trở về map

- Sau shiny chưa đủ 100 IV, bot kiểm tra bằng ảnh ADB tươi thay vì frame stream có thể bị trễ.
- Nếu MuMu nuốt cú tap Flee, bot tự luân phiên **tap nút Flee và phím Android Back**, tối đa sáu lần.
- Chỉ tiếp tục QuickSniper sau **hai frame tươi liên tiếp không còn Berry**. Nếu đã ngoài map từ đầu, bot xác nhận thành công ngay thay vì báo lỗi.

### Feed trong chế độ Bắt không còn nhảy mất Pokémon

- Thêm tùy chọn **“Nearby hết Pokémon: lấy 1 con từ Feed”** trong nhóm Bắt; mặc định tắt.
- Khi bật, bot chỉ tap Feed đúng một lần sau khi Nearby được xác nhận trống, rồi khóa Feed trong lúc chờ map và Pokémon tải xong.
- Chỉ mở khóa mục Feed kế tiếp sau khi Pokémon đã xuất hiện trên Nearby và encounter đó được xử lý. Timeout tải map không còn khiến bot tap Feed lần hai và bỏ mất Pokémon đầu.
- AutoWalk không chen vào khi đang chờ một Pokémon đã lấy từ Feed.

### Kiểm thử

- Bổ sung 16 bài test cho nhận diện Berry, trả map/Flee, chặn double-tap, trạng thái QuickSniper và khóa hàng đợi Feed.

---

## English

### No more phantom shiny encounters

- Encounters are confirmed by the **bottom-left Berry button**, with AR-camera and Poké Ball signals removed from the decision path.
- The Berry button is **located dynamically on every frame** instead of using a manually calibrated coordinate, so the overlay follows the real button centre.
- A single unanswered double-tap no longer advances QuickSniper. A bounded second confirmed no-answer handles PGSharp builds that silently block non-shiny Pokémon.

### Flee reliably returns to the map

- Skipped shinies are verified with fresh ADB screenshots rather than potentially stale stream frames.
- If MuMu drops the Flee tap, the routine alternates between an independent Flee tap and Android Back, for up to six attempts.
- QuickSniper resumes only after **two consecutive fresh frames without the Berry button**. An already-open map is accepted immediately instead of raising a false failure.

### Catch-mode Feed no longer skips unloaded Pokémon

- Adds an opt-in **“When Nearby is empty: take 1 Pokémon from Feed”** setting under Catch; it is off by default.
- One Feed item is tapped only after Nearby is confirmed empty, then the Feed queue is locked while the map and Pokémon load.
- The next Feed item is unlocked only after that Pokémon appears on Nearby and its encounter is handled. A load timeout can no longer consume a second Feed entry.
- AutoWalk stays out of the way while a Feed Pokémon is pending.

### Tests

- Adds 16 tests covering Berry localisation, Flee/map confirmation, bounded double-taps, QuickSniper state, and the Catch Feed queue lock.
