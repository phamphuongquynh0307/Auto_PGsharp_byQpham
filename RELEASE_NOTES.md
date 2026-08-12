# v1.4.1

## Tiếng Việt

### Discord Coord Collector v0.3.1

- Chỉ lấy trước một coord mới nhất thay vì giữ bộ đệm ba coord, tránh coord nằm chờ quá lâu khiến Pokémon chạy mất.
- Sau khi app chấm xong Pokémon hiện tại, extension mới lấy coord mới nhất tiếp theo từ Discord.

### Shundo từ Discord Coord

- Thêm chế độ **Shundo từ Discord Coord**: app nhận tọa độ tại `127.0.0.1:8765`, nhập coord vào PGSharp bằng Android key event an toàn và teleport tuần tự.
- Mỗi coord được giữ cho tới khi Pokémon hiện tại có kết quả xác nhận. App chỉ báo extension lấy thêm đúng một coord sau khi chấm xong, tránh bỏ spawn chậm hoặc tiêu tốn nhầm coord tiếp theo.
- Thêm nhóm căn chỉnh riêng cho dòng Teleport, ô Coordinates và nút OK; hỗ trợ tự co giãn theo màn hình như các chế độ khác.
- Tăng độ chắc chắn khi nhận diện Pokémon trong sidebar: loại map/gyms tối phía sau thanh trong suốt nhưng vẫn giữ sprite Pokémon sáng phía trước.

### Discord Coord Collector v0.3.0

- Extension Edge theo dõi đúng tab Discord Web đang active, lấy link **Click for Coords** từ Pokedex100 và tự đóng tab tạm sau khi đọc xong.
- Bộ đệm ban đầu lấy tối đa ba coord; sau đó app desktop hoàn tất một Pokémon thì extension mới cấp thêm một coord.
- Cho phép dán tối đa 2.000 `latitude,longitude` từ clipboard, tự bỏ coord sai/trùng và gắn chú thích **Từ Discord Pokedex100**.
- Thêm nút **Xóa dữ liệu cũ**, dọn lịch sử extension, hàng chờ và hàng coord trong app desktop.
- Extension được đặt trực tiếp trong repository tại `downloads/discord-coord-collector-v0.3.0.zip`, kèm link tải nhanh trong README.

### Kiểm chứng

- Kiểm tra cú pháp toàn bộ JavaScript của extension và mô phỏng luồng nhập hàng loạt → gửi tool → xóa dữ liệu.
- **164 test đạt**, không có lỗi; 17 test phụ thuộc môi trường được bỏ qua đúng điều kiện. Bộ test bao phủ bridge, hàng coord, nhập phím Android, luồng Shundo và nhận diện sidebar.
- EXE Windows build thành công; xác nhận `avc.coord_source` và `avc.coord_shundo` có trong gói PyInstaller.

---

## English

### Discord Coord Collector v0.3.1

- Prefetches only the first/newest coordinate instead of holding a three-coordinate buffer, reducing stale spawns.
- After the app finishes checking the current Pokémon, the extension fetches the next newest coordinate from Discord.

### Shundo from Discord coords

- Added **Shundo from Discord coords** mode. The app receives coordinates on `127.0.0.1:8765`, enters them into PGSharp using safe Android key events, and teleports sequentially.
- A coordinate remains active until the current Pokémon has a confirmed result. The app grants exactly one new-coordinate credit after a completed check, preventing slow spawns from consuming the next coordinate.
- Added dedicated calibration points for the Teleport row, Coordinates input, and OK button, with the same screen scaling support as other modes.
- Strengthened sidebar Pokémon detection by rejecting dark map/gym detail behind the translucent bar while retaining bright foreground sprites.

### Discord Coord Collector v0.3.0

- The Edge extension follows only the active Discord Web tab, extracts Pokedex100 **Click for Coords** links, and closes temporary tabs after processing.
- It prefetches up to three coordinates, then requests one more only after the desktop app completes a Pokémon check.
- It can paste up to 2,000 `latitude,longitude` entries from the clipboard, skips invalid/duplicate values, and labels them **From Discord Pokedex100**.
- Added **Clear old data** to remove extension history, pending work, and the desktop app's coordinate queue.
- The extension archive is stored directly in the repository at `downloads/discord-coord-collector-v0.3.0.zip`, with a direct download link in the README.

### Verification

- Checked all extension JavaScript and simulated the bulk import → tool delivery → clear-data flow.
- **164 tests pass** with no failures; 17 environment-dependent tests are skipped as expected. Coverage includes the HTTP bridge, coordinate queue, Android text input, Shundo flow, and sidebar detection.
- The Windows EXE builds successfully, with `avc.coord_source` and `avc.coord_shundo` verified inside the PyInstaller archive.
