# v1.2.0

## Tiếng Việt

### Sửa lỗi toạ độ sai trên máy không phải máy gốc

Màn hình có **hai giao diện co giãn theo hai quy luật khác nhau**, nhưng bot dùng chung một con số cho cả hai:

- **Overlay PGSharp** (thanh Nearby, Feed, menu) vẽ bằng view Android nên co theo **mật độ điểm ảnh (dpi)**.
- **Giao diện Pokémon GO** (nút berry, nút thoát, nút bóng, lực ném) do game tự vẽ nên co theo **bề rộng màn hình**.

Đo trên ba máy thật cho thấy lớp giao diện game lệch **13–18%** trên điện thoại thường. Máy 1220x2712@480 là cấu hình duy nhất hai quy luật trùng nhau — đó là lý do lỗi này không thể thấy trên máy gốc mà máy khác đều dính.

Từ bản này mỗi lớp dùng đúng quy luật của nó, nên **mọi máy đúng ngay từ giây đầu** thay vì phải chờ được hiệu chỉnh.

### Tự đo và tự sửa cho máy lạ

- Bot đo scale giao diện game bằng **khoảng cách giữa nút berry và nút chọn bóng**, hai thứ nó tự dò bằng màu và hình — không cần template, không cần mốc cố định.
- Cần **ba lần đọc đồng thuận** mới tin, vì bộ dò berry có thể báo nhầm trên bản đồ.
- Ngưỡng quyết định có sửa hay không được **suy từ độ chính xác đo được trên chính máy đó**: máy đọc ổn định thì bắt được cả sai lệch nhỏ.
- Scale overlay được đo từ **tất cả** icon PGSharp nhận ra được rồi đối chiếu chéo. Icon nào lệch nhau thì bot **không** đụng vào toạ độ. Thêm lượt quét tinh nên phép đo chính xác gấp 5 lần trước.

### Không còn thao tác trên khung hình cũ

- Cứ 175 giây luồng hình bị Android ngắt và bot khởi động lại. Trước đây khung hình cuối cùng trước khoảng trống đó vẫn được dùng như "hiện tại", khiến bot chạm vào chỗ giao diện **đã không còn ở đó** — trên bản đồ thì dính hộp thoại "Stop AutoWalk?".
- Khoảng trống này ngắn khi cắm USB nhưng dài trên máy tính yếu hoặc Wi-Fi chậm, nên lỗi chỉ xuất hiện ở máy người khác và lặp lại suốt phiên.
- Giờ khung hình quá 0.5 giây bị coi như không có, bot tự chụp lại ảnh mới.
- Sửa luôn trường hợp nặng hơn: khi luồng hình chết hẳn, bot từng chạy mãi trên **một ảnh đứng yên** mà không bao giờ chụp lại.

### Ghi log và nút xuất báo cáo lỗi

- Mọi dòng hiện trong khung log giờ được lưu vào `autoclick.log` cạnh file exe.
- Mỗi lần chạy có dòng đầu ghi rõ máy, độ phân giải, dpi, và đang nối **USB hay Wi-Fi**.
- Nút **🧾 Xuất báo cáo lỗi** gói log, cấu hình và ảnh màn hình vào một file zip để gửi khi báo lỗi.
- **Webhook Discord bị che** trong file xuất ra — đó là thông tin bí mật, không phải dữ liệu chẩn đoán.

### Gọn lại bảng cài đặt

- Từ **29 ô xuống 12 ô** khi bắt thường, **6 ô** ở chế độ shundo. Ô nào không có tác dụng ở chế độ đang chọn thì được ẩn đi — trước đây có 8 ô luôn hiện mà hoàn toàn vô tác dụng.
- Thêm công tắc **Hiện tùy chọn nâng cao** cho các ô tinh chỉnh mili-giây.
- Giá trị bị ẩn vẫn được lưu và nạp lại đầy đủ.
- Ba ô hết báo sai giá trị thật: "Chờ sau ném" bắt đầu từ 1.0 (dưới mức đó bot vốn đã tự nâng lên), "Khoảng cách các lần thoát" ghi rõ shundo tối thiểu 0.45.
- Hai ô tên gần giống nhau được đổi cho rõ nghĩa ngược: **"Chờ con kế tiếp, tối đa"** là mức trần, **"Bắt chậm lại, cách nhau ít nhất"** là mức sàn.

### Kiểm thử

- 82 bài test đều đạt (17 bài cũ, 65 bài mới).
- Kiểm chứng trực tiếp trên ba thiết bị thật: điện thoại 1280x2772@520, MuMu 810x1440@270, và máy 1220x2712@480.

---

## English

### Fixes coordinates being wrong on any device but the authoring one

The screen holds **two UIs that scale by different rules**, and one number was used for both:

- **PGSharp's overlay** (Nearby bar, Feed, menu) is drawn as native Android views, so it follows **density (dpi)**.
- **Pokémon GO's own UI** (Berry button, flee button, ball, throw strength) is drawn by the game, so it follows **screen width**.

Measured on three real devices, the game layer was **13–18% off** on ordinary phones. 1220x2712@480 is the one configuration where both rules agree — which is exactly why this was invisible on the device the coordinates were authored on and affected everyone else.

Each layer now uses its own rule, so **every device is right from the first second** instead of waiting to be corrected.

### Self-measurement for unusual devices

- The game UI scale is measured from the **distance between the Berry button and the ball selector**, both found by colour and shape — no template, no fixed anchor needed.
- **Three readings must agree** before it is believed, because the Berry detector can report a false positive on the map.
- The threshold for acting is **derived from how precisely that device actually measured**, so a steady device catches even small errors.
- The overlay scale is measured from **every** recognisable PGSharp icon and cross-checked. If they disagree, coordinates are left alone. A fine second pass makes the measurement 5× more precise.

### No longer acts on a stale frame

- Every 175 seconds Android stops the video stream and the bot restarts it. The last frame before that gap was still served as "now", so taps landed where the UI **no longer was** — on the map that raises the "Stop AutoWalk?" dialog.
- The gap is short over USB and long on a slow PC or weak Wi-Fi, so this only showed on other people's machines, and it recurred all run.
- Frames older than 0.5s now count as absent and a fresh capture is taken.
- Also fixes the worse case: when the stream died outright the bot ran forever on **one still image** and never fell back.

### Diagnostic log and bug report export

- Every line shown in the log pane is now written to `autoclick.log` next to the exe.
- Each run starts with a header naming the device, resolution, dpi, and whether adb is on **USB or Wi-Fi**.
- A **🧾 Export bug report** button bundles the log, settings and a screenshot into one zip.
- The **Discord webhook is redacted** from the export — it is a credential, not diagnostics.

### Smaller settings panel

- From **29 rows down to 12** while catching, **6** in Shundo mode. Controls that do nothing in the current mode are hidden — eight were always visible while having no effect at all.
- Added a **Show advanced options** toggle for the millisecond tuning.
- Hidden values are still saved and restored in full.
- Three boxes stopped misreporting the real value: "Wait after throw" starts at 1.0 (below that the bot already rounded up), and "Flee tap gap" now states Shundo's 0.45 minimum.
- Two near-identical labels now say which is which: **"wait for next Pokémon, at most"** is a ceiling, **"slow down, at least this long between catches"** is a floor.

### Tests

- All 82 tests pass (17 existing, 65 new).
- Verified directly on three real devices: a 1280x2772@520 phone, MuMu at 810x1440@270, and a 1220x2712@480 device.
