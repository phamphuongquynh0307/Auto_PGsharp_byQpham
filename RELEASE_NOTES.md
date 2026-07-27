# v1.1.10

## Tiếng Việt

### Shundo kiểm tra Pokémon hiện tại trước khi dịch chuyển

- Khi vừa bấm chạy, bot kiểm tra Pokémon đang có sẵn trên thanh Nearby `@` trước.
- Bot chỉ lấy Pokémon tiếp theo từ feed và dịch chuyển sau khi đã chấm con hiện tại.
- Các vòng sau vẫn tiếp tục theo feed bình thường, không mở lại Pokémon vừa chấm.

### Không còn báo shiny khi vẫn đang ở bản đồ

- Tín hiệu nút Poké Ball giờ phải đi kèm việc thanh Nearby `@` đã biến mất.
- Nếu một chi tiết đỏ/trắng trên bản đồ bị nhận nhầm thành nút bóng nhưng thanh Nearby vẫn
  còn hiển thị, bot bỏ qua và không tăng bộ đếm shiny.

---

## English

### Check the current Pokémon before teleporting

- On startup, Shundo checks a Pokémon already present in the Nearby `@` bar first.
- It consumes the next feed entry and teleports only after the current Pokémon is checked.
- Later cycles continue through the feed normally without reopening the last checked spawn.

### No phantom shiny reports while still on the map

- The encounter Poké Ball signal is now accepted only after the Nearby `@` bar disappears.
- A red/white map element that resembles the ball button is ignored while Nearby remains
  visible, so it cannot increment the shiny counter.

---

# v1.1.9

## Tiếng Việt

### Xem trực tiếp: giờ là màn hình gương thật, và điều khiển được

- **14–26 fps** thay cho một ảnh tĩnh mỗi 800 ms. Hình lấy từ luồng H.264 sẵn có.
- **Kéo chuột trên ảnh là vuốt thật trên máy**, qua đúng kênh điều khiển mà bot vẫn dùng. Là nhấn–kéo–thả thật nên bản đồ pan và fling bình thường, không phải một cú chạm nhảy cóc.
- Thêm nút **Back**, **Home**, nút phóng to (340/460/600 px), và hai ô tích: **Vẽ vùng bot nhìn**, **Điều khiển bằng chuột** (tắt nếu chỉ muốn xem, tránh lỡ tay).
- **Vẽ đúng theo chế độ đang chạy.** Trước đây luôn vẽ khung của Shundo kể cả khi đang chạy chế độ bắt. Chế độ bắt nay có hình vẽ riêng: ô Nearby sẽ bấm, điểm ném và hướng ném, thanh feed khi dùng tới, khung nhận encounter, khung hết bóng, nút thoát.
- Lớp vẽ được tính trên nhịp riêng (mỗi ~0,8 giây) rồi ghép vào từng khung hình, nên hình vẫn mượt để điều khiển. Đổi lại, phần vẽ trễ tối đa khoảng một giây so với hình.
- Thanh trạng thái hiện fps, độ phân giải máy, và **báo lỗi cuối** nếu có — trước đây lỗi bị nuốt im lặng.

### Không còn phải căn tay khung nút bóng

- Nút chọn bóng ở góc dưới phải (dấu hiệu "đang trong encounter") **tự được tìm theo hình dạng**: một vòm đỏ bão hoà, rộng hơn cao, có bụng trắng ngay bên dưới. Góc quét tính theo phần trăm màn hình nên không phụ thuộc thiết bị.
- **Đã xoá mục "Khung nút bóng phải" khỏi cửa sổ căn chỉnh tay** — không còn gì để căn.
- Lý do phải đổi: khung mặc định nằm gần như hoàn toàn *phía trên* quả bóng, chỉ liếm đúng mép trên của vòm đỏ, lệch tâm bóng thật khoảng 50 px. Vì thế nó cần những điều kiện hình học rất khó chịu và chỉ lệch vài pixel là mù hẳn.
- Ngưỡng màu được siết theo số đo thật (bóng: r−b ≈ 175; banner hồng "A Route is nearby!" ở cùng góc: r−b ≈ 52) kèm giới hạn kích thước, nên tấm banner đó không còn bị nhận nhầm thành encounter.

---

