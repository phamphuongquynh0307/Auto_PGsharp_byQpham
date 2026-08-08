# v1.3.1

## Tiếng Việt

### Tối ưu bắt Pokémon liên tục

- Bỏ UI dump nặng khỏi đường mở encounter. Tool giờ chỉ đọc stream hình ảnh và ném ngay ở frame đầu tiên thấy nút Berry, không chờ hết timeout.
- Luôn gửi một tap mở đầu rất ngắn trước double-tap Nearby. Ngay cả khi thiết lập là `0`, tool giữ sàn 0,12 giây để PGSharp không bỏ mất lần mở encounter đầu tiên.
- Timeout mở encounter trở thành trần an toàn cho màn chuyển trắng chậm; trường hợp bình thường vẫn đi tiếp ngay khi game sẵn sàng.
- Sau khi bắt xong, thời gian **chờ Nearby cập nhật** giờ là thời gian refresh thật. Tool xóa bằng chứng slot cũ, chỉ dùng frame chụp sau thời gian chờ để xác nhận con tiếp theo, tránh bấm lại dòng Pokémon vừa bị xóa rồi mất thêm 4 giây timeout.
- Mỗi Pokémon mới bắt đầu trên một phiên cảm ứng sạch. Tránh trạng thái pointer còn sót sau cú vuốt ném bóng qua Wi-Fi làm cú tap Nearby kế tiếp bị gửi nhưng PGSharp không nhận.
- Kết quả thực tế: loại bỏ nhịp xen kẽ “bắt thành công → tap hỏng → chờ 4 giây → thử lại”; khoảng con 1 đến con 2 giờ chủ yếu còn thời gian refresh 1 giây và animation thật của game.

### Sửa Shundo bị kẹt ở một Pokémon đã mất

- Khi stream thấy entry nhưng ảnh ADB nét tạm thời không thấy, tool giữ nguyên entry và nhìn lại thay vì tiêu tốn mục QuickSniper tiếp theo.
- Giới hạn việc nhìn lại: tối đa 15 lần, cách nhau 0,5 giây. Entry đã despawn được bỏ qua để thanh feed tiếp tục chạy, thay vì chụp ADB vô hạn.
- Nhật ký phân biệt rõ **đang nhìn lại** và **entry đã mất**; thời gian nhìn lại không còn bị tính nhầm là hoạt động, nên cảnh báo idle vẫn hoạt động đúng.

### Kiểm chứng

- 140 bài test đạt, không bài nào lỗi; 17 bài phụ thuộc môi trường được bỏ qua đúng điều kiện.
- Đã kiểm tra trực tiếp trên thiết bị 1220×2712 qua ADB Wi-Fi và đối chiếu timestamp tap → encounter → ném trong log.
- EXE Windows build thành công.

---

## English

### Smoother consecutive catches

- Removed the expensive UI hierarchy dump from the encounter-opening path. The routine now reads only the video stream and throws on the first frame where the Berry button is ready.
- A very short priming tap always precedes the Nearby double-tap. Even a configured value of `0` keeps a 120 ms floor so PGSharp does not drop the first encounter gesture.
- The encounter timeout is now only a safety ceiling for slow white transitions; normal openings continue immediately.
- **Wait for Nearby refresh** is now a real post-catch refresh period. Old slot evidence is discarded, and only a frame captured after that period may prime the next cycle. This prevents tapping the consumed row and then paying a four-second failed-open timeout.
- Every next Pokémon starts on a clean touch-control session, preventing a lost pointer-up after a Wi-Fi throw from silently swallowing the following Nearby tap.
- In practice this removes the alternating rhythm of “successful catch → dead tap → four-second timeout → retry”; the remaining gap is the configured one-second refresh plus the game's real animation time.

### Fixed Shundo getting stuck on a lost entry

- When the stream sees an entry but a crisp ADB capture temporarily does not, the same entry is rechecked instead of consuming the next QuickSniper item.
- Rechecks are bounded to 15 attempts at 0.5-second intervals. A genuinely despawned entry is released so the feed can advance instead of taking ADB captures forever.
- The log now distinguishes **rechecking** from a **lost entry**, and rechecking no longer counts as activity, so idle alerts remain accurate.

### Verification

- 140 tests pass with no failures; 17 environment-dependent tests are skipped under their expected conditions.
- Verified live on a 1220×2712 device over Wi-Fi ADB by comparing tap → encounter → throw timestamps in the diagnostic log.
- The Windows executable builds successfully.
