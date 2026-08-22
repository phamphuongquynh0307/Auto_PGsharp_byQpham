# Ảnh cho hướng dẫn trong app

Tab **Hướng dẫn** tự tìm ảnh PNG trong thư mục `guide_images` nằm cạnh `AutoCatchPokemonPGSharp.exe`.

Mỗi ô trong app dùng đúng một tên file. Bộ ảnh hiện đã có đủ:

```text
guide_images/01-app-windows.png
guide_images/02-usb-debug.png
guide_images/03-connect-wifi.png
guide_images/04-test-control.png
guide_images/05-pgsharp-install.png
guide_images/06-pgsharp-shortcuts.png
guide_images/07-pgsharp-common.png
guide_images/08-catch-layout.png
guide_images/09-catch-preview.png
guide_images/10-shundo-feed.png
guide_images/11-shundo-calibration.png
guide_images/12-edge-extension.png
guide_images/13-pgsharp-teleport.png
guide_images/14-coord-flow.png
guide_images/15-spin-preview.png
```

Chỉ cần đặt ảnh đúng tên rồi đóng/mở lại app. Không cần sửa code. Nên:

- che email, tên trainer, webhook, serial thiết bị và tọa độ riêng tư;
- dùng cùng một máy/ngôn ngữ cho toàn bộ bộ ảnh;
- dùng khung hoặc mũi tên để chỉ đúng nút;
- cắt bớt vùng không liên quan nhưng vẫn giữ đủ ngữ cảnh màn hình.

## Nguồn tham khảo của bộ ảnh

- Android Developer options, USB debugging và ADB qua Wi-Fi: tài liệu Android Developers.
- Tên và bố cục các tính năng PGSharp: trang chủ và trang Features chính thức của PGSharp.
- Developer mode và Load unpacked: tài liệu Microsoft Edge trên Microsoft Learn.
- Popup Discord Coord Collector: tự chạy và chụp trực tiếp từ `discord-coord-collector/popup.html` trong dự án.
- Giao diện app, điểm căn và vùng bot nhìn: dựng theo đúng nhãn, màu và luồng hiện có trong mã nguồn.

Ảnh hướng dẫn không chứa serial thiết bị, tài khoản, trainer name hoặc tọa độ thật. Khi giao diện Android/PGSharp đổi phiên bản, nên đối chiếu lại vị trí nút nhưng vẫn giữ nguyên tên file để app tự nạp ảnh mới.
