# PoGo Monitor v0.3.6 cho Edge / Chrome

Popup nhỏ tự Search PoGo Coordinates, lọc Top IV và Top PvPoke, báo trên web và Discord. Mỗi kết quả gửi hai tin Discord riêng: một thẻ thông tin Pokémon và một tin văn bản chỉ có tọa độ. Trên điện thoại, nhấn giữ tin → Sao chép văn bản để lấy đúng tọa độ.

Bảng trạng thái ở góc trái dưới trang cho biết đang chạy, đang tìm, đã dừng, chạy ở tab khác hoặc mất kết nối. Đóng popup vẫn thấy lần tìm gần nhất và đếm ngược lần tiếp. Bấm tiêu đề bảng để thu gọn.

## Cài lần đầu

1. Tải file `pogocoordinates-monitor-v0.3.6.zip` và giải nén vào thư mục cố định.
2. Edge: mở `edge://extensions` → bật **Developer mode** → **Load unpacked** → chọn thư mục có `manifest.json`. Chrome dùng `chrome://extensions`.
3. Bấm biểu tượng extension → **Mở web**. Đăng nhập PoGo Coordinates trong cùng profile trình duyệt.
4. Chọn Pokémon, Stats/PvP và bộ lọc **trên website**.
5. Mở popup → **Cài đặt**: mã bạn bè 12 số, chu kỳ (tối thiểu 30 giây), thời gian chạy (0 = tới khi dừng), ngưỡng Top IV / Top PvPoke. Nếu dùng Discord, nhập webhook của kênh bạn muốn nhận.
6. Lưu và bấm **Chạy tự động**. Giữ Edge và tab PoGo mở; tab có thể chạy nền và popup có thể đóng.

## Cập nhật / chạy thử lại

- Cập nhật: chép đè vào thư mục extension cũ rồi bấm **Tải lại**, sau đó **F5 trang PoGo**. Popup phải hiện **v0.3.6**. Không gỡ để giữ cấu hình và lịch sử.
- Đổi bộ lọc: Dừng, sửa trên web, rồi Chạy lại.
- Chạy thử lại: tab **Thông báo** → **Xóa lịch sử & thử lại** → **Tìm ngay**. Các kết quả vẫn phải đạt bộ lọc và ngưỡng PvP.
- Nếu không có tin mới, đọc dòng trạng thái: không đạt hạng, đã báo, hết hạn hoặc lỗi tọa độ.

## Stats và PvP

Stats báo kết quả mới đạt bộ lọc web, không có hạng. PvP kiểm tra thêm hạng IV và hạng loài PvPoke; hạng 1 tốt nhất, mốc 1500 hoặc 2500. Mặc định cả hai ngưỡng phải đạt trên cùng loài/tiến hóa. Dữ liệu đầy đủ xem trong tab Thông báo.

Mỗi người dùng phiên đăng nhập, mã bạn bè và webhook riêng; file ZIP không chứa tài khoản hay webhook của tác giả. Shiny cần thêm mã bạn bè vào hồ sơ PoGo Coordinates. Quyền VIP và hạn mức trên web vẫn áp dụng.

Cột PvPoke nằm cạnh CP / LVL / IV trên kết quả Search ở chế độ PvP. Hạng theo Great 1500 / Ultra 2500; khi xét tiến hóa, hiện loài có hạng tốt nhất. Dấu — là chưa có hạng. Đây là hạng loài, không phải hạng IV.
