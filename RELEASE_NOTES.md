# v1.4.7

## Tiếng Việt

### Wireless Debugging ổn định hơn

- Chờ ADB xác nhận transport thật sự ở trạng thái `device` trước khi báo kết nối thành công; không còn vòng lặp “tự kết nối lại Wi-Fi” dù điện thoại đã online.
- Tuần tự hóa các lệnh `adb connect`, chấp nhận thông báo thành công từ cả stdout/stderr và thử lại ngắn khi transport còn `offline`.
- Tự thử lại mDNS trong thời gian giới hạn để bắt đúng cổng TLS mới khi Android vừa bật Wireless Debugging hoặc đổi cổng.
- Sau khi kết nối thành công, danh sách thiết bị và trạng thái GUI được cập nhật mà không tự khởi động thêm một reconnect cạnh tranh.

### Discord Coord Collector v0.3.3

- Chuyển bridge coord sang cổng riêng `127.0.0.1:8766`, hoàn toàn tách khỏi cổng ADB/Wireless Debugging đang xoay của điện thoại.
- Popup hiển thị rõ phiên bản extension, trạng thái kết nối và endpoint đang dùng.
- Extension tự chèn lại bộ quét vào tab Discord đã mở trước khi extension được reload; không còn đứng ở “Đang chờ link mới” chỉ vì content script cũ chưa được nạp lại.
- Reset session tạm khi nâng phiên bản và cải thiện đọc tọa độ từ input, text, thuộc tính `data-*` hoặc tham số URL của Pokedex100.
- Gói cài mới `discord-coord-collector-v0.3.3.zip` được đính kèm trực tiếp trong release.

### Kiểm chứng

- **238 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test không có desktop Tk.
- Kiểm tra cú pháp toàn bộ JavaScript của extension và xác nhận manifest v0.3.3 chỉ dùng bridge `127.0.0.1:8766`.
- Xác nhận ADB thật nhận thiết bị Wireless Debugging ở trạng thái `device` sau kết nối.

---

## English

### More reliable Wireless Debugging

- Waits for ADB to report the transport as an actual `device` before declaring success, preventing endless Wi-Fi reconnect loops while the phone is already online.
- Serializes `adb connect` operations, accepts success output from stdout or stderr, and briefly retries while the transport is still `offline`.
- Performs bounded mDNS retries to discover a newly advertised or rotated Android TLS port.
- Refreshes the device list and GUI state after a verified connection without launching a competing reconnect worker.

### Discord Coord Collector v0.3.3

- Moves the coordinate bridge to dedicated port `127.0.0.1:8766`, fully separate from the phone's rotating ADB/Wireless Debugging port.
- Shows the extension version, connection state, and active endpoint in the popup.
- Automatically injects the scanner into Discord tabs that were already open when the extension was reloaded, preventing a false permanent “waiting for new links” state.
- Resets transient session state on extension upgrades and reads coordinates from inputs, visible text, `data-*` attributes, or Pokedex100 URL parameters.
- Includes the new `discord-coord-collector-v0.3.3.zip` package in the release.

### Verification

- **238 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is available.
- All extension JavaScript files pass syntax validation, and the v0.3.3 manifest uses only the dedicated `127.0.0.1:8766` bridge.
- A live ADB check confirms the Wireless Debugging transport reaches the `device` state after connection.
