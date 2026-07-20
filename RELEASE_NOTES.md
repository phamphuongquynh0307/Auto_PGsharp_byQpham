# v1.0.1

## 🎯 Nổi bật
- **Chạy đúng trên nhiều độ phân giải / kích thước màn hình khác nhau.** Tọa độ giờ được tính theo **mật độ điểm ảnh (density)** thay vì chiều rộng, nên các nút và vùng nhận diện bám đúng vị trí trên mọi tỉ lệ màn hình — không còn bấm lệch khi đổi máy.
- **Tự hiệu chỉnh khi khởi động (self-calibration).** Bot tự **đo kích thước giao diện thật** của máy (dựa trên nút menu PGSharp) rồi căn chỉnh nhận diện theo đó — cắm máy nào cũng tự thích nghi, khỏi chỉnh tay.
- **Nhận diện ổn định hơn.** Quét template ở **nhiều kích thước** nên bắt icon tốt hơn dù giao diện game render to/nhỏ khác nhau.

## 🐛 Sửa lỗi
- **Đếm số bóng ném sai:** chu kỳ *"không có Pokémon"* không còn bị cộng nhầm vào tổng — chỉ đếm khi thực sự vào màn bắt.
- **Đọc độ phân giải:** sửa lỗi đọc nhầm khi máy đặt độ phân giải tùy chỉnh (nay đọc đúng *Override size/density*), tránh bấm sai toàn bộ.

## ✨ Khác
- Thêm link **Discord** vào tab **Ủng hộ ❤** để tham gia cộng đồng.
