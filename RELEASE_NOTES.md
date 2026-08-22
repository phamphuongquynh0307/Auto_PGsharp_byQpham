# v1.4.5

## Tiếng Việt

### Sửa lỗi Feed không bao giờ được gọi khi AutoWalk đặt ở 1 vòng

- Nguồn Feed và AutoWalk dùng chung một biến đếm số vòng khô liên tiếp. AutoWalk đặt biến đó về 0 ngay khi nó chạy, nên với **Số vòng trống trước khi bấm AutoWalk = 1**, biến luôn bằng 0 đúng vào lúc Feed cần đọc.
- Feed kiểm tra `số vòng khô >= ngưỡng` trước khi làm bất cứ việc gì, nên điều kiện luôn sai và hàm xử lý Feed **chưa từng được gọi một lần nào**. Nhìn từ ngoài giống hệt lỗi nhận diện: bot đứng cạnh thanh Feed đầy Pokémon và không phản ứng, log không hề nói gì.
- Nay Feed có biến đếm riêng, chỉ về 0 khi thật sự bắt được Pokémon hoặc khi đang chờ cú nhảy Feed trước đó. AutoWalk giữ nguyên biến cũ và hành vi không đổi.
- Lỗi này chỉ xuất hiện khi đặt AutoWalk ở 1 vòng. Để 3 vòng thì Feed vẫn chạy, nên nó ẩn mình rất kỹ.

### Sửa bẫy khép kín khiến thanh Feed không bao giờ được tìm bằng ảnh nét

- Khung hình từ luồng video bị nén H.264 thường xuyên làm icon RSS và tay cầm của thanh Feed tụt dưới ngưỡng khớp mẫu. App có sẵn bước chụp ảnh nét để cứu, nhưng bước đó bị khoá sau điều kiện "đã từng thấy thanh Feed".
- Mà cờ "đã từng thấy" chỉ được bật khi khớp thành công trên chính khung hình luồng video. Trên máy mà khung hình luôn nhoè, đó là vòng lặp khép kín: thứ duy nhất chứng minh được thanh Feed tồn tại lại chính là thứ bị cấm chạy.
- Nay cho phép chụp một ảnh nét để khởi động, giới hạn 20 giây một lần để người bật Feed mà không mở thanh Feed không phải trả phí chụp mỗi vòng khô. Sau khi đã thấy thanh Feed một lần thì bước cứu này chạy lại bình thường mỗi vòng.

### Log nói rõ vì sao bỏ qua Feed

- Trước đây bốn tình huống hoàn toàn khác nhau đều in ra đúng một câu, nên không có cách nào biết bot đang vướng ở đâu.
- Nay tách riêng từng lý do: không tìm thấy thanh Feed trên màn hình, thanh Feed đang trống, vừa hiện Pokémon và đang chờ khung hình xác nhận, hoặc không thấy mốc `@` của thanh Nearby.

### Kiểm chứng

- **210 test đạt**, không có lỗi. Bộ test mới khoá đúng ca gây lỗi: AutoWalk đặt ở 1 vòng và vừa đặt lại biến đếm, Feed vẫn phải tới lượt.
- Chạy thật trên máy 1220x2712: tap Feed tại `(141, 385)`, Pokémon xuất hiện trên thanh Nearby sau **35,1 giây** và chuyển sang bắt bình thường.
- Lưu ý về cài đặt: 35 giây đã khá sát mặc định 45 giây của ô **Chờ Pokémon từ Feed hiện trên Nearby**. Nếu mạng chậm hoặc điểm nhảy xa, nên nâng ô này lên.

---

## English

### Fixed the Feed never being called when AutoWalk is set to 1 idle cycle

- The Feed source and AutoWalk shared one counter of consecutive dry cycles. AutoWalk zeroes that counter the moment it fires, so with **idle cycles before AutoWalk = 1** the counter was always 0 at exactly the point the Feed read it.
- The Feed checks `dry cycles >= threshold` before doing anything, so the condition never held and the Feed routine **was never called once**. From the outside this looked exactly like a detection failure: the bot standing beside a Feed bar full of Pokémon, doing nothing, with the log saying nothing at all.
- The Feed now has its own counter, zeroed only when a Pokémon is actually caught or while waiting on a Feed jump already made. AutoWalk keeps the original counter and its behaviour is unchanged.
- The bug only appeared with AutoWalk set to 1 cycle. At 3 the Feed still worked, which is what kept it so well hidden.

### Fixed the closed loop that stopped the Feed bar ever being found on a crisp capture

- H.264 compression on the video stream routinely drops the Feed bar's small RSS icon and drag handle below the match threshold. The app already had a crisp-capture fallback for this, but it was gated behind "the Feed bar has been seen before".
- That flag is only set when a match succeeds on a stream frame in the first place. On a device where stream frames never match, this is a closed loop: the one capture able to prove the bar exists is the one thing the gate forbids.
- A crisp capture may now bootstrap that flag, rate-limited to once every 20 seconds so a user who enables the Feed without opening the Feed bar does not buy a capture on every dry cycle. Once the bar has been seen, the fallback runs every cycle as before.

### The log now says why the Feed was skipped

- Four genuinely different situations previously printed one identical line, leaving no way to tell where the bot was stuck.
- Each now reports its own reason: the Feed bar could not be found on screen, the Feed bar is empty, a Pokémon has just appeared and one more frame is needed to confirm it, or the Nearby bar's `@` anchor is not in view.

### Verification

- **210 tests passing**, no failures. A new test pins the exact failing case: AutoWalk set to 1 cycle and having just reset its counter, the Feed must still get its turn.
- Confirmed on a live 1220x2712 device: Feed tapped at `(141, 385)`, the Pokémon reached the Nearby bar after **35.1 seconds**, and catching proceeded normally.
- A note on settings: 35 seconds is close to the 45-second default of **Wait for the Feed's Pokémon on Nearby**. Raise it if your connection is slow or the jumps are long.
