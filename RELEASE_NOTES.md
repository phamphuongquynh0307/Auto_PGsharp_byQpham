# v1.2.2

## Tiếng Việt

### Không còn tự bấm khi đang chờ Pokémon load

- Trong vòng chờ spawn, bot kiểm tra popup trên từng frame để tự đóng các cảnh báo thật.
- Sau lượt dò nút X an toàn ở ngưỡng `0.82`, code cũ còn lặp lại một lượt ở ngưỡng thấp `0.70`. Bản đồ hoặc Pokémon chuyển động đôi lúc khớp nhầm lượt thứ hai này, khiến bot bấm dù màn hình không có popup.
- Đã xóa hoàn toàn lượt dò X ngưỡng thấp trong cả chế độ bắt thường và Shundo.
- Nút X thật vẫn được nhận bằng một lượt dò duy nhất ở ngưỡng `0.82`, gồm cả cách dò riêng phần glyph cho popup huy chương.

### Kiểm chứng

- Ảnh map trong báo cáo lỗi có điểm khớp X giả `0.666`; bản mới từ chối và trả về `popup=False`, `taps=[]`.
- Popup huy chương thật từng ghi nhận điểm khớp khoảng `0.93`, vẫn cao hơn ngưỡng mới và đóng bình thường.
- 89 bài test đạt; 7 bài giao diện được bỏ qua trong môi trường không có display.
- Đã build thành công bản EXE Windows.

---

## English

### No more unexplained taps while waiting for a Pokémon to load

- While waiting for a spawn, the bot checks every frame so it can dismiss genuine blocking popups.
- After the safe close-X search at `0.82`, the old code repeated the same search at the generic `0.70` threshold. Moving map art or Pokémon could occasionally cross that second threshold and trigger a tap when no popup existed.
- The low-confidence X pass has been removed completely from both Catch and Shundo modes.
- Real close buttons still use one `0.82` search, including the glyph-only fallback required by medal popups.

### Verification

- The reported map screenshot scores `0.666` against the false X match; the fixed build rejects it with `popup=False` and `taps=[]`.
- A real medal close X previously measured about `0.93`, so it remains safely detectable.
- 89 tests pass; 7 display-dependent GUI tests are skipped in the headless environment.
- The Windows executable builds successfully.
