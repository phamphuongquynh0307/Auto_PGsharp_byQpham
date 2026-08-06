# v1.3.0

## Tiếng Việt

### Chế độ mới: Quay PokéStop khi đi đường

- Thêm chế độ **Quay PokéStop khi đi đường** bên cạnh Auto bắt và Chấm shundo.
- Không cần key PGSharp, không cần Go Plus: bot nhận PokéStop bằng **màu**. Stop chưa quay là một khối xanh dương sáng, quay rồi chuyển tím nên tự rơi ra khỏi vùng quét.
- Chỉ bấm những stop nằm trong **vòng tròn quanh nhân vật**; vòng này kéo/chỉnh được trong cửa sổ căn chỉnh vì tầm với phụ thuộc mức zoom bản đồ của từng người. Dùng vòng tròn (không phải cả màn hình) để tay bot không chạm nhầm dãy icon và menu PGSharp ở rìa màn hình.
- Chọn đốm xanh **to nhất** chứ không phải gần nhất: vòng sáng xoay quanh stop bắn ra những mảnh xanh nhỏ, xếp theo khoảng cách thì một mảnh vụn thắng cả cái stop của nó và cú bấm rơi xuống bản đồ trống.
- Nhớ chỗ vừa bấm trong 60 giây, nên một stop ngoài tầm (vẫn xanh) không ăn hết mọi chu kỳ trong khi AutoWalk đang đưa các stop thật đi ngang.
- AutoWalk chỉ được bật **một lần** lúc bắt đầu. Ở chế độ này không có stop trong tầm không có nghĩa là phải đi chỗ khác — stop đứng yên tại chỗ của nó — nên bấm lại hàng AutoWalk mỗi chu kỳ chỉ tổ tắt mất cái đang chạy.
- Mỗi lần chạm bản đồ PGSharp đều hỏi "Stop AutoWalk?"; bot luôn bấm **CANCEL**. Nếu stop mở màn ảnh photo-disc thì cùng lượt quét đó đóng luôn.

### Hết bóng: vừa đi vừa quay stop

- Auto bắt có thêm tùy chọn **Hết bóng: vừa đi vừa quay PokéStop (không cần key)**.
- Quay stop mới là thứ thật sự làm đầy lại túi, nên 10 phút chờ giờ không đứng yên nữa. Khác Go Plus, cách này chạy được cả với **Bắt nhanh không key**.
- Thời gian chờ hết bóng thành **thiết lập chỉnh được (phút)** thay vì cố định 10 phút, vì stop dày hay thưa là chuyện của từng khu.

### Sửa: còn bóng loại khác thì ném tiếp, đừng báo hết

- Trước đây bot dò quả bóng bằng **màu đỏ ở phần vòm**. Hết Poké Ball thường, game tự đổi sang Great (xanh), Ultra (đen/vàng) hay Master (tím) — dò không ra đỏ, bot tưởng hết bóng, chạy trốn rồi ngồi im 10 phút trong khi túi vẫn đầy.
- Giờ đọc ở **nút tròn giữa quả bóng**: lõi xám sáng nằm trong vành đen dày. Chỗ này giống hệt nhau ở mọi loại bóng, chỉ có vòm mới đổi màu. Bot ném tới khi thật sự không còn quả nào.
- Bắt buộc thấy **cả hai** (vành đen và lõi sáng) nên nền tối (bản đồ đêm, cỏ tối) hay nền sáng (tuyết, trời) đều không bị nhận nhầm là còn bóng.
- Cửa sổ xác nhận hết bóng nới 1,2 → 2,0 giây để chịu được lúc game đang chuyển từ loại bóng này sang loại kia, khi ô chọn bóng trống vài khung hình dù túi chưa hết.
- Live view vẽ thêm vòng tròn ngay chỗ đang đọc, nhìn màn hình là biết bot bắt đúng chỗ chưa.

### Khác