## English

### Live view: a real mirror now, and you can drive it

- **14–26 fps** instead of one still image every 800 ms, taken from the existing H.264 stream.
- **Dragging on the image swipes the phone**, through the same control channel the routines use. It is a real press–move–release, so the map pans and flings instead of receiving one teleporting tap.
- Adds **Back** and **Home** buttons, a zoom step (340/460/600 px), and two toggles: **Draw what the bot sees** and **Control with mouse** (untick to just watch).
- **Draws the running mode's own detections.** It previously always drew Shundo's boxes even in catch mode. Catch now has its own: the Nearby slot it would tap, the throw point and direction, the feed bar when it is used, the encounter box, the out-of-balls box and the flee button.
- The overlay is computed on its own cadence (~0.8 s) and composited onto live frames, keeping the video smooth enough to control. The trade-off is that the drawing lags the video by up to a second.
- The status line shows fps, device resolution and **the last error** if one occurred — these used to be swallowed silently.

### The encounter ball-selector no longer needs manual alignment

- The bottom-right ball-selector (the "we are in an encounter" signal) is now **found by its own shape**: a saturated red dome, wider than it is tall, with a bright white belly directly beneath it. The corner searched is a fraction of the frame, so it is device-independent.
- **The "Right ball-selector box" item is gone from the manual calibration window** — there is nothing left to line up.
- Why it had to change: the default box sat almost entirely *above* the ball, clipping only the top edge of the dome, about 50 px off the real centre. That forced some very awkward geometry conditions and went blind when a few pixels out.
- Colour thresholds were tightened from measurements (ball: r−b ≈ 175; the pink "A Route is nearby!" banner sharing that corner: r−b ≈ 52) plus a size bound, so that banner is no longer mistaken for an encounter.

---

# v1.1.8

Bản vá cho v1.1.7. Cùng một lỗi nhận diện gây ra tất cả: thanh sidebar trong suốt nên nền
bản đồ rối (sân gym, sự kiện, confetti) đâm xuyên qua, làm **viền xung quanh ô còn nhiều hơn
viền của chính con Pokémon** — phép kiểm tra sprite trượt và bot kết luận thanh trống trong
khi nó đang đầy. Trước v1.1.7 hậu quả chỉ là đứng chờ; từ v1.1.7 nó thành dịch chuyển đi mất.

## Tiếng Việt

### Không còn bấm nhầm sang thanh feed khi Nearby vẫn còn Pokémon

- Quét cả thanh Nearby thay vì chỉ soi ô đầu tiên. Ô nào đọc được thì bấm ô đó; chỉ khi **cả thanh** không thấy gì mới coi là trống.
- Phải **3 chu kỳ liên tiếp** đọc trống mới cho phép dịch chuyển theo thanh feed. Một lần đọc trống là nhiễu, không phải bằng chứng.
- Chỉ nhảy feed khi nhìn thấy dấu `@` của thanh Nearby — không thấy nghĩa là đang ở màn hình khác (encounter, tổng kết, hộp thoại) và tuyệt đối không được dịch chuyển.
- Bỏ cú bấm thừa khi encounter mở trễ: máy nào vẫn hiện sidebar lúc đang bắt thì điều kiện "ô Nearby còn Pokémon" luôn đúng, khiến bot bấm thêm một cái lên màn hình encounter.

### Shundo chạy được trở lại

- **Bỏ thao tác tự đóng menu PGSharp.** Menu ở trạng thái mở là bình thường và thường trực, nên icon bánh răng khớp trên mọi khung hình map — bot bấm ngôi sao mỗi vòng, chống lại chính bố cục của người dùng. Menu mở không che thanh nào cả.
- **Quét cả thanh feed** thay vì chỉ ô đầu. Đây là lỗi khiến shundo báo "không có gì" rồi đứng im dù thanh feed đang đầy spawn.
- **Ô Nearby đo từ tay cầm `≡`** thay vì khoảng cách cố định phía trên dấu `@`. Khoảng cách cố định chỉ đúng khi thanh đầy; thanh ngắn lại là điểm bấm trôi lên trên đầu thanh, thậm chí ra ngoài màn hình.
- Điểm bấm nhắm đúng ô mà bộ quét tìm thấy spawn.
- Thêm xử lý cảnh báo Go Plus: bấm CANCEL rồi **dừng hẳn** kèm thông báo, vì shundo dịch chuyển mỗi vòng nên không có đường lui. Trước đây hộp thoại này chặn cứng cả chế độ.

