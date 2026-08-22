# v1.4.3

## Tiếng Việt

### Sửa lỗi bot tap nhầm thanh Feed thay vì thanh Nearby

- PGSharp dựng thanh Nearby và thanh Feeds từ cùng một widget, nên mọi mục ở cả hai thanh đều mang chung một mã `hl_sri_icon`. App đọc gộp cả hai thành một danh sách rồi lấy mục trên cùng — tức là lấy nhầm thanh nào đang treo cao hơn trên màn hình, và điều đó thay đổi liên tục.
- Hậu quả: toạ độ của thanh Feed ghi đè điểm căn chỉnh tay của người dùng cho cả phiên chạy, bot double-tap thanh Feed hết vòng này tới vòng khác trong khi thanh Nearby đang đầy Pokémon.
- Nay hai thanh được tách theo cột. Mốc `@` — thứ chỉ thanh Nearby mới có — là căn cứ xác định đâu là Nearby, kèm điểm căn chỉnh tay và cột đã nhận trong phiên làm phương án dự phòng. Khi không đủ căn cứ, app trả lời "không đọc được" và quay về nhận diện ảnh, thay vì đoán rồi teleport nhầm.
- Bỏ qua các mục bị cắt cụt ở đáy danh sách: tâm của chúng không phải tâm ô, tap vào là trúng viền thanh.

### Feed được ưu tiên trước AutoWalk

- Trước đây nhánh AutoWalk chạy trước và thoát luôn khỏi vòng lặp. Hàng AutoWalk gần như luôn ở trạng thái tạm dừng vào mỗi vòng khô, nên nguồn Feed thực tế không bao giờ được đọc dù người dùng đã bật.
- Khi bật **Nearby hết Pokémon: lấy 1 con từ Feed**, Feed được thử trước; AutoWalk lùi về làm phương án dự phòng cho lúc Feed rỗng, đang khoá chờ cú nhảy trước đó, hoặc bị chặn.
- Vẫn không teleport ngay ở lần đọc trống đầu tiên: một lần đọc trống thường là nhận diện rớt frame chứ không phải thanh rỗng thật.
- Tắt tuỳ chọn thì thứ tự chạy giữ nguyên hoàn toàn như cũ.

### Vòng chờ nhanh hơn khoảng một phần ba

- Khi cây giao diện PGSharp đã xác nhận thanh Nearby trống, app không chụp thêm ảnh nét để hỏi lại nữa. Ảnh không được quyền bác bỏ nguồn chuẩn đó, mà tốn khoảng 2,8 giây mỗi lần trên kết nối Wi-Fi.
- Ảnh nét chỉ còn được chụp khi dump thật sự không đọc được — trường hợp duy nhất mà nhận diện ảnh còn tiếng nói.
- Đo trên máy 1220x2712 qua Wi-Fi: một vòng khô giảm từ khoảng 9 giây xuống khoảng 6 giây.

### Log nói đúng lý do khi thanh Nearby trống

- Khi cảnh báo Go Plus chặn teleport, nguồn Feed bị tắt cho cả phiên chạy. Log cũ vẫn ghi "không thấy Pokémon trên thanh Nearby lẫn thanh feed", nghe như nhận diện hỏng và khiến người dùng đi tìm lỗi không có thật.
- Nay log ghi rõ Feed đã tắt vì teleport bị chặn do Go Plus đang kết nối, kèm hướng xử lý là ngắt Go Plus rồi chạy lại. Trường hợp người dùng chủ động tắt Feed cũng được ghi riêng.

### Kiểm chứng

- **201 test đạt**, không có lỗi.
- Bộ test mới bao phủ: tách hai thanh theo cột, chọn đúng cột Nearby theo mốc `@` và theo điểm căn chỉnh tay, phân biệt "thanh rỗng thật" với "không xác định được thanh nào", loại mục bị cắt cụt, và thứ tự ưu tiên Feed trước AutoWalk ở cả bốn trường hợp bật/tắt.

---

## English

### Fixed the bot tapping the Feed bar instead of the Nearby bar

- PGSharp builds its Nearby sidebar and its Feeds sidebar from the same widget, so every entry on both bars reports the same `hl_sri_icon` id. The app read them as one merged list and took the topmost entry — which is whichever bar happens to hang higher on screen, and that changes constantly.
- The consequence: a Feed coordinate overwrote the user's manual calibration for the whole run, and the bot double-tapped the Feed bar cycle after cycle while the Nearby bar sat full of Pokémon.
- The two bars are now separated by column. The `@` anchor — which only the Nearby bar has — is what names the Nearby column, with the calibrated point and the column already accepted this session as fallbacks. Without enough evidence the app answers "cannot read" and falls back to pixel detection rather than guessing and teleporting to the wrong place.
- List items scrolled half out of view are discarded: their centre is not a slot centre, and tapping one lands on the bar's rim.

### The Feed now gets first refusal, ahead of AutoWalk

- AutoWalk previously took the branch first and returned. A paused AutoWalk row is the normal state on a dry cycle, so the Feed source was never actually read even when the user had enabled it.
- With **Nearby hết Pokémon: lấy 1 con từ Feed** enabled, the Feed is tried first; AutoWalk becomes the fallback for when the Feed is empty, locked behind a jump already made, or blocked.
- The first empty read still never earns a teleport: one empty read is usually the sprite test dropping a frame rather than a genuinely empty bar.
- With the option off, the ordering is exactly what it always was.

### Dry cycles roughly a third faster

- Once the PGSharp view tree has confirmed the Nearby bar is empty, the app no longer spends a crisp capture re-asking. Pixels cannot overrule that source anyway, and the capture costs about 2.8 seconds over a Wi-Fi connection.
- The crisp capture is now reserved for a dump that genuinely could not be read — the one case where pixel detection still has a say.
- Measured on a 1220x2712 device over Wi-Fi: a dry cycle drops from about 9 seconds to about 6.

### Honest logging when the Nearby bar is empty

- When a Go Plus warning blocks a teleport, the Feed source is switched off for the rest of the run. The old log line still said "nothing on the Nearby bar or the feed", which reads as a broken detector and sends users hunting for a fault that is not there.
- The log now states that the Feed was disabled because Go Plus blocked the teleport, and that disconnecting Go Plus restores it. A Feed the user simply left switched off is reported separately.

### Verification

- **201 tests passing**, no failures.
- New tests cover splitting the two bars by column, picking the Nearby column from the `@` anchor and from the calibrated point, telling a genuinely empty bar apart from an unidentifiable one, discarding clipped list items, and the Feed-before-AutoWalk ordering across all four enabled/disabled cases.