- Sửa lỗi build: file spec giờ **hỏi trước** xem Tcl/Tk của máy có chạy được không, chỉ ép TCL_LIBRARY/TK_LIBRARY khi nó thật sự hỏng. Ép sẵn như trước làm PyInstaller dò tkinter thất bại và loại luôn tkinter, ra file EXE chết ngay khi mở.

### Kiểm chứng

- 131 bài test đạt, không bài nào lỗi.
- Bộ dò bóng chạy đúng trên ảnh chụp thật 1220×2712: đo được vành đen 0,26–0,38 và lõi sáng 0,33–0,53, ổn định qua lệch ±25px, nhiều bán kính và 3 mức tỉ lệ máy — ngưỡng đặt cách xa khoảng đó. Khung bóng đang bay và các khung màn hình bản đồ đều đọc đúng là "không có bóng".
- EXE Windows build thành công.

---

## English

### New mode: spin PokéStops while walking

- **Spin PokéStops while walking** joins Auto catch and Shundo check as a third mode.
- No PGSharp key and no Go Plus: stops are recognized by **colour**. An unspun stop is one flat bright blue; a spun one turns violet and drops out of the scan by itself.
- Only stops inside the **circle around your avatar** are tapped, and that circle is drag/resizable in the calibration window, since how far a stop can sit and still be in range depends on your map zoom rather than on the app. A circle rather than the whole screen keeps taps off the right icon rail and the PGSharp menu column at the screen edges.
- The **biggest** blue blob wins, not the nearest: the rings spinning around a stop throw off bright blue fragments, and ranking by distance let a fragment beat the very stop it belonged to, landing the tap on bare map.
- Tapped spots are remembered for 60 seconds, so a stop that stayed blue because it was out of range cannot eat every cycle while the walk carries real ones past.
- AutoWalk is started **once**, at the start. Here an empty cycle does not mean the area dried up — stops stand where they stand — so re-tapping that row every cycle could achieve exactly one thing: stopping a walk that was running fine.
- Every map touch makes PGSharp raise its "Stop AutoWalk?" dialog; the bot always answers **CANCEL**. If a stop opens its photo-disc screen instead of spinning in place, the same sweep closes it.

### Out of balls: spin stops during the hold

- Catching gains an **Out of balls: spin PokéStops while walking (no key needed)** option.
- Spinning stops is what actually refills the bag, so the ten-minute hold is no longer spent standing still — and unlike Go Plus this path works in **Quick Catch without a key**.
- The hold's length is now a **setting in minutes** instead of a fixed ten, because how dense the stops are is a local matter.

### Fixed: a different ball type is not an empty bag

- The ball was detected by the **red of its dome**. When the last Poké Ball was spent the game switched to Great (blue), Ultra (black/yellow) or Master (purple), the red test found nothing, and the bot fled the encounter and sat out a ten-minute pause with a full bag.
- Readiness is now read at the **ball's round centre button** — a light grey hub inside a thick black band — which is identical on every ball type; only the dome carries the type's colour. Throwing continues until no ball of any type is left.
- **Both** halves are required (some black band and a light hub), so dark scenery (night maps, dark grass) and pale scenery (snow, sky) cannot be mistaken for a ball.
- The empty-bag confirmation window widens from 1.2 to 2.0 seconds so it outlasts the swap the game does when one ball type runs out and the next takes over, which briefly empties the selector while the bag is not.
- The live view draws the window that is actually being read, so a mis-aimed detector is visible at a glance.

### Also

- Build fix: the spec now **asks first** whether this Python's Tcl/Tk starts, and only forces TCL_LIBRARY/TK_LIBRARY when it genuinely cannot. Forcing them unconditionally broke PyInstaller's own tkinter probe, which then excluded tkinter and produced an EXE that died before the GUI could open.

### Verification

- 131 tests pass, none failing.
- The ball detector was measured on a real 1220×2712 screenshot: black band 0.26-0.38 and light hub 0.33-0.53, stable across ±25px of placement error, several radii and three device scales — the thresholds sit well outside that range. A ball mid-throw and map screens all read correctly as "no ball".
- The Windows executable builds successfully.
