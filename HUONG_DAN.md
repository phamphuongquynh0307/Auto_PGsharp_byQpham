# Hướng dẫn thiết lập Auto Catch Pokemon cho PGSharp

[Về trang chính](README.vi.md)

Tài liệu này chia riêng từng chế độ để bạn chỉ cần đọc đúng phần mình sử dụng. Hãy làm phần **Thiết lập chung** một lần, sau đó chuyển tới chế độ cần chạy.

> Các giá trị ghi là “khuyên dùng lần đầu” nhằm tạo một cấu hình dễ kiểm tra. Sau khi chạy ổn một Pokémon, bạn mới nên chỉnh tốc độ hoặc các tùy chọn nâng cao.

Tab **Hướng dẫn** trong app cũng có đầy đủ các mục bên dưới. Mỗi ô **ẢNH CẦN THÊM** ghi sẵn tên PNG; đặt ảnh đúng tên vào thư mục `guide_images` cạnh EXE rồi mở lại app, ảnh sẽ tự hiện tại đúng bước.

## 1. Thiết lập chung

### Chuẩn bị điện thoại

1. Bật **Tùy chọn nhà phát triển** trên Android.
2. Bật **Gỡ lỗi USB (USB debugging)**.
3. Kết nối điện thoại và máy tính vào cùng mạng Wi-Fi.
4. Mở Pokémon GO bản PGSharp và vào hẳn màn hình bản đồ.
5. Giữ nguyên độ phân giải/DPI của điện thoại sau khi đã căn chỉnh. Nếu đổi độ phân giải, hãy căn lại.

<!-- ẢNH 01: Android Developer options + USB debugging. -->

### Kết nối lần đầu

1. Cắm cáp USB vào máy tính.
2. Mở `AutoCatchPokemonPGSharp.exe` và bấm **Kết nối**.
3. Chọn **USB (cắm cáp)** nếu chỉ muốn dùng cáp, hoặc chọn **Wi-Fi (rút được cáp)** để app bật ADB qua Wi-Fi.
4. Chấp nhận hộp thoại cho phép gỡ lỗi trên điện thoại nếu Android hỏi.
5. Chỉ rút cáp sau khi nhật ký báo đã kết nối Wi-Fi và có thể rút cáp.

Những lần sau, chọn lại thiết bị đã lưu. Nếu không thấy máy, bấm **Làm mới**; nếu vẫn không được thì cắm USB để bật lại ADB qua Wi-Fi.

<!-- ẢNH 02: Nút Kết nối và thông báo kết nối Wi-Fi thành công. -->

### Kiểm tra trước khi chạy

1. Chọn đúng điện thoại trong ô **Thiết bị**.
2. Bấm **Kiểm tra ADB/scrcpy**.
3. Chỉ chạy bot khi nhật ký xác nhận đủ ba phần: ADB chụp màn hình được, stream realtime nhận được frame và socket scrcpy hoạt động.
4. Bấm **👁 Xem bot nhìn** để xác nhận ảnh đúng chiều, không bị đen và các vùng nhận diện nằm trên giao diện điện thoại.

<!-- ẢNH 03: Ba dòng kiểm tra ADB/stream/scrcpy thành công. -->

### Có cần mọi máy cùng độ phân giải không?

Không bắt buộc. Bản tự động đọc kích thước/DPI, đo tỉ lệ overlay PGSharp, đọc hàng AutoWalk từ
view Android khi ảnh icon khác phiên bản và tìm tâm quả bóng thật trước khi ném. Không nên ép điện
thoại thật đổi độ phân giải chỉ để giống máy của người viết app.

Nếu phát nhiều máy ảo giống nhau hoặc clone một cấu hình emulator, có thể dùng profile chuẩn tùy
chọn để việc hỗ trợ dễ hơn:

1. Màn hình dọc, độ phân giải `1220 × 2712`, mật độ `480 dpi`.
2. **Display size** và **Font size** của Android để **Default**.
3. PGSharp dùng cùng phiên bản; thêm **AutoWalk**, **Feeds**, **Teleport** và **Settings** vào
   Custom Shortcuts, rồi để menu shortcut mở trong lần kiểm tra đầu.
