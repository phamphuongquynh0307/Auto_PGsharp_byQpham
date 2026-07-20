# Auto Catch Pokemon (PGSharp)

Công cụ tự động bắt Pokemon dùng với PGSharp, điều khiển thiết bị Android qua ADB từ máy tính.

> **Dự án cá nhân.** Repo này public để tham khảo, **không** nhận đóng góp code.

## Tính năng

- **Bắt Pokémon tự động** – tự bắt các Pokémon ở thanh bên phải màn hình.
- **Săn Shundo** – chỉ dừng khi gặp shiny / 100% IV theo cấu hình.
- **Tự né popup** – cảnh báo thời tiết, tốc độ, level-up… và tự đóng màn Pokéstop.
- **Hết bóng tự xử lý** – thoát encounter, tạm nghỉ, vẫn AutoWalk đi kiếm bóng rồi bắt lại.
- **Cảnh báo Discord** – trống spawn lâu, báo cáo định kỳ, pin yếu, hết bóng, gặp shiny…
- **Tự thích nghi màn hình** – đo và căn tọa độ theo từng máy (không cần chỉnh tay).

## Yêu cầu

- Máy tính **Windows**.
- Điện thoại **Android** đã cài **Pokémon GO (PGSharp)**.
- Điện thoại và máy tính **chung một mạng Wi-Fi**.

## Hướng dẫn sử dụng

### 1. Chuẩn bị điện thoại

1. Bật **Tùy chọn nhà phát triển** (thường: *Cài đặt → Giới thiệu →* bấm **Số hiệu bản dựng** 7 lần).
2. Trong đó, bật **Gỡ lỗi USB (USB debugging)**.
3. Mở **Pokémon GO (PGSharp)** và vào tới màn hình bản đồ.

### 2. Kết nối

**Lần đầu tiên:**

1. Cắm **cáp USB** từ điện thoại vào máy tính.
2. Mở app, bấm **Kết nối**.
3. App tự chuyển sang kết nối **Wi-Fi** và ghi nhớ máy.
4. Khi app báo *"có thể rút cáp USB"* → rút cáp ra.

**Những lần sau** (không cần cáp):

1. Mở app.
2. Chọn điện thoại trong danh sách, hoặc bấm **Kết nối**.
3. App tự nối lại qua Wi-Fi.

### 3. Chọn chế độ

- **Bắt Pokémon** – tự động bắt các Pokémon hiện ở thanh bên phải.
- **Shundo** – chỉ săn shiny / 100% IV theo cấu hình bạn đặt.

### 4. Chạy

- Bấm **Chạy** để bắt đầu, **Tạm dừng** để nghỉ, **Dừng** để kết thúc.
- Theo dõi hoạt động ở khung **Nhật ký** phía dưới.

### 5. Cài đặt (tab *Cài đặt*)

- **Webhook Discord** – dán *Webhook URL* của một kênh Discord để nhận cảnh báo.
- **Lực ném** – tăng/giảm nếu bóng ném lệch (quá mạnh sẽ bay qua Pokémon).
- **Khoảng cách @ → ô đầu** – chỉnh nếu bấm không trúng ô Pokémon đầu tiên.

## Khi hết Poké Ball

Khi hết bóng, app tự thoát màn bắt, gửi cảnh báo Discord, **tạm ngừng bắt 10 phút** nhưng vẫn tự di chuyển (**AutoWalk**) để đi kiếm bóng, rồi tự bắt lại.

## Xử lý sự cố

| Vấn đề | Cách xử lý |
|--------|------------|
| Không thấy điện thoại | Kiểm tra đã bật **Gỡ lỗi USB** chưa, và hai máy có **chung Wi-Fi** không. |
| Mất kết nối giữa chừng | Bấm **Làm mới** hoặc chọn lại máy trong danh sách. |
| Bấm lệch tọa độ | Bản mới tự căn theo màn hình; nếu vẫn lệch, **tắt/mở lại app** để đo lại. |
| Máy nóng khi chạy lâu | Cắm sạc; app có thể tự làm tối màn hình cho đỡ nóng (game vẫn chạy nền). |

## Mẹo

- Nên **cắm sạc** khi chạy trong thời gian dài.
- Giữ Pokémon GO ở **màn hình bản đồ** trước khi bấm **Chạy**.

## Cộng đồng & Ủng hộ

- Discord: <https://discord.gg/QXSfKKPpG6>
- Ko-fi: <https://ko-fi.com/qpham7286>

## Bản quyền

Copyright © 2026 Qpham. **All Rights Reserved.**

- ✅ Bạn được **xem** mã nguồn và **fork** repo (theo điều khoản GitHub).
- ❌ **Không** được sử dụng, sao chép, chỉnh sửa, phát hành lại, hay dùng cho mục đích thương mại nếu chưa có sự đồng ý bằng văn bản của tác giả.
- Pull Request từ bên ngoài **sẽ không được merge**.

Chi tiết xem file [LICENSE](LICENSE). Muốn xin phép: mở một issue trên GitHub.