---

## English

### No more jumping to the feed bar while Nearby still holds Pokémon

- Scans the whole Nearby bar instead of only its first slot. Whichever slot reads clean is tapped; only an entirely unreadable bar counts as empty.
- The feed may only teleport after **three consecutive empty cycles**. One empty read is noise, not evidence.
- The feed is only used when the Nearby bar's `@` is in view. Without it we are on another screen (an encounter, a summary, a dialog) and must not teleport.
- Drops the redundant retry tap when an encounter opens late: on devices that keep the sidebars visible mid-catch the "slot still occupied" test stays true, so the retry fired a stray tap onto the encounter screen.

### Shundo works again

- **Removes the automatic PGSharp-menu close.** The expanded menu is the normal, permanent state of that UI, so its gear icon matches on every ordinary map frame — the bot tapped the star every cycle, fighting the user's own layout. The open menu overlaps neither sidebar nor any tap target.
- **Scans the whole feed bar** rather than its first slot. This is what made shundo report nothing and idle while the feed was full of spawns.
- **Measures the Nearby slot from the `≡` drag handle** instead of a fixed distance above `@`. The fixed distance only holds on a full bar; a shorter list walks the tap point off the top of the bar, sometimes off-screen.
- The tap aims at the slot the scan actually found the spawn in.
- Handles the Go Plus warning: answers CANCEL and then **stops with a clear message**, since every shundo cycle teleports and there is no fallback. Previously the dialog blocked the mode outright.

---

# v1.1.7

## Tiếng Việt

### Không còn kẹt trong encounter

- Đầu mỗi vòng, nếu nút chọn bóng góc dưới phải đang hiện thì bot hiểu là đang ở trong encounter và ném luôn. Trước đây khi Pokémon thoát ra khỏi bóng, màn hình encounter che mất thanh Nearby nhưng bot vẫn quay về quét thanh đó nên đứng im vô hạn.
- Pokémon thoát ra khỏi bóng sẽ được ném lại ngay, nhận biết bằng việc quả bóng quay về đúng điểm ném.
- Hết lượt ném mà encounter vẫn mở thì tự thoát encounter để quay lại bản đồ, không bao giờ nằm lại trong đó.
- Thêm cài đặt **Số bóng tối đa mỗi con** (mặc định 3).

### Ném bóng chính xác hơn

- Đường ném giữ thẳng đứng: trước đây điểm đầu và điểm cuối được random riêng nên cú vẩy bị lệch ngang tới hai lần biên độ random, làm bóng bay chệch. Nay chỉ random điểm đầu và độ dài cú ném.
- Nhận biết kết quả từng cú ném (bắt được / thoát ra / quá hạn) thay vì chờ hết thời gian rồi mới xử lý.

### Tìm Pokémon trên thanh Nearby và thanh feed

- Điểm bấm trên thanh Nearby được đo từ tay cầm `≡` ở đầu thanh thay vì dùng một tọa độ cố định. Trên 18 ảnh chụp thử, cách cũ nhận ra 0/18, cách mới 18/18, và tự đúng khi thanh đổi chỗ hoặc đổi độ dài.
- Khi thanh Nearby trống, bot tìm sang thanh feed của PGSharp và nhảy tới spawn đầu tiên nếu có, thay vì ngồi chờ tới lượt AutoWalk. Có thể tắt bằng cài đặt **Nearby trống thì lấy Pokémon từ thanh feed**.
- **Giới hạn số con** nay đếm số Pokémon thay vì số bóng, vì một con thoát ra tốn nhiều bóng.

### Cảnh báo Go Plus khi teleport

- Hộp thoại "Go Plus is connected, teleport may trigger a softban" luôn được trả lời **CANCEL**. Khung tìm kiếm dừng hẳn trước nút OK nên không thể bấm nhầm sang OK.
- Sau một lần bị từ chối, nguồn feed tự tắt cho cả phiên chạy để tránh lặp vô tận tap feed → cảnh báo → CANCEL. Bot tiếp tục chạy bằng Nearby và AutoWalk.