4. Giữ bật **Đọc overlay PGSharp để soi Nearby chính xác hơn**.
5. Sau khi đổi resolution/DPI hoặc clone máy, vào **Căn chỉnh tay → Đặt lại mặc định** để xóa tọa
   độ của máy cũ.

Profile trên là điểm chuẩn hỗ trợ, không phải điều kiện chạy. Với điện thoại thật, ưu tiên giữ
nguyên cấu hình màn hình đang dùng và kiểm tra bằng **Xem bot nhìn**:

- Ở map: AutoWalk phải được khoanh đúng hàng và ghi `RUNNING` hoặc `PAUSED` khi icon đọc được.
- Trong encounter có bóng: vòng tâm bóng và mũi tên `THROW` phải bám vào quả bóng thật.
- Nếu popup vẫn không được xử lý, giữ nguyên popup và bấm **Xuất báo cáo lỗi**; ZIP đã có ảnh,
  resolution, DPI và log nhận dạng để sửa theo đúng máy, không cần người dùng đoán threshold.

### Nguyên tắc căn chỉnh

- Hãy thử chế độ tự động trước. App tự đọc kích thước, DPI và tự đo tỉ lệ giao diện.
- Điểm ném tự động bám theo tâm quả bóng thật; hàng AutoWalk ưu tiên icon rồi dùng view Android
  làm đường lui. Chỉ căn tay khi cả hai đường tự động vẫn lệch/không đọc được.
- Chỉ mở **🎯 Căn chỉnh tay** khi cửa sổ **Xem bot nhìn** cho thấy điểm hoặc khung bị lệch thật sự.
- Tọa độ lưu trong phần căn tay chỉ là cấu hình cho đúng độ phân giải đã căn, không phải một vị trí dùng chung cho mọi máy.
- Riêng vị trí Pokémon trên Nearby, app ưu tiên vị trí đang đọc trực tiếp từ giao diện PGSharp; tọa độ căn tay chỉ là đường lui khi không đọc được.
- Sau khi đổi độ phân giải, DPI hoặc bố cục PGSharp, bấm **Đặt lại mặc định** rồi căn lại thay vì dùng tọa độ cũ.
### Khi bot gặp popup lạ

Ảnh nhận dạng popup đi kèm app được cắt từ một máy, một bản PGSharp và Pokémon GO. Máy khác bản,
khác ngôn ngữ hay khác giao diện thì popup vẽ khác đi và app không nhận ra được.

Từ bản này, không cần làm gì cả: **màn hình không đọc được liên tục quá 12 giây thì bot tự bấm
phím Back**, giống như khi mình gặp popup lạ. Tối đa 8 giây một lần.

Bot **không bao giờ** bấm Back trong hai trường hợp: đang gặp Pokémon (bấm là mất con đó) và
đang ở map (thanh Nearby còn hiện). Nếu Back lỡ làm hiện hộp *"Thoát Pokémon GO?"* thì đó là hộp
thoại Android thật, app đã biết bấm CANCEL.

Mỗi lần kẹt app lưu một ảnh vào thư mục `stuck/` cạnh EXE. Gửi ảnh đó kèm báo lỗi thì lần cập
nhật sau app nhận được popup đó cho tất cả mọi người — không ai phải tự chỉnh.

Muốn tắt: **Cài đặt → bật Hiện tuỳ chọn nâng cao → bỏ tick "Bot kẹt: tự bấm Back để thoát màn
hình lạ"**.

## 2. Chế độ Auto bắt Pokémon

### Dùng khi nào

Chế độ này tự tìm Pokémon trên thanh Nearby bên phải, mở encounter và ném bóng. Có hai kiểu bắt:

- **Auto bắt thường**: ném rồi theo dõi kết quả encounter, ném lại nếu Pokémon thoát ra.
- **Auto bắt nhanh (không cần PGSharp key)**: dùng thao tác Quick Catch và thoát nhanh sau cú ném.

### Chuẩn bị PGSharp

