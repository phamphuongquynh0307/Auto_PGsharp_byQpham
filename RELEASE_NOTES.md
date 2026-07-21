# v1.1.0

## Tiếng Việt

### Nổi bật: Quick Catch không cần PGSharp key

- Thêm kiểu bắt **Auto bắt nhanh (không cần PGSharp key)**.
- Mô phỏng thao tác Quick Catch hai ngón thật: giữ và kéo khay Berry, ném bóng, sau đó thoát encounter để bỏ qua hoạt ảnh bắt.
- Hoạt động với PGSharp Free; không cần kích hoạt tính năng Quick Catch trả phí.
- Không cần root điện thoại và không cần cài thêm ứng dụng trên máy Android.
- Bộ điều khiển multi-touch được đóng gói sẵn trong file EXE và tự khởi động khi cần.

### Tùy chỉnh cú ném

- Có thể chỉnh **Lực ném** từ 100–1400 px.
- Có thể chỉnh **Flick Quick Catch** từ 50–500 ms; giá trị càng thấp thì cú vuốt càng nhanh.
- Giá trị mặc định đã được thử nghiệm: lực 700 px và flick 100 ms.
- App lưu lại đúng thông số người dùng nhập và không khóa cứng lực ném.

### Căn chỉnh tay cho Quick Catch

- Thêm điểm **Quick Catch: nút Berry**.
- Thêm điểm **Quick Catch: kéo Berry tới**.
- Hiển thị mũi tên hướng kéo ngay trên ảnh chụp màn hình điện thoại.
- Các tọa độ được lưu theo độ phân giải thiết bị và dùng thay cho vị trí tự động khi chạy.

### Ổn định và sửa lỗi

- Chờ game ghi nhận bóng đã rời tay trước khi bấm Flee, tránh hủy cú ném vì thoát quá sớm.
- Tự kiểm tra đã về bản đồ; nếu Flee chưa được nhận, bot sẽ thử lại thay vì chồng encounter mới lên encounter cũ.
- Sửa quá trình bắt tay với scrcpy control socket để multi-touch hoạt động ổn định qua ADB Wi-Fi.
- Tự đóng kết nối điều khiển và dọn ADB port-forward khi dừng bot.
- Đã thử nghiệm nhiều lượt Quick Catch liên tiếp trên thiết bị Android 15 ở độ phân giải 1220×2712.

### Thông báo cập nhật Discord

- GitHub Actions có thể tự gửi thông báo vào Discord sau khi phát hành phiên bản mới.
- Tin nhắn gồm phiên bản, link tải EXE trực tiếp và link xem release notes.
- Cần cấu hình repository secret `DISCORD_WEBHOOK_URL` để bật thông báo.

### Cách cập nhật

1. Tải file `AutoCatchPokemonPGSharp-v1.1.0.exe` trong phần Assets.
2. Đóng phiên bản đang chạy.
3. Thay file EXE cũ bằng file mới và mở lại; không cần cài đặt.
4. Chọn **Auto bắt nhanh (không cần PGSharp key)** trong phần Kiểu bắt.
5. Nếu cần, mở **Căn chỉnh tay** để đặt lại hai điểm Berry cho đúng màn hình.

> Lưu ý: PGSharp Free không có Guaranteed Hit. Tỷ lệ trúng vẫn phụ thuộc vào lực ném, tốc độ flick, khoảng cách Pokémon và thời điểm Pokémon tấn công hoặc nhảy.

Hỗ trợ: https://discord.gg/QXSfKKPpG6

---

## English

### Highlight: Quick Catch without a PGSharp key

- Added the **Quick auto catch (no PGSharp key)** catch style.
- Performs a real two-finger Quick Catch gesture: hold and drag the Berry drawer, throw the ball, then leave the encounter to skip the catch animation.
- Works with PGSharp Free without enabling its paid Quick Catch feature.
- No root access or additional Android app installation is required.
- The multi-touch controller is bundled in the EXE and starts automatically when needed.

### Throw customization

- **Throw power** is editable from 100–1400 px.
- **Quick Catch flick** is editable from 50–500 ms; lower values produce a faster flick.
- Tested defaults: 700 px throw power and a 100 ms flick.
- User-entered values are saved and are not forcibly locked.

### Manual Quick Catch alignment

- Added a **Quick Catch: Berry button** alignment point.
- Added a **Quick Catch: Berry drag target** alignment point.
- The drag direction is displayed as an arrow over the phone screenshot.
- Coordinates are saved per device resolution and override automatic positions while running.

### Reliability and fixes

- Waits for Pokémon GO to register the released ball before tapping Flee, preventing early exits from cancelling the throw.
- Confirms that the map has returned and retries Flee when necessary instead of stacking encounters.
- Fixed the scrcpy control-socket handshake for reliable multi-touch over ADB Wi-Fi.
- Closes the control connection and removes ADB port forwarding when the bot stops.
- Tested across multiple consecutive Quick Catch cycles on an Android 15 device at 1220×2712.

### Discord update notifications

- GitHub Actions can notify Discord after a new release is published.
- The notification includes the version, direct EXE download, and release-notes links.
- Configure the `DISCORD_WEBHOOK_URL` repository secret to enable notifications.

### How to update

1. Download `AutoCatchPokemonPGSharp-v1.1.0.exe` from the release Assets.
2. Close the currently running version.
3. Replace the old EXE and launch the new one; no installation is required.
4. Select **Quick auto catch (no PGSharp key)** under Catch style.
5. If necessary, open **Manual align** and reposition the two Berry points for your screen.

> Note: PGSharp Free does not provide Guaranteed Hit. Accuracy still depends on throw power, flick speed, Pokémon distance, and whether the Pokémon attacks or jumps.

Support: https://discord.gg/QXSfKKPpG6