### Nút bấm thích ứng theo từng thiết bị

- Nút AutoWalk được dò bằng chính icon của hàng ở cả hai trạng thái (đang chạy và đang tạm dừng), thay cho một khoảng cách cố định tính từ ngôi sao menu — khoảng cách đó chỉ đúng trên máy đã đo và lệch một hàng là bấm nhầm sang Feeds hoặc Teleport.
- Mỗi lần thấy icon, khoảng cách ngôi sao → hàng được học lại theo máy nên cả đường dự phòng cũng tự chỉnh đúng.
- Nút CANCEL của hộp thoại "Stop AutoWalk?" cũng chuyển sang dò template thay vì offset cố định.

### Căn chỉnh tay

- Mỗi dấu có nút `⌖` để đưa về giữa màn hình, kèm nút đưa toàn bộ dấu trong tab về giữa. Dùng khi giá trị mặc định quy đổi ra ngoài màn hình khiến không kéo được dấu đó nữa.

---

## English

### No more getting stuck in an encounter

- Each cycle now starts by checking the bottom-right ball selector: if it is showing we are inside an encounter and throw immediately. Previously a Pokémon breaking out left the encounter screen covering the Nearby bar while the bot kept scanning for that bar, so it sat there indefinitely.
- A break-out triggers another throw straight away, detected by the ball returning to the throw point.
- If the encounter is still open after the last allowed throw, the bot flees it and returns to the map instead of remaining inside.
- Adds a **Max throws per Pokémon** setting (default 3).

### More accurate throws

- The flick is kept vertical. Start and end points were previously jittered independently, tilting the throw sideways by up to twice the jitter amount and sending balls wide. Only the start point and the throw length are randomised now.
- Each throw's outcome (caught / break-out / timeout) is read directly instead of waiting out the full timeout.

### Finding Pokémon on the Nearby and feed bars

- The Nearby tap point is measured from the bar's own `≡` drag handle instead of a fixed coordinate. Across 18 test screenshots the old approach detected 0/18 and the new one 18/18, and it stays correct when the bar moves or changes length.
- When the Nearby bar is empty the bot checks PGSharp's feed bar and jumps to its first spawn, rather than idling until the AutoWalk dry-spell timer fires. Can be turned off with the **Use the feed bar when Nearby is empty** setting.
- **Catch limit** now counts Pokémon rather than balls, since a break-out costs several throws.

### Go Plus teleport warning

- The "Go Plus is connected, teleport may trigger a softban" dialog is always answered **CANCEL**. The search box stops well short of the OK button so a stray match cannot confirm the teleport.
- After one refusal the feed source switches itself off for the rest of the run, avoiding an endless tap → warning → CANCEL loop. The bot carries on with Nearby and AutoWalk.

### Per-device button targeting

- The AutoWalk row is located by its own icon in both states (running and paused) instead of a fixed distance below the menu star — that distance is only correct on the device it was measured on, and being one row out taps Feeds or Teleport.
- Whenever the icon is seen, the star-to-row offset is re-learned for the device, so the fallback path self-corrects too.
- The "Stop AutoWalk?" dialog's CANCEL button is matched by template rather than a fixed offset.

### Manual calibration

- Every marker gets a `⌖` button that drops it in the middle of the screen, plus a button to recentre every marker in the tab. Use it when a scaled default lands off-screen and the marker can no longer be dragged.

---

# v1.1.6

## Tiếng Việt

### Quick Catch và thoát encounter ổn định hơn

- Giữ đủ thời gian để game ghi nhận cú ném trước khi bấm Flee.
- Gửi thao tác thả bóng dự phòng để tránh trạng thái giữ bóng bị kẹt khi điều khiển qua Wi-Fi.
- Bấm Flee trực tiếp bằng ADB và luôn thực hiện đủ số lần đã cấu hình để trở về Map.
- Khi lỡ mở trang thông tin Pokémon, chỉ bấm nút tick bằng template chính xác; không còn dùng vùng màu rộng có thể bấm nhầm Poké Ball giữa màn hình.

### Quét Nearby chính xác trên nhiều thiết bị

