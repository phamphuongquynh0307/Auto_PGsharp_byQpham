# v1.4.9

## Tiếng Việt

### Chạy lâu ổn định hơn

- Mỗi lần Android `screenrecord` tự khởi động lại, app giờ đóng hẳn bộ giải mã video, pipe và
  process cũ thay vì để thread/handle tích tụ theo thời gian.
- Giới hạn bộ giải mã còn 2 thread để dành CPU cho nhận dạng màn hình; các phiên chạy nhiều giờ
  không còn chậm dần sau hàng chục lần stream khởi động lại.

### Nhận dạng nhanh hơn mà vẫn giữ đường lui an toàn

- Tìm template trong một vùng nhỏ giờ crop ảnh trước khi đổi sang grayscale và tái sử dụng trực
  tiếp score map, giảm chuyển đổi pixel và cấp phát bộ nhớ không cần thiết.
- Bộ dò nút đóng vẫn thử scale đã căn ở mọi chu kỳ, còn lượt quét rộng 17 scale được giới hạn một
  lần mỗi giây. Popup lạ vẫn được bắt, nhưng map bình thường không còn trả thêm khoảng 90 ms ở
  từng vòng lặp.

### Có số liệu thật để sửa lệch trên máy khác

- Khi app đã đọc overlay PGSharp vì công việc sẵn có, app âm thầm đối chiếu tọa độ do ảnh nhận ra
  với tọa độ thật trong view Android cho Nearby, AutoWalk và nút CANCEL.
- Kết quả nằm trong `doi-chieu.log` và tự đi kèm gói **Xuất báo cáo lỗi**. Phần đo không thay đổi
  bất kỳ tọa độ bấm hay cache nào của phiên chạy, không tự chụp ảnh chậm khi stream mất, và tự
  dừng sau khi đủ mẫu để không tốn CPU mãi.

### Kiểm chứng

- **272 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.

---

## English

### More stable long-running sessions

- Every Android `screenrecord` relaunch now closes the previous video decoder, pipe, and process
  instead of accumulating threads and handles over time.
- The decoder is capped at two threads so screen recognition keeps the CPU it needs, preventing
  multi-hour sessions from slowing down after repeated stream restarts.

### Faster recognition with the safety net intact

- Region-based template searches now crop before grayscale conversion and reuse the score map
  directly, avoiding unnecessary full-frame work and memory allocations.
- Calibrated popup-close scales are still checked every cycle, while the expensive 17-scale safety
  sweep is limited to once per second. Unexpected popup sizes remain detectable without adding
  roughly 90 ms to every ordinary map pass.

### Real cross-device alignment evidence

- Whenever the app already reads the PGSharp overlay, it passively compares image-derived
  coordinates with Android view coordinates for Nearby, AutoWalk, and CANCEL controls.
- Results are stored in `doi-chieu.log` and included in **Export error report** bundles. Measurement
  never changes tap coordinates or detector caches, never buys a slow one-shot screenshot when
  the stream is unavailable, and stops after enough samples have been collected.

### Verification

- **272 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is
  available.

---

# v1.4.8

## Tiếng Việt

### Nhận dạng đa máy

- Điểm ném tự bám tâm quả bóng thật theo cấu trúc hub sáng + vòng đen, không còn phụ thuộc hoàn
  toàn vào tọa độ của máy mẫu; căn tay vẫn là override cuối cùng.
- AutoWalk dùng view Android của PGSharp khi template icon không khớp và nhận cả hai nhãn
  `AutoWalk`/`AW(Paused)`; vị trí và trạng thái hàng vì vậy không phụ thuộc DPI/font/icon theme.
- Hộp thoại Android phải được view tree xác nhận đúng nút `CANCEL/HỦY` trước khi bấm trên cấu hình
  mặc định, ngăn màn thông tin Pokémon bị nhầm thành hộp hai nút.
- Xem bot nhìn hiển thị tâm bóng/điểm ném thật và trạng thái AutoWalk đọc được bằng ảnh.
- Bổ sung profile emulator chuẩn tùy chọn `1220 × 2712 @ 480 dpi`; điện thoại thật không bị yêu cầu
  đổi độ phân giải.

### Bỏ hẳn việc tự bật Go Plus

- Pokémon GO thêm một nút tròn nữa vào dải icon mép phải có đúng hình dạng mà bộ dò Go Plus tìm
  (nắp đỏ nửa trên, tâm tối). Khi hết bóng, app dò trúng nút mới đó rồi **bấm vào** — tức là tự
  bật Go Plus lên. Go Plus bật thì PGSharp chặn mọi teleport, mà teleport là thứ Shundo và nguồn
  Feed sống bằng nó. App đang tự khoá chính mình, và Shundo sau đó dừng với thông báo
  *"Go Plus đang kết nối"*.
- Không có ngưỡng nào chữa được chuyện này: nút kia **trông thật sự giống** nút đang tìm. Nên bỏ
  hẳn phần tự bật Go Plus — cả ô tick *"Hết bóng: khởi động Go Plus sau AutoWalk"*, bộ dò và
  đường gọi nó.