1. Đứng ở màn hình bản đồ.
2. Mở thanh Nearby bên phải và bảo đảm nhìn thấy ít nhất một Pokémon.
3. Không che thanh Nearby bằng cửa sổ khác của PGSharp.
4. Nếu muốn app lấy thêm Pokémon từ Feed khi Nearby trống, mở đúng thanh Feed có biểu tượng RSS. Lần thiết lập đầu nên để tùy chọn này **tắt**.

<!-- ẢNH 04: Màn hình PGSharp đúng cho Auto bắt, đánh dấu thanh Nearby và dấu @. -->

### Cài đặt khuyên dùng lần đầu

1. Chọn **Chế độ → Auto bắt Pokémon**.
2. Chọn kiểu bắt mong muốn.
3. Giữ **Lực ném = 700**, **Chờ mở màn bắt = 3 giây**, **Số bóng tối đa mỗi con = 3**.
4. Giữ bật **Đọc overlay PGSharp để soi Nearby chính xác hơn**.
5. Giữ bật **Nghỉ khi PGSharp báo cooldown**.
6. Đặt **Giới hạn số con = 1** cho lần thử đầu.
7. Bấm **Chạy** và quan sát một quy trình đầy đủ trước khi tăng giới hạn.

Với Quick Catch, chỉ chỉnh **Flick Quick Catch** hoặc **Chờ sau ném trước khi thoát** khi thấy thao tác Berry/Flee chưa ăn. Không nên đổi nhiều giá trị cùng lúc.

### Dấu hiệu đang chạy đúng

- Nhật ký báo tìm thấy Pokémon trên Nearby và bấm đúng hàng có Pokémon.
- Encounter mở, bóng được ném từ chính nút bóng trên màn hình.
- Sau khi bắt/thoát, app trở về bản đồ rồi mới chọn Pokémon kế tiếp.
- Nếu một cú bấm Nearby không ăn, app thấy hàng vẫn còn và thử lại sớm thay vì chờ hết timeout dài.

### Khi nào cần căn tay

Mở **🎯 Căn chỉnh tay → Bắt Pokémon** và chỉ sửa mục đang sai:

- **Điểm bấm Pokémon (Nearby)** khi điểm vàng không nằm trên hàng Pokémon.
- **Điểm ném bóng** khi điểm bắt đầu cú ném không nằm giữa quả bóng.
- Nhóm **Bắt nhanh** khi thao tác Berry hoặc Flee lệch.
- **Vòng quét PokéStop** nếu đã bật quay stop khi hết bóng.

<!-- ẢNH 05: Xem bot nhìn + ảnh căn tay của Auto bắt thường và Quick Catch. -->

## 3. Chế độ Chấm shiny theo IV

### Dùng khi nào

Chế độ này lấy Pokémon từ Feed PGSharp, teleport tới Pokémon, rồi thử mở encounter. PGSharp phải chặn Pokémon không shiny; vì vậy encounter chỉ mở khi gặp shiny. Nếu shiny mở ra, app đọc ba cột IV Công/Thủ/HP và so với mục tiêu.

### Chuẩn bị PGSharp bắt buộc

1. Bật tính năng PGSharp chặn encounter không shiny.
2. Mở thanh Feed/QuickSniper có biểu tượng RSS và để hàng Pokémon đầu tiên nhìn thấy được.
3. Giữ thanh Nearby có dấu `@` hiển thị ở bên phải.
4. **Ngắt Go Plus trước khi chạy.** Nếu Go Plus còn kết nối, PGSharp chặn teleport; app sẽ bấm CANCEL để tránh softban rồi dừng chế độ.

<!-- ẢNH 06: Cài đặt chặn non-shiny và bố cục Feed + Nearby đúng. -->

### Cài đặt khuyên dùng lần đầu