- Nhận diện thêm các sprite màu tối, màu trầm nhưng vẫn giữ điều kiện cạnh để hạn chế nhận nhầm nền.
- Vùng kiểm tra điểm Nearby chỉnh tay giữ kích thước gọn theo pixel thực, không bị phóng quá rộng trên điện thoại độ phân giải cao.
- Bỏ cài đặt **Khoảng cách @ → ô đầu**; dấu `@` chỉ xác nhận thanh Nearby đang hiện, không còn dùng để suy ra điểm bấm.
- Tọa độ và vùng chỉnh tay tự quy đổi theo kích thước màn hình, giúp dùng lại cấu hình trên thiết bị có độ phân giải khác.

### Giao diện và hiệu năng

- Đưa các nút lưu/reset/hủy của cửa sổ căn chỉnh tay lên phía trên và cho phép thay đổi kích thước cửa sổ.
- Giảm bitrate stream mặc định từ 4 Mbps xuống 2 Mbps để giảm tải và nhiệt độ thiết bị.

---

## English

### More reliable Quick Catch and encounter exit

- Waits long enough for the game to commit the throw before tapping Flee.
- Sends fallback pointer-release events to prevent a held-ball state over Wi-Fi control.
- Uses direct ADB taps for Flee and always sends the configured number of exit taps.
- On accidentally opened Pokémon details, accepts only the precise tick template and no longer uses broad color matching that could tap the central Map Poké Ball.

### Accurate Nearby scanning across devices

- Detects darker, muted Pokémon sprites while retaining edge requirements to limit background false positives.
- Keeps the manually calibrated Nearby inspection area tight in native pixels instead of over-scaling it on high-resolution phones.
- Removes the **Distance @ → first slot** setting; `@` now confirms sidebar presence only and never determines the tap point.
- Scales manual points and regions to the current screen size so calibration remains usable across resolutions.

### Interface and performance

- Moves manual-calibration save/reset/cancel controls to the top and makes the window resizable.
- Reduces the default stream bitrate from 4 Mbps to 2 Mbps to lower device load and heat.

---

# v1.1.5

## Tiếng Việt

### Log chẩn đoán nhận diện

- Hiển thị trực tiếp trong khung log từng bước Nearby, mở encounter, chờ bóng và ném.
- Ghi lại tọa độ ô Pokémon và quả bóng mà detector đã chọn.
- Báo thời gian encounter phản hồi trễ, thời gian phục hồi còn lại và nguyên nhân timeout.
- Xác nhận cú ném đã được detector ghi nhận hoặc cảnh báo khi bóng vẫn còn sau thời gian chờ.
- Debounce các thông báo lặp để log dễ đọc và không ảnh hưởng luồng bắt.

---

## English

### Detection diagnostics

- Shows each Nearby, encounter opening, ball wait, and throw stage directly in the application log.
- Records the coordinates selected by the Pokémon-slot and ball detectors.
- Reports delayed encounter timing, remaining recovery time, and timeout reasons.
- Confirms when the detector observes a committed throw or warns when the ball remains visible.
- Debounces repeated messages to keep diagnostics readable without affecting the catch loop.

---

# v1.1.4

## Tiếng Việt

### Phục hồi encounter bị trễ

- Ghi nhớ trạng thái sau khi bấm Pokémon, không quay lại quét Nearby khi encounter đang che giao diện.
- Tiếp tục chờ và ném khi quả bóng xuất hiện trễ do stream MuMu bị lag hoặc nhòe frame.
- Chỉ dùng detector quả bóng chính xác hiện có, không quét màu rộng nên tránh ném nhầm trên bản đồ.
- Giới hạn tổng thời gian phục hồi encounter còn 4,5 giây để chuyển sang Pokémon tiếp theo nhanh hơn.

---

## English

### Delayed encounter recovery

- Remembers the pending encounter after tapping a Pokémon instead of returning to Nearby while the encounter covers the UI.
- Keeps watching and throws when the ball appears late because of MuMu stream lag or a smeared frame.
- Reuses the existing precise ball detector without broad color scanning, preventing blind throws on the map.
- Caps total encounter recovery at 4.5 seconds so the routine advances to the next Pokémon sooner.

---

# v1.1.3

## Tiếng Việt

### Popup phản hồi nhanh và không bấm lặp

