# PoGo Monitor 0.3.6

- Tách thông tin Pokémon và tọa độ thành hai tin Discord riêng. Nhấn giữ tin coord để sao chép riêng tọa độ trên mobile.
- Thẻ thông tin giữ ảnh, tên, IV, hạng và despawn; bỏ khối tọa độ trong thẻ để tránh nhầm chỗ sao chép.
- Lưu trạng thái đã gửi thẻ. Nếu tin coord bị 429, chỉ thử lại coord, không gửi lại thẻ.
- Giữ cột PvPoke trên trang Search.

Cập nhật: chép đè → Tải lại extension → F5 trang PoGo. Popup hiện v0.3.6. Chỉ tin gửi mới dùng định dạng này.

## PoGo Monitor 0.3.5

- Thêm cột PvPoke cạnh CP / LVL / IV trên mỗi kết quả Search ở chế độ PvP, kể cả khi chưa chạy tự động.
- Tự đổi theo league và tùy chọn tiến hóa; tên loài hiển thị dưới hạng. Chưa có hạng hiện dấu —.
- Cột là hạng loài PvPoke, không phải hạng IV. Không thay đổi kết quả hoặc bộ lọc web.
- Giữ thẻ thông tin Discord và phần văn bản coord để sao chép trên mobile.

Cập nhật: chép đè → Tải lại extension → F5 trang PoGo. Popup hiện v0.3.5.

## PoGo Monitor 0.3.4

- Khôi phục thẻ Discord: ảnh, tên Pokémon, IV, hạng PvP hoặc CP/level, giờ despawn và tọa độ.
- Phần văn bản chính của cùng tin chỉ chứa tọa độ; dùng Sao chép văn bản trên Discord mobile để lấy riêng coord.

Chép đè vào thư mục cũ → Tải lại extension → F5 trang PoGo. Popup phải hiện v0.3.4.

## PoGo Monitor 0.3.3

- Tin Discord chỉ chứa tọa độ dạng văn bản thường để Sao chép văn bản trên điện thoại lấy đúng tọa độ.
- Áp dụng cho cả Stats và PvP; bỏ tên, IV, ảnh và embed trong tin Discord.

Chép đè vào thư mục extension cũ → Tải lại extension → F5 trang PoGo Coordinates. Popup phải hiện v0.3.3.

## PoGo Monitor 0.3.2

- Thêm bảng trạng thái thu gọn ở góc trái dưới trang PoGo Coordinates, hoạt động khi popup đóng.
- Hiển thị đang chạy, đang tìm, đã dừng, chạy ở tab khác hoặc mất kết nối; kèm lần tìm gần nhất, đếm ngược lần tìm tiếp và giờ dừng.
- Chỉ đọc trạng thái từ extension; bảng trên trang không nhận webhook hoặc mã bạn bè.

Chép đè vào thư mục extension cũ → Tải lại extension → F5 trang PoGo Coordinates. Popup phải hiện v0.3.2.

## PoGo Monitor 0.3.1

- Discord hiển thị giờ despawn và thời gian còn lại bằng timestamp tự cập nhật theo giờ của người xem.
- Tên Pokémon nằm trong khối riêng để sao chép nhanh, tọa độ vẫn có khối riêng.
- Khi Discord gửi lại sau lỗi hoặc giới hạn tốc độ, giờ despawn giữ đúng mốc phát hiện ban đầu.

Chép đè bản 0.3.1 vào đúng thư mục extension đã cài, rồi vào `edge://extensions` hoặc `chrome://extensions` bấm **Tải lại**. Popup phải hiển thị **v0.3.1**. Cập nhật app desktop không cập nhật extension.

## PoGo Monitor 0.3.0

Bản cập nhật tổng hợp các thay đổi đã thống nhất:

- Popup nhỏ, bộ lọc chọn trực tiếp trên web; tab Theo dõi, Cài đặt và Thông báo.
- Tự nhận phiên đăng nhập khi mở lại popup; hướng dẫn rõ khi thiếu mã bạn bè.
- Tự bấm Search theo chu kỳ và thời gian chạy đã chọn.
- PvP lọc cả Top IV và Top PvPoke cho Great 1500 / Ultra 2500.
- Discord: ảnh Pokémon, tên và IV; dòng hạng PvP in đậm; tọa độ trong khối riêng để sao chép. Stats bỏ các hạng.
- Xóa lịch sử & thử lại: xóa dấu đã báo, giữ cài đặt; sau đó bấm Tìm ngay hoặc Chạy tự động.
- Dòng trạng thái giải thích kết quả bị loại bởi PvP, đã báo, hết hạn hoặc lỗi tọa độ.

## Cập nhật bản đã cài

Chép đè các file bản mới vào cùng thư mục extension đang dùng. Mở edge://extensions và bấm Tải lại của PoGo Monitor. Không gỡ extension để giữ mã bạn bè, webhook và lịch sử. Mở popup sẽ thấy v0.3.0.

Edge cần mở và giữ tab PoGo Search, có thể để nền. Bản mới chưa được xác minh đã tải vào Edge của bạn.
