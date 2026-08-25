# v1.4.6

## Tiếng Việt

### Luồng bắt mượt hơn, không còn nhịp “không có Pokémon” giả

- Rút thời gian giữa tap mồi và double-tap từ 0,8 giây xuống 0,12 giây, vẫn giữ nhịp chạm tối thiểu để PGSharp nhận ổn định.
- Thay khoảng chờ cứng sau mỗi encounter bằng chờ thích nghi: app lưu dấu vân tay màu của slot vừa bắt, bắt đầu kiểm tra sau 0,25 giây và đi tiếp ngay khi Nearby đã đổi qua hai frame mới. Mức 1,2 giây nay chỉ là trần an toàn khi hai Pokémon liên tiếp giống nhau hoặc frame khó đọc.
- Các nhịp đang mở encounter hoặc đang thử lại cú tap được ghi nhận là công việc đang diễn ra, không còn bị log thành “không có Pokémon”, kích hoạt AutoWalk hay cảnh báo khô giả.
- Không thử lại từ một frame Nearby còn lưu trong hàng đợi video. App chờ hết cửa sổ chuyển cảnh rồi dùng một ảnh chụp trực tiếp làm phán quyết cuối, tránh double-tap vào map và mất thêm một timeout.

### Wireless Debugging dễ kết nối và tự hồi phục

- Thêm cửa sổ **Wireless Debug** ngay trong app: tự tìm thiết bị đã ghép đôi bằng mDNS, kết nối bằng IP:cổng, hoặc ghép đôi lần đầu bằng địa chỉ ghép đôi và mã 6 số.
- Kiểm tra chặt địa chỉ ADB IPv4/IPv6 và không lưu mã ghép đôi.
- Ưu tiên đúng điện thoại từng dùng, thử endpoint Wireless Debugging bảo mật và cổng 5555 dự phòng, đồng thời xử lý cổng TLS thay đổi sau khi điện thoại bật lại Wireless debugging.
- Nếu ADB Wi-Fi rớt giữa phiên, app dừng stream/control cũ, tự nối lại và tiếp tục chính routine đang chạy; bộ đếm, cooldown và trạng thái Feed không bị mất.

### Làm lại toàn bộ luồng hết Poké Ball

- Sửa đúng nguyên nhân trên giao diện game hiện tại: túi rỗng vẫn vẽ nút Poké Ball tròn ở góc phải, nên nút đó không còn được xem là bằng chứng còn bóng. Chỉ bóng thật đang nằm tại điểm ném mới cho phép quẹt.
- Khi không thấy bóng thật, app nhả mọi con trỏ Quick Catch bị giữ, chờ bóng trở lại tối đa theo cấu hình và xác nhận lần cuối bằng ảnh ADB không nén. Nhờ vậy bóng đang bị giữ/đảo vẫn hồi phục, còn túi rỗng không tạo các cú ném ảo.
- Khi xác nhận hết bóng, app thoát encounter bằng tap ADB độc lập, kiểm tra đã về map và dùng Android Back nếu cú tap đầu không ăn.
- Sau khi về map, app bật AutoWalk và thử Go Plus lại ở các nhịp sau cho đến khi thật sự bấm được nút đang ngắt kết nối. Detector không chạm nút Go Plus màu xanh nên không thể vô tình tắt một kết nối đang chạy.
- Hiển thị đúng số phút refill theo cấu hình, log tiến độ AutoWalk/Go Plus và thời gian còn lại. Ô thời gian refill luôn hiện trong chế độ bắt vì nó áp dụng cả khi không bật quay PokéStop trên màn hình.
- Mở rộng và tự di chuyển vùng nhận diện huy hiệu x0 cũ cho người dùng đang giữ calibration mặc định từ bản trước.

### Tối ưu nhận diện và chẩn đoán

- Chỉ chạy phép khớp mẫu x0 tương đối nặng sau khi detector độc lập xác nhận đang ở encounter; giảm khoảng 33 ms cho mỗi vòng quét Nearby thông thường trên máy thử.
- Giữ kết nối điều khiển scrcpy giữa các Pokémon và chỉ đóng khi reset con trỏ thất bại.
- Log phân biệt rõ cú tap bị từ chối, encounter đang chuyển cảnh, hết bóng, refill và ADB Wi-Fi đang reconnect.