- Nhận diện nút đóng theo tỷ lệ màn hình, hỗ trợ nhiều độ phân giải và nhiều kiểu nút X.
- Quét popup trên ảnh thu nhỏ để giảm đáng kể thời gian phân tích.
- Thêm debounce 0,75 giây: mỗi popup chỉ được bấm một lần, không còn đóng rồi mở lại do frame stream cũ.
- Có thể xử lý các popup thời tiết, tốc độ, AutoWalk, Weekly Challenge, phần thưởng và màn tổng kết.

### Stream và nhận diện nhanh hơn

- Mỗi vòng chỉ phân tích frame mới; không xử lý lặp lại cùng một ảnh.
- Decoder chỉ phóng lớn frame thực sự được sử dụng thay vì resize mọi frame nhận được.
- Một frame được dùng chung cho nhiều phép kiểm tra, đồng thời tái sử dụng ảnh thu nhỏ giữa các detector popup.
- Nearby giảm từ khoảng 145 ms xuống 8 ms sau lần nhận diện đầu; Feed giảm từ khoảng 506 ms xuống 16 ms.
- Vị trí Nearby/Feed được xác nhận trong vùng nhỏ và tự quét rộng lại nếu thanh bị di chuyển hoặc biến mất.

### Quick Catch không key ổn định hơn

- Ổn định thao tác hai ngón: giữ Berry, chạm bóng, flick và thả đúng thứ tự.
- Chờ tối thiểu 0,35 giây để game ghi nhận cú ném trước khi thoát.
- Bình thường chỉ bấm Flee một lần; chỉ thử lại nếu frame mới xác nhận encounter vẫn còn mở.
- Không còn các lần Flee thừa rơi xuống bản đồ hoặc vô tình mở lại giao diện.

### Cài đặt và căn chỉnh gọn hơn

- Trang Cài đặt trở lại một trang cuộn, sắp theo thứ tự kiểu bắt, thông số chính, thời gian, Shundo và Discord.
- Căn chỉnh tay chia theo **Bắt thường (có key)**, **Bắt nhanh (không key)** và **Shundo**; chỉ hiện các điểm cần cho từng luồng.
- Toàn bộ thời gian trong Cài đặt dùng đơn vị **giây**. Cấu hình cũ dùng ms/phút được tự động chuyển đổi.

---

## English

### Fast popup handling without repeated taps

- Close-button detection now scales with the screen and supports multiple resolutions and X styles.
- Popup matching runs on reduced frames for substantially lower analysis latency.
- A 0.75-second debounce ensures each popup is tapped once and prevents stale stream frames from reopening it.
- Handles weather, speed, AutoWalk, Weekly Challenge, reward, and catch-summary dialogs.

### Faster streaming and detection pipeline

- Analysis waits for a new frame instead of processing the same image repeatedly.
- The decoder enlarges only frames that are actually consumed instead of resizing every incoming frame.
- Detectors share one frame and reuse prepared reduced images during each popup pass.
- Cached Nearby detection drops from roughly 145 ms to 8 ms; cached Feed detection drops from roughly 506 ms to 16 ms.
- Nearby and Feed positions are validated locally and automatically rediscovered after moving or disappearing.

### More reliable keyless Quick Catch

- Stabilized the two-finger Berry hold, ball touch, flick, and release sequence.
- Waits at least 0.35 seconds for the throw to commit before leaving.
- Normally taps Flee once and retries only while a fresh frame confirms the encounter is still open.
- Prevents extra Flee taps from landing on the map or reopening another screen.

### Cleaner settings and manual alignment

- Settings use one scrollable page ordered by catch style, primary controls, timing, Shundo, and Discord.
- Manual alignment is split into **Normal catch (with key)**, **Quick catch (no key)**, and **Shundo**, showing only relevant controls.
- Every timing setting now uses **seconds**. Existing millisecond/minute settings are migrated automatically.

---

# v1.1.2

## Tiếng Việt

### Hỗ trợ và tối ưu MuMu Player

