# v1.2.3

## Tiếng Việt

### Nhận đúng hết bóng trên giao diện mới

- Pokémon GO mới có thể ẩn biểu tượng bóng thay vì hiện `x0`; bot giờ nhận cả hai kiểu.
- Chỉ báo hết bóng khi encounter còn mở, bóng vắng 1,2 giây qua 3 frame và ảnh ADB mới vẫn xác nhận.

### Tự bật Go Plus khi hết bóng

- Auto bắt thường (có key) có tùy chọn **Hết bóng: khởi động Go Plus sau AutoWalk**.
- Bot thoát encounter, bật AutoWalk rồi tìm nút Go Plus đang tắt để quay PokéStop trong 10 phút.
- Dò bằng hình ảnh nên vẫn đúng khi icon đổi vị trí; Go Plus đang chạy sẽ không bị bấm tắt.
- Bắt nhanh không key và trường hợp tắt tùy chọn sẽ không chạm Go Plus.

### Kiểm chứng

- 100 bài test đạt; 7 bài GUI được bỏ qua trong môi trường không có display.
- Bộ dò tìm đúng nút Go Plus trên ảnh thật 1220×2712; EXE Windows build thành công.

---

## English

### Out-of-ball detection for the new UI

- New Pokémon GO builds may hide the entire ball selector instead of showing `x0`; both states are now supported.
- An empty bag is reported only while the encounter remains open, the ball is absent for at least 1.2 seconds across three frames, and a fresh ADB capture confirms it. This avoids false alerts from animations or smeared stream frames.

### Start Go Plus automatically when balls run out

- Normal keyed catching now has an **Out of balls: start Go Plus after AutoWalk** setting.
- The bot leaves the encounter, starts AutoWalk, then locates and taps a disconnected Go Plus button so PokéStops can be spun during the ten-minute refill pause.
- Visual detection follows the button when event icons move it vertically and deliberately ignores an already connected accessory.
- Quick/no-key catching and a disabled setting never touch Go Plus.
- An already-running AutoWalk row is recognized and left running instead of being tapped off.

### Verification

- 100 tests pass; 7 display-dependent GUI tests are skipped in the headless environment.
- The detector locates the real Go Plus button on a 1220×2712 device screenshot, and the Windows executable builds successfully.