1. Chọn **Chế độ → Chấm shiny theo IV**.
2. Nhập riêng **IV Công**, **IV Thủ** và **IV HP** từ `0` tới `15`.
3. Để **Chờ Pokémon xuất hiện trên Nearby = 0** nếu muốn giữ nguyên một Feed item cho tới khi spawn thật sự xuất hiện.
4. Giữ **Chờ máy ảnh hiện tối đa = 3 giây**.
5. Chọn hành động khi đúng IV: **Tạm dừng chờ tôi bắt** là an toàn nhất khi thử lần đầu.
6. Chọn hành động khi shiny khác IV: **Thoát, soi con khác** hoặc **Tạm dừng chờ tôi bắt** theo nhu cầu.

### Dấu hiệu đang chạy đúng

- App bấm một Pokémon trong Feed, chờ nó xuất hiện trên Nearby rồi mới chấm.
- Pokémon không shiny bị PGSharp chặn và bộ đếm **Soi** tăng.
- Khi encounter shiny mở, app đọc IV. Nếu không đọc chắc chắn, app giữ encounter và tạm dừng thay vì bỏ nhầm.
- App không lấy Feed item kế tiếp khi Pokémon hiện tại chưa có kết quả rõ ràng.

### Căn chỉnh cần kiểm tra

Trong **🎯 Căn chỉnh tay → Shundo**, kiểm tra:

- Điểm hàng đầu của Feed.
- Thanh Nearby/dấu `@`.
- Khung IV pill.
- Khung toast báo Pokémon không shiny.
- Nút Flee.

<!-- ẢNH 07: Căn tay Feed, IV pill, toast và Flee. -->

## 4. Chế độ Chấm shiny IV từ Discord Coord

### Chuẩn bị Microsoft Edge

1. Tải và giải nén **Discord Coord Collector**.
2. Mở `edge://extensions`.
3. Bật **Developer mode**.
4. Bấm **Load unpacked** và chọn đúng thư mục extension đã giải nén.
5. Đăng nhập Discord Web và Pokedex100 trong cùng profile Edge.
6. Mở đúng kênh Discord cần theo dõi. Collector chỉ đọc tab Discord Web đang active.

<!-- ẢNH 08: Edge Extensions với Developer mode và extension đã nạp. -->

### Chuẩn bị PGSharp bắt buộc

1. Bật chặn encounter không shiny giống chế độ Feed.
2. Ngắt Go Plus.
3. Mở rộng menu shortcut PGSharp và giữ nguyên menu đó.
4. Bảo đảm nhìn thấy hàng **Teleport**; app sẽ bấm thẳng vào hàng này, không tự mở menu sao.
5. Kiểm tra hộp Coordinates và nút OK của Teleport hoạt động bình thường.

<!-- ẢNH 09: Menu PGSharp mở sẵn, đánh dấu Teleport, ô Coordinates và OK. -->

### Căn chỉnh ba điểm Discord Coord

Mở **🎯 Căn chỉnh tay → Discord Coord** và đặt đúng:

1. **Dòng Teleport**: giữa hàng Teleport trong menu PGSharp.
2. **Ô nhập Coordinates**: giữa ô nhập tọa độ.
3. **Nút OK Teleport**: giữa nút OK sau khi bàn phím đã ẩn.

Ba điểm này phụ thuộc mạnh vào độ phân giải và bố cục PGSharp, vì vậy cần kiểm tra lại nếu đổi máy.

<!-- ẢNH 10: Cửa sổ căn tay với ba điểm Discord Coord. -->

### Thứ tự chạy đúng

1. Mở app desktop trước và chọn **Chấm shiny IV từ Discord Coord**.
2. Kiểm tra nhật ký có dòng bộ nhận đang chạy tại `127.0.0.1:8766`.
3. Nhập IV mục tiêu và bấm **Chạy**.
4. Mở popup Discord Coord Collector trên Edge và bấm **Bắt đầu**.
5. Collector gửi một coord mới nhất; app chấm xong coord hiện tại rồi mới cho Collector lấy coord tiếp theo.

Nếu nhật ký báo **đang chờ coord**, đó là trạng thái bình thường khi hàng đợi trống, không phải lỗi.

Nếu popup không nhận coord: vào `edge://extensions`, bấm **Reload** extension rồi mở popup kiểm tra phải hiện
`v0.3.3` và endpoint `127.0.0.1:8766`. Nếu vẫn hiện bản cũ, xóa extension cũ và **Load unpacked** lại thư mục
`discord-coord-collector`; không dùng đồng thời hai bản.