- Tự phát hiện và kết nối MuMu qua `127.0.0.1:7555`; ưu tiên thiết bị MuMu đang online thay cho thiết bị Wi-Fi cũ đã offline.
- Chuyển tap, double-tap, swipe và Quick Catch sang scrcpy control socket. Sau lần khởi tạo đầu, tap trên MuMu giảm từ khoảng 700 ms xuống còn khoảng 40 ms.
- Double-tap có khoảng nghỉ chính xác, không còn bị MuMu xử lý thành một click đơn.

### Quick Catch đúng chuỗi thao tác và có thể tinh chỉnh

- Chuỗi thao tác: kéo Berry sang phải và giữ → ném/thả Poké Ball → thả Berry → nhấn Flee.
- Nhận diện quả bóng lớn để bắt đầu ném sớm hơn; không phải chờ toàn bộ animation của nút chọn bóng.
- Thêm các cài đặt:
  - Chờ bóng sẵn sàng trước ném (ms).
  - Chờ sau ném trước khi thoát (ms).
  - Số lần nhấn thoát.
  - Khoảng cách giữa các lần thoát (ms).
- Mặc định chờ 200 ms trước ném, 1000 ms sau ném, nhấn thoát 3 lần cách nhau 200 ms.

### Nhận diện và xử lý popup chính xác hơn

- Sửa nhận diện encounter khi khung căn tay bao cả phần đỏ và trắng của nút chọn bóng.
- `CLAIM REWARDS` dùng dải scale riêng và hoạt động trong cả Auto bắt lẫn Shundo.
- Không còn bấm mù tọa độ đóng PokéStop trùng với nút Poké Ball chính trên map; chỉ đóng khi thấy nút X thật.

### Chu kỳ bắt và Shundo nhanh, nhẹ hơn

- Chờ theo trạng thái màn hình thay cho nhiều khoảng nghỉ cố định giữa các lần bắt.
- Shundo nhận toast chặn non-shiny để chuyển con tiếp theo sớm hơn.
- Giảm thời gian chờ cố định sau teleport và giới hạn detector icon `@` vào thanh bên phải.
- Shundo dùng stream nhẹ; chỉ chụp ảnh nét khi encounter shiny cần đọc IV.

---

## English

### MuMu Player support and performance

- Automatically discovers and connects to MuMu at `127.0.0.1:7555`, preferring an online emulator over stale offline Wi-Fi devices.
- Tap, double-tap, swipe, and Quick Catch now use the scrcpy control socket. After initial setup, MuMu tap latency drops from roughly 700 ms to about 40 ms.
- Double-taps now use an accurate gesture gap instead of being interpreted as a single click.

### Configurable native Quick Catch

- Uses the correct sequence: drag and hold Berry → throw/release Poké Ball → release Berry → tap Flee.
- Detects the large throwable ball to start earlier without waiting for the selector animation to finish.
- Added settings for ball-ready delay, post-throw wait, Flee tap count, and Flee tap interval.
- Defaults: 200 ms before throwing, 1000 ms before fleeing, and three Flee taps spaced 200 ms apart.

### Safer detection and popup handling

- Fixed encounter detection when manual alignment frames the complete red-and-white selector button.
- `CLAIM REWARDS` now uses its own scale sweep and works in both Catch and Shundo modes.
- Removed the blind PokéStop close fallback that overlapped the map's main Poké Ball button; the bot now requires a visible X template.

### Faster catch and Shundo cycles

- Replaced several fixed sleeps with screen-state-driven waits.
- Shundo reacts to the non-shiny blocked toast and moves on sooner.
- Reduced fixed post-teleport delay and restricted `@` anchor searches to the nearby sidebar.
- Shundo uses a lighter live stream and requests a crisp frame only when a shiny encounter needs IV reading.

---

# v1.1.1

## Tiếng Việt

### Nổi bật: Nhận encounter đáng tin cho mọi loại bóng

- Bot xác nhận đang trong màn bắt bằng **nút chọn bóng màu đỏ ở góc dưới bên phải** — nút này luôn là Poké Ball đỏ dù bạn đang nạp Poké Ball, Great Ball hay Ultra Ball.
- Thay cho cách cũ dựa vào icon camera (viền trắng trong suốt), vốn mất tương phản trên nền trời sáng nên nhiều lúc **không nhận ra encounter và không ném bóng**.
- Là màu đặc nên nhận diện ổn định trên nền của bất kỳ Pokémon nào.