- Nạp bóng giờ đi qua **quay PokéStop**, vốn đã có sẵn, không cần PGSharp key, và chỉ bấm vào thứ
  nó đã nhận diện chắc chắn là stop.
- App vẫn bấm CANCEL nếu gặp cảnh báo teleport thật của Go Plus — chỗ đó là an toàn tài khoản,
  không đụng tới.

### Shundo không còn dừng oan vì một hộp thoại lạ

- Trước đây bất kỳ hộp thoại hai nút nào ở giữa màn hình, có một nút CANCEL, cũng đủ để Shundo
  kết luận "Go Plus đang kết nối" và **dừng hẳn run**. Chứng cứ đó quá yếu so với kết luận: rất
  nhiều hộp thoại Android trông y như vậy.
- Giờ app vẫn bấm CANCEL (không bao giờ xác nhận một teleport đang bị cảnh báo) nhưng **chạy
  tiếp**. Chỉ đúng ảnh mẫu cảnh báo Go Plus, khớp trong vùng riêng của nó, mới được phép dừng run.

### Bot tự thoát khi kẹt

- Popup nào app chưa biết mặt thì trước đây bot đứng im đến khi có người phát hiện. Giờ khi màn
  hình không đọc được liên tục quá 12 giây, bot **tự bấm phím Back** — đúng thứ người thật làm.
  Không cần ảnh mẫu, không cần toạ độ, không phụ thuộc ngôn ngữ hay bản game, và người dùng
  không phải thao tác gì. Tối đa 8 giây một lần.
- Hai rào chắn cứng: **không bao giờ** bấm Back khi đang gặp Pokémon (mất con đó), và không bấm
  khi thanh Nearby đang hiện (đang ở map). Nếu lỡ rơi vào hộp "Thoát Pokémon GO?" thì đó là
  hộp thoại Android thật, phần xử lý sẵn có đã biết bấm CANCEL.
- Mỗi lần kẹt, app lưu một ảnh màn hình vào thư mục `stuck/` cạnh EXE. Popup gây kẹt thường xuất
  hiện lúc không ai ngồi canh; có ảnh thì báo lỗi được sau, không phải bắt đúng lúc.
- Tắt được ở Cài đặt (mục nâng cao) nếu không muốn app bấm Back.

### Sửa lỗi đọc nhầm hàng AutoWalk

- Khi cả hai icon hàng AutoWalk (`⊘` đang dừng và glyph đang chạy) cùng vượt ngưỡng, app giờ chọn
  cái **khớp cao hơn** thay vì cái được thử trước. Đo trên máy 1220×2712 thật: ảnh `⊘` ăn 0.72 ở một
  hàng menu bên cạnh trong khi hàng AutoWalk thật ăn 0.97 ở vị trí thấp hơn 100px — app đọc walk
  đang chạy thành đang dừng, bấm nhầm hàng ở mỗi chu kỳ Nearby trống, rồi chờ một icon `⊘` vốn
  chưa từng ở đó biến mất.

### Kiểm chứng

- **255 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.

---

## English

### Better multi-device recognition

- Throwing now follows the detected center of the actual ball instead of relying entirely on
  coordinates captured from one device; manual alignment remains the final override.
- AutoWalk falls back to PGSharp's Android view data when icon templates differ and recognizes
  both `AutoWalk` and `AW(Paused)` labels across DPI, font, and icon-theme variations.
- Native Android dialogs must expose an exact `CANCEL/HỦY` button in the view tree before the
  default geometry-based handler taps them, reducing false positives on Pokémon detail screens.
- The vision preview now shows the detected ball center, throw point, and AutoWalk state.
- Documents an optional `1220 × 2712 @ 480 dpi` emulator support profile without requiring real
  phones to change their display configuration.

### Removed automatic Go Plus startup

- Pokémon GO added another round side control that genuinely resembles the disconnected Go Plus
  button. The old detector could tap that control, start Go Plus, and then block the teleports used
  by Shundo and Feed modes.
- Automatic Go Plus startup and its setting have therefore been removed. Out-of-ball recovery now
  relies on the existing PokéStop spinning path, which does not require a PGSharp key.
- Genuine Go Plus teleport warnings are still cancelled for account safety.

### Safer Shundo dialog handling

- A generic two-button dialog with a CANCEL button no longer permanently stops a Shundo run.
  The app cancels the dialog and continues; only the dedicated Go Plus warning template can mark
  teleporting as blocked.

### Automatic recovery from unknown screens

- After a screen remains unrecognized for 12 seconds, the bot sends a rate-limited Android Back
  command to dismiss unknown popups without depending on language, templates, or coordinates.
- Hard safety guards prevent Back from being pressed during a Pokémon encounter or on the map.
- Each recovery attempt saves a screenshot under `stuck/` for later diagnosis, and the watchdog
  can be disabled in advanced settings.

### Correct AutoWalk row selection

- When both running and paused icon templates clear their thresholds, the stronger match now wins,
  preventing the bot from tapping a neighboring row because a weaker paused-icon match happened
  to be checked first.

### Verification

- **255 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is
  available.

---

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
