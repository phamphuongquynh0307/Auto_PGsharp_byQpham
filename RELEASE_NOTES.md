# v1.4.2

## Tiếng Việt

### Nearby nhanh và chính xác hơn

- Không còn phụ thuộc cứng vào một tọa độ Nearby: khi đọc được giao diện PGSharp, app tự lấy tâm Pokémon đầu tiên và ưu tiên vị trí thật đó trong suốt phiên chạy.
- Nếu thao tác chạm bị PGSharp bỏ qua nhưng thanh Nearby vẫn còn nguyên, app xác nhận bằng hai frame mới rồi thử lại sớm thay vì chờ hết timeout encounter.
- Giữ kết nối điều khiển scrcpy giữa các Pokémon và gửi lệnh nhả con trỏ dự phòng; chỉ kết nối lại khi socket thật sự lỗi, giúp giảm khoảng chờ 1–5 giây trên Wi-Fi.

### Popup ổn định trên nhiều máy

- Tách tỷ lệ hiển thị của lớp PGSharp, Android và giao diện Pokémon GO để popup không còn dùng nhầm scale từ máy gốc.
- Cải thiện xử lý các popup huy chương, thông báo thời tiết, nút Check/Maybe Later, màn hình Pokémon Caught và đĩa PokéStop.
- Khi đã xác nhận đúng loại popup nhưng hình nút X thay đổi theo phiên bản game, app dùng điểm đóng đã căn hoặc vị trí hình học an toàn thay vì đứng chờ vô hạn.

### Chấm shiny theo bộ IV tùy chọn

- Thêm ba mục tiêu IV riêng cho Công/Thủ/HP, mỗi cột từ 0–15, dùng chung cho chế độ Feed và Discord Coord; `15/15/15` vẫn là Shundo truyền thống.
- Đọc trực tiếp ba cột IV từ cây giao diện PGSharp, phân biệt được các Pokémon có cùng phần trăm nhưng khác bộ chỉ số.
- Nếu gặp shiny nhưng không đọc chắc được IV, app giữ encounter và tạm dừng thay vì bỏ nhầm Pokémon.
- Log và thông báo Discord ghi cả IV thực tế lẫn IV mục tiêu để dễ kiểm tra.

### Hướng dẫn trong app và đóng gói Windows

- Viết lại tab **Hướng dẫn** thành các mục riêng cho cài Windows, Android/USB, PGSharp, bắt Pokémon, chấm shiny từ Feed, Discord Coord, quay PokéStop và báo lỗi.
- Thêm đủ 15 ảnh minh họa vào hướng dẫn và nhúng trực tiếp trong EXE; ảnh cùng tên trong `guide_images` cạnh EXE vẫn có thể ghi đè mà không cần build lại.
- Bổ sung tài liệu tiếng Việt `HUONG_DAN.md` và liên kết từ README.
- Sửa khởi động Tcl/Tk trên các máy Windows chặn việc nạp script giao diện từ `%TEMP%`.

### Kiểm chứng

- **184 test đạt**, không có lỗi; 17 test giao diện được bỏ qua đúng điều kiện khi môi trường test không có desktop Tk.
- Bộ test mới bao phủ retry Nearby, tọa độ Nearby động, scale popup, tái sử dụng kết nối điều khiển, đọc chính xác ba cột IV và nội dung hướng dẫn.
- EXE Windows one-file chứa đủ 15 ảnh hướng dẫn và được kiểm tra khởi động sau khi build.

---

## English

### Faster and more accurate Nearby handling

- Nearby is no longer tied to one fixed coordinate. When the PGSharp hierarchy is available, the app remembers the live centre of the first Pokémon and prefers it for the rest of the run.
- If PGSharp ignores a tap while the occupied Nearby row remains visible, two fresh frames confirm the miss and trigger an early retry instead of waiting for the full encounter timeout.
- The scrcpy control connection stays warm between Pokémon. Duplicate pointer-up events clear stale touch state, with reconnection reserved for a genuinely broken socket, reducing the 1–5 second Wi-Fi delay.

### Popups across different devices

- PGSharp overlays, Android dialogs and Pokémon GO game UI now use separate render scales instead of inheriting one authoring-device scale.
- Improved handling for medal, weather, Check/Maybe Later, Pokémon Caught and PokéStop-disc screens.
- Once a popup is structurally confirmed, calibrated or geometry-based close points safely handle versions whose X artwork no longer matches the template.

### Configurable exact-IV shiny checks

- Added separate 0–15 Attack, Defence and HP targets shared by Feed and Discord-coordinate modes; `15/15/15` remains the traditional Shundo target.
- Reads the three IV columns directly from the PGSharp UI hierarchy, distinguishing Pokémon with the same percentage but different stat spreads.
- If a shiny's IV cannot be read confidently, the app keeps the encounter and pauses rather than fleeing the wrong Pokémon.
- Logs and Discord notifications include both actual and target IVs.

### In-app guide and Windows packaging

- Rebuilt the **Guide** tab into focused pages for Windows, Android/USB, PGSharp, catching, Feed shiny checks, Discord coordinates, PokéStop spinning and bug reports.
- Added and bundled all 15 guide images in the EXE. Matching files in a `guide_images` folder beside the EXE can still override them without rebuilding.
- Added the detailed Vietnamese `HUONG_DAN.md` and linked it from the README.
- Fixed Tcl/Tk startup on Windows configurations that block GUI scripts extracted under `%TEMP%`.

### Verification

- **184 tests pass** with no failures; 17 GUI tests are skipped as expected when the test environment has no Tk desktop.
- New coverage includes Nearby retries, live Nearby coordinates, popup scaling, control-channel reuse, exact three-column IV parsing and guide content.
- The Windows one-file EXE contains all 15 guide images and is smoke-tested after build.
