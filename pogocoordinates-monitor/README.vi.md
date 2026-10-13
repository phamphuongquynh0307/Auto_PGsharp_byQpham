# PoGo Monitor v0.3.3

Popup nhỏ cho Edge/Chrome. Bạn chọn bộ lọc trên PoGo Coordinates; extension tự bấm Search, kiểm tra hạng PvP và báo trên web / Discord.

## Cách dùng

1. Bấm biểu tượng extension → Mở web. Đăng nhập PoGo Coordinates trong cùng profile trình duyệt.
2. Trên web chọn Pokémon, Stats/PvP, khu vực và các bộ lọc.
3. Mở lại popup → Cài đặt. Nhập mã bạn bè 12 số, chu kỳ (ít nhất 30 giây), thời gian chạy (0 = đến khi dừng), ngưỡng Top IV / Top PvPoke và Discord Webhook nếu dùng. Lưu.
4. Bấm Chạy tự động. Popup có thể đóng; giữ Edge và tab Search mở, có thể chạy nền.
5. Đổi bộ lọc trên web: Dừng trước khi đổi, rồi mở popup và Chạy lại.

Không có bộ lọc sao chép trong popup. Mở web / Chỉnh bộ lọc đưa bạn tới tab PoGo. Tab Thông báo xem kết quả và trạng thái gửi.

## Cập nhật

Giải nén ZIP mới và chép đè vào đúng thư mục extension hiện tại. Trong edge://extensions bấm Tải lại của PoGo Monitor. Không gỡ extension để giữ cấu hình, webhook và lịch sử. Bấm biểu tượng extension để mở popup mới.

Cài lần đầu: edge://extensions → Developer mode → Load unpacked → chọn thư mục chứa manifest.json.

## PvP và Discord

Hạng 1 tốt nhất. Hạng IV tính cục bộ theo stat product, giới hạn level và sàn IV đã chọn. Hạng loài từ PvPoke Overall Open Great/Ultra League. Mặc định cả hai ngưỡng phải đạt trên cùng loài/tiến hóa. Bộ lọc web chạy trước ngưỡng extension. Dữ liệu PvPoke có sẵn, có thể cập nhật trong Cài đặt.

Discord chỉ gửi tọa độ dạng văn bản thường, ví dụ `14.538988,121.004883`. Trên điện thoại, nhấn giữ tin → Sao chép văn bản để lấy đúng tọa độ. Không kèm tên, IV, ảnh, khối code hoặc embed. Webhook lưu cục bộ; không gửi mã bạn bè hay webhook trong thông báo.

Một spawn chỉ báo một lần đến khi hết hạn. Discord 429 được thử lại; lỗi mạng không rõ đã gửi hay chưa cần kiểm tra kênh trước khi gửi lại. Khóa VIP và hạn mức web được giữ nguyên. Shiny yêu cầu thêm mã bạn bè trong hồ sơ web.

## Kiểm tra

Bản 0.3.3 đổi tin Discord sang chỉ tọa độ. Chưa tải lại bản mới vào Edge hoặc kiểm tra tin mới trong Discord thực tế.

Bản 0.2.4: Trong tab Thông báo, bấm Xóa lịch sử & thử lại. Extension dừng lịch, xóa lịch sử và dấu đã báo; giữ nguyên cấu hình và webhook. Sau đó bấm Tìm ngay hoặc Chạy tự động. Không xóa tin trong Discord. Kiểm tra tự động: 41 passed. Chưa thực hiện xóa trên extension đang cài trong Edge.