### Ném xong tự thoát mượt

- Sau khi ném, bot **bấm Flee 2 lần** để chắc chắn thoát kịp trước khi cú bắt hoàn tất — tránh bị kẹt lại ở màn tổng kết.
- Nếu lỡ vẫn hiện màn **"POKÉMON CAUGHT" (tổng kết XP)**, bot tự bấm nút **OK**.
- Nếu lỡ nhảy vào **trang thông tin Pokémon**, bot tự bấm nút **tick (✓) xanh** để quay lại.
- Các nút này được nhắm chính xác, **không bấm nhầm POWER UP / EVOLVE** (tránh tốn Bụi Sao/Kẹo).

### Tự tắt popup Thử thách tuần

- Khi hiện hộp **"WEEKLY CHALLENGE"**, bot tự bấm **MAYBE LATER** để đóng.
- Nhắm đúng dòng chữ, **không bấm nút CHOOSE GROUP** màu xanh.

### Chế độ Shundo cũng dùng chung cách nhận encounter

- Shundo giờ xác nhận encounter đã mở (tín hiệu shiny) bằng đúng **nút chọn bóng đỏ** như chế độ bắt — không còn phụ thuộc icon camera.

### Căn chỉnh tay

- Thêm ô **Khung nút bóng phải (nhận encounter)** — dùng chung cho cả chế độ Bắt và Shundo; kéo thả như các ô khác.
- Gỡ ô "Khung quét camera" cũ vì không còn dùng.

### Cách cập nhật

1. Tải file `AutoCatchPokemonPGSharp-v1.1.1.exe` trong phần Assets.
2. Đóng phiên bản đang chạy.
3. Thay file EXE cũ bằng file mới và mở lại; không cần cài đặt.
4. Nếu nút chọn bóng trên máy bạn nằm lệch, mở **Căn chỉnh tay** và kéo ô đỏ vào đúng nút.

> Lưu ý: PGSharp Free không có Guaranteed Hit. Tỷ lệ trúng vẫn phụ thuộc vào lực ném, tốc độ flick, khoảng cách Pokémon và thời điểm Pokémon tấn công hoặc nhảy.

Hỗ trợ: https://discord.gg/QXSfKKPpG6

---

## English

### Highlight: Reliable encounter detection for any ball type

- The bot confirms it is in an encounter using the **red ball-selector button at the bottom-right** — which is always a red Poké Ball whether a Poké Ball, Great Ball, or Ultra Ball is loaded.
- This replaces the old camera-icon check (a semi-transparent white outline) that lost contrast against a bright sky and often **missed the encounter and never threw**.
- Being an opaque colour, it reads reliably against any Pokémon's background.

### Clean exit after every throw

- After throwing, the bot **taps Flee twice** to leave in time before the catch resolves — no more getting stuck on the summary screen.
- If the **"POKÉMON CAUGHT" XP summary** still slips through, the bot taps **OK** automatically.
- If it lands on the **Pokémon detail page**, the bot taps the **green check (✓)** to go back.
- These buttons are matched precisely and **never hit POWER UP / EVOLVE** (so no Stardust/candy is spent).

### Auto-dismiss the Weekly Challenge popup

- When the **"WEEKLY CHALLENGE"** modal appears, the bot taps **MAYBE LATER** to close it.
- It targets the text and **never taps the green CHOOSE GROUP button**.

### Shundo mode shares the same detection

- Shundo now confirms the encounter opened (its shiny signal) with the same **red ball-selector button** as catch mode — no longer relying on the camera icon.

### Manual alignment

- Added a **Right ball-selector box (encounter)** region — shared by both Catch and Shundo modes; drag it like the other boxes.
- Removed the old "Camera scan box" since it is no longer used.

### How to update

1. Download `AutoCatchPokemonPGSharp-v1.1.1.exe` from the release Assets.
2. Close the currently running version.
3. Replace the old EXE and launch the new one; no installation is required.
4. If your device's ball-selector sits in a different spot, open **Manual align** and drag the red box onto it.

> Note: PGSharp Free does not provide Guaranteed Hit. Accuracy still depends on throw power, flick speed, Pokémon distance, and whether the Pokémon attacks or jumps.

Support: https://discord.gg/QXSfKKPpG6
