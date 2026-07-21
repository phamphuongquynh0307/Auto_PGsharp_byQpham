# Auto Catch Pokemon cho PGSharp

[English](README.md) | **Tiếng Việt**

Công cụ Windows tự động bắt Pokemon trong Pokemon GO dùng với PGSharp. Ứng dụng kết nối và điều khiển điện thoại Android qua ADB, hỗ trợ cả cách bắt thường và bắt nhanh.

> **Dự án cá nhân.** Repo được công khai để tham khảo và không nhận đóng góp code từ bên ngoài.

## Tính năng

- **Tự động bắt Pokemon** — bắt các Pokemon xuất hiện trong danh sách gần đây của PGSharp.
- **Bắt nhanh không cần key PGSharp** — điều khiển cảm ứng Android để ném bóng và thoát encounter nhanh.
- **Tùy chỉnh cú ném** — chỉnh lực ném và thời gian flick cho từng điện thoại.
- **Căn chỉnh thủ công** — tinh chỉnh tọa độ chạm khi tự co giãn chưa đủ chính xác.
- **Săn Shundo** — chỉ dừng khi gặp shiny hoặc Pokemon 100% IV theo cấu hình.
- **Tự né popup** — đóng cảnh báo thời tiết, tốc độ, level-up và màn hình PokeStop.
- **Tự xử lý khi hết bóng** — tạm ngừng bắt, vẫn cho AutoWalk tìm vật phẩm rồi tự bắt lại.
- **Cảnh báo Discord** — báo spawn lâu, báo cáo định kỳ, pin yếu, hết bóng, gặp shiny và nhiều trạng thái khác.
- **Thích nghi màn hình** — tự co giãn tọa độ theo kích thước màn hình Android.

## Yêu cầu

- Máy tính **Windows**.
- Điện thoại **Android** đã cài **Pokemon GO (PGSharp)**.
- Điện thoại và máy tính kết nối **cùng mạng Wi-Fi**.

## Hướng dẫn sử dụng

### 1. Chuẩn bị điện thoại

1. Bật **Tùy chọn nhà phát triển** (thường là: *Cài đặt → Giới thiệu điện thoại → nhấn Số hiệu bản dựng 7 lần*).
2. Bật **Gỡ lỗi USB (USB debugging)**.
3. Mở **Pokemon GO (PGSharp)** và ở màn hình bản đồ.

### 2. Kết nối

**Lần đầu tiên:**

1. Cắm điện thoại vào máy tính bằng cáp USB.
2. Mở ứng dụng và bấm **Kết nối**.
3. Ứng dụng chuyển điện thoại sang gỡ lỗi qua Wi-Fi và ghi nhớ thiết bị.
4. Rút cáp khi ứng dụng thông báo có thể rút an toàn.

**Những lần sau:**

1. Mở ứng dụng.
2. Chọn điện thoại đã lưu hoặc bấm **Kết nối**.
3. Ứng dụng tự kết nối lại qua Wi-Fi.

### 3. Chọn chế độ

- **Bắt Pokemon** — tự động bắt Pokemon trong danh sách gần đây.
- **Shundo** — chỉ săn shiny hoặc Pokemon 100% IV theo cấu hình.

Sau đó chọn kiểu bắt:

- **Bắt thường** — chờ toàn bộ hoạt ảnh bắt thông thường.
- **Bắt nhanh (không key)** — thực hiện thao tác quick catch mà không cần key PGSharp trả phí.

### 4. Chạy

Bấm **Chạy** để bắt đầu, **Tạm dừng** để nghỉ hoặc **Dừng** để kết thúc. Theo dõi hoạt động trong khung nhật ký.

### 5. Cài đặt

- **Webhook Discord** — dán URL webhook của kênh Discord để nhận cảnh báo.
- **Lực ném** — tăng hoặc giảm khoảng cách bay của bóng.
- **Quick Catch flick** — chỉnh thời gian giữ và kéo ngón tay khi bắt nhanh.
- **Căn chỉnh thủ công** — chỉnh các điểm tọa độ nếu thao tác chạm bị lệch trên máy của bạn.
- **Khoảng cách @ → ô đầu** — chỉnh độ lệch tới Pokemon đầu tiên khi cần.

## Khi hết Poke Ball

Ứng dụng tự thoát encounter, gửi cảnh báo Discord, tạm ngừng bắt trong 10 phút nhưng vẫn giữ AutoWalk để tìm thêm vật phẩm. Sau đó ứng dụng tự bắt lại.

## Xử lý sự cố

| Vấn đề | Cách xử lý |
|---|---|
| Không thấy điện thoại | Kiểm tra **Gỡ lỗi USB** và bảo đảm hai thiết bị dùng **cùng mạng Wi-Fi**. |
| Mất kết nối giữa chừng | Bấm **Làm mới** hoặc chọn lại điện thoại. |
| Chạm lệch tọa độ | Mở phần căn chỉnh thủ công và chỉnh các điểm tương ứng với màn hình. |
| Ném bóng quá yếu hoặc quá mạnh | Chỉnh **Lực ném** rồi thử lại với một Pokemon. |
| Điện thoại nóng | Giảm độ sáng, tránh vừa sạc vừa chạy khi không cần thiết và bật tùy chọn làm tối màn hình khi chạy lâu. |

## Mẹo

- Giữ Pokemon GO ở **màn hình bản đồ** trước khi bấm **Chạy**.
- Sau khi chỉnh lực ném hoặc tọa độ, nên thử bắt một Pokemon trước.
- Chạy tự động lâu có thể làm máy ấm; nên để độ sáng vừa phải và đặt máy ở nơi thoáng.

## Cộng đồng & Ủng hộ

- Discord: <https://discord.gg/QXSfKKPpG6>
- Ko-fi: <https://ko-fi.com/qpham7286>

## Bản quyền

Copyright © 2026 Qpham. **All Rights Reserved.**

- Bạn được **xem** mã nguồn và **fork** repo theo điều khoản GitHub.
- Không được sử dụng, sao chép, chỉnh sửa, phát hành lại hoặc dùng cho mục đích thương mại khi chưa có sự đồng ý bằng văn bản của tác giả.
- Pull request từ bên ngoài sẽ không được merge.

Xem chi tiết tại [LICENSE](LICENSE). Nếu muốn xin phép, hãy mở một issue trên GitHub.