<!-- ẢNH 11: Popup Collector ở trạng thái Bắt đầu và log app nhận coord. -->

## 5. Chế độ Quay PokéStop khi đi đường

### Chuẩn bị PGSharp

1. Đứng ở màn hình bản đồ và đặt nhân vật tại khu vực có PokéStop.
2. Nên mở menu PGSharp để app đọc được hàng AutoWalk trong các vòng đầu.
3. Nếu AutoWalk đang dừng và app nhìn rõ biểu tượng dừng, app sẽ bật một lần. Nếu không đọc chắc chắn, app không bấm đoán để tránh tắt nhầm AutoWalk đang chạy.

### Cài đặt khuyên dùng lần đầu

1. Chọn **Chế độ → Quay PokéStop khi đi đường**.
2. Giữ **Bán kính vòng quét = 450 px** và **Giãn cách giữa hai lần bấm stop = 2 giây**.
3. Mở **👁 Xem bot nhìn**. Vòng quét phải ôm quanh nhân vật và chỉ bao phủ các stop thực sự có thể tới.
4. Nếu vòng lệch, dùng **🎯 Căn chỉnh tay → Quay stop** để kéo vòng vào đúng vị trí.

<!-- ẢNH 12: Xem bot nhìn ở chế độ Quay stop, có vòng quét và stop được đánh dấu. -->

### Dấu hiệu đang chạy đúng

- App chỉ bấm PokéStop xanh chưa quay trong vòng quét.
- Stop đã quay chuyển tím nên tự bị bỏ qua.
- Khi PGSharp hỏi **Stop AutoWalk?**, app luôn chọn CANCEL.
- Nếu màn PokéStop mở ra, app tự bấm dấu X để trở lại bản đồ.

## 6. Discord và báo lỗi

### Cảnh báo Discord

Dán URL vào **Cài đặt → Webhook URL**. Tùy chế độ, app có thể gửi báo cáo định kỳ, pin yếu, hết bóng hoặc ảnh shiny. Để trống nếu không cần cảnh báo.

### Khi cần gửi lỗi

1. Giữ nguyên màn hình đang lỗi nếu có thể.
2. Bấm **🧾 Xuất báo cáo lỗi**.
3. Gửi file ZIP vừa tạo, kèm mô tả chế độ đang chạy và thao tác cuối cùng app đã làm đúng.
4. Nếu lỗi liên quan tới vị trí bấm, gửi thêm ảnh từ **👁 Xem bot nhìn** có bật **Vẽ vùng bot nhìn**.

## 7. Danh sách ảnh sẽ bổ sung trong app

Khi chụp ảnh hướng dẫn, nên dùng cùng một máy và che thông tin riêng tư. Bộ ảnh dự kiến gồm:

1. `01-app-windows.png` — tải/cài app Windows.
2. `02-usb-debug.png` — bật USB debugging.
3. `03-connect-wifi.png` — kết nối Wi-Fi thành công.
4. `04-test-control.png` — kiểm tra ADB/stream/scrcpy.
5. `05-pgsharp-install.png` — tải/cài PGSharp và vào map.
6. `06-pgsharp-shortcuts.png` — Custom Shortcuts và menu mở sẵn.
7. `07-pgsharp-common.png` — Nearby Radar, Cooldown, Encounter IV và Block Non-Shiny.
8. `08-catch-layout.png` — bố cục Auto bắt trên map.
9. `09-catch-preview.png` — Live View và căn Auto bắt/Quick Catch.
10. `10-shundo-feed.png` — Feed Shundo và Block Non-Shiny.
11. `11-shundo-calibration.png` — IV pill/toast/Flee.
12. `12-edge-extension.png` — cài extension trên Edge.
13. `13-pgsharp-teleport.png` — hàng Teleport, Coordinates và OK.
14. `14-coord-flow.png` — ba điểm căn + Collector gửi coord.
15. `15-spin-preview.png` — AutoWalk và vòng quét PokéStop.