### Kiểm chứng

- **234 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test không có desktop Tk.
- Trên log thật của máy 1220x2712, chờ Nearby thích nghi hoàn tất sau 0,28–0,33 giây ở các slot đổi nhanh thay vì luôn chờ 1,2 giây.
- Ảnh thật của encounter hết bóng trên cùng máy được detector mới trả về trạng thái empty, trong khi bản cũ ghi nhận nút góc phải là còn bóng và tạo hai cú ném ảo mỗi encounter.
- EXE Windows one-file đã được smoke-test sau khi build.

---

## English

### Smoother catching without false “no Pokémon” beats

- Reduced the primer-to-double-tap delay from 0.8 seconds to 0.12 seconds while retaining the minimum input beat PGSharp needs for reliable engagement.
- Replaced the fixed post-encounter sleep with an adaptive refresh wait. The app fingerprints the engaged slot, starts checking after 0.25 seconds, and proceeds as soon as two fresh frames show that Nearby changed. The 1.2-second value is now only a safety ceiling for identical consecutive species or unreadable frames.
- Encounter-opening and tap-retry cycles are classified as active work instead of being logged as “no Pokémon”, starting AutoWalk, or contributing to false dry-spell alerts.
- A queued stale Nearby frame can no longer trigger an early retry. The app consumes the transition budget and uses one direct capture as the final verdict, avoiding map double-taps and another full timeout.

### Easier Wireless Debugging with runtime recovery

- Added an in-app **Wireless Debug** window that can discover paired devices over mDNS, connect to an IP:port endpoint, or perform first-time pairing with the displayed pairing endpoint and six-digit code.
- Strictly validates IPv4/IPv6 ADB endpoints and never stores pairing codes.
- Prefers the previously used phone, supports the secure Wireless Debugging endpoint and the optional port 5555 fallback, and discovers rotated TLS ports after Wireless debugging is restarted.
- If Wi-Fi ADB drops during a run, the app tears down the stale stream/control channel, reconnects, and resumes the same routine without losing counters, cooldown state, or a pending Feed item.

### Rebuilt out-of-Poké-Ball flow

- Fixed the current game's actual empty-bag UI: it still draws the round Poké Ball selector at the lower right, so that button is no longer treated as inventory proof. Only a real throwable ball resting at the throw point permits a swipe.
- When the real ball is absent, the app releases stale Quick Catch pointers, waits for a held/rotated ball to return, and performs a final uncompressed ADB capture. A recoverable held ball remains safe while an empty bag no longer produces phantom throws.
- After confirming an empty bag, the app exits with an independent ADB tap, verifies that the map returned, and falls back to Android Back when needed.
- On the map it starts AutoWalk and safely retries Go Plus until the disconnected button is actually tapped. The detector never touches the connected green state, so retries cannot disable a running accessory.
- Refill messages use the configured duration, report AutoWalk/Go Plus progress, and expose the refill-duration setting in every catching configuration.
- Expanded the legacy x0 badge region and automatically migrates the unchanged old default calibration.

### Detection and diagnostics

- Runs the comparatively expensive x0 template only after an independent encounter detector succeeds, saving about 33 ms from each ordinary Nearby cycle on the test device.
- Keeps the scrcpy control channel warm between Pokémon and closes it only when pointer reset genuinely fails.
- Logs now distinguish rejected taps, encounter transitions, empty bags, refill progress, and Wireless ADB reconnection.

### Verification

- **234 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is available.
- On a live 1220x2712-device log, adaptive Nearby refresh completed in 0.28–0.33 seconds for quickly changing slots instead of always sleeping 1.2 seconds.
- A real empty-bag encounter frame from that device is classified as empty; the previous flow treated its persistent lower-right selector as inventory and generated two phantom throws per encounter.
- The Windows one-file EXE is smoke-tested after build.
