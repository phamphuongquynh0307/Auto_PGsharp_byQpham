# v1.2.1

## Tiếng Việt

### Không còn báo shiny khi vẫn đang ở bản đồ

- Frame H.264 realtime chỉ còn được xem là một ứng viên encounter.
- Trước khi tăng bộ đếm shiny, gửi Discord hoặc bấm Flee, bot phải chụp một ảnh ADB mới và xác nhận lại nút Berry.
- Bộ dò Berry giờ kiểm tra đúng dải vị trí sát đáy màn hình, vòng sáng bao quanh và đủ bốn góc. Pokémon đỏ/trắng hoặc vật thể trên bản đồ không còn bị nhận thành nút Berry.

### Mỗi Pokémon chỉ double-tap một lần

- Bot xác nhận map và ô Nearby đang có Pokémon rồi thực hiện đúng một thao tác double-tap.
- Nếu sau thời gian chờ vẫn ở map và PGSharp không hiện toast, bot kết luận ngay Pokémon không shiny rồi chuyển sang mục tiếp theo.
- Bỏ lần double-tap thử lại gây chậm và làm log liên tục báo “chưa có phản hồi”.

### Đóng popup huy chương đúng nút X

- Popup huy chương ưu tiên tìm nút X ở đáy trước các nút hành động màu xanh.
- Không còn nhận nhầm nút SHARE hoặc SAVE IMAGE thành nút xác nhận cảnh báo thời tiết.
- Có thêm cách dò riêng phần glyph X để hoạt động khi nền hoặc viền nút thay đổi giữa các phiên bản game.

### Bản EXE mở được đầy đủ giao diện

- Cấu hình PyInstaller tự trỏ tới dữ liệu Tcl/Tk đi kèm dự án.
- Sửa lỗi bản đóng gói dừng ngay khi mở với thông báo `No module named 'tkinter'`.

### Kiểm thử

- 89 bài test đạt; 7 bài giao diện được bỏ qua trong môi trường không có display.
- Đã kiểm tra trực tiếp các ảnh từng gây nhận nhầm popup và encounter.
- Bản EXE Windows đã được build và smoke-test thành công.

---

## English

### No more shiny alerts while still on the map

- A realtime H.264 frame is now treated only as an encounter candidate.
- Before incrementing the shiny count, sending a Discord alert, or tapping Flee, the bot takes a new independent ADB screenshot and confirms the Berry button again.
- Berry detection now validates the bottom UI band, the pale outer ring, and all four quadrants. Red/white Pokémon and map objects no longer qualify as the Berry control.

### Exactly one double-tap per Pokémon

- The bot confirms both the map and an occupied Nearby slot, then performs one double-tap gesture.
- If PGSharp remains on the map without showing its blocked toast, that single no-encounter result is final and the bot advances to the next feed item.
- The redundant retry and repeated “no answer” log message are removed from the normal flow.

### Medal popups close with the real X

- Medal popups look for their bottom close X before any green action button.
- SHARE and SAVE IMAGE can no longer be mistaken for the weather warning confirmation button.
- A glyph-only X fallback handles game versions that change the button background or border.

### Working packaged GUI

- The PyInstaller spec now locates the project's bundled Tcl/Tk runtime automatically.
- Fixes packaged builds failing at startup with `No module named 'tkinter'`.

### Verification

- 89 tests pass; 7 display-dependent GUI tests are skipped in the headless test environment.
- The exact screenshots that previously caused popup and encounter false positives were checked directly.
- The Windows executable was rebuilt and smoke-tested successfully.
