# v1.1.12

## Tiếng Việt

### Không còn đứng im trước thanh Nearby đang đầy

- **Quét hết mọi ô của thanh Nearby**, không chỉ ô đầu. Khi dùng ô cố định đã căn tay thì các ô dưới trước đây không hề được nhìn tới, nên chỉ cần ô trên cùng trống là bot kết luận cả thanh trống dù bên dưới vẫn còn Pokémon.
- **Đổi cách đánh giá một ô có Pokémon hay không**: dùng khoảng sáng (bách phân vị 98 trừ 20) thay cho độ lệch chuẩn. Cách cũ chết trên cảnh đêm — sprite tối trên nền thanh tối gần như không lệch. Đo trên 37 ô ở máy MuMu 1220x2712: một con Combee ban đêm chỉ đạt 17.9 trong khi nhiễu bản đồ đạt 27.9, không ngưỡng nào đúng được.
- **Xác nhận trong một khoảng thời gian** thay vì đòi các khung hình liên tiếp, nên một khung stream bị nhòe không còn xóa sạch bằng chứng và bỏ bot đứng yên trước thanh đầy.
- Trước khi kết luận thanh trống, bot chụp lại một ảnh nét và **đọc thẳng cây giao diện của PGSharp** để hỏi lại lần cuối.

### Đọc thẳng overlay PGSharp

- PGSharp vẽ overlay bằng view Android thật, nên cây giao diện **nói thẳng** có bao nhiêu Pokémon trên thanh Nearby, mỗi con ở đâu, và cooldown còn bao lâu. Đây là câu trả lời chứ không phải ước lượng: không ngưỡng, không căn chỉnh, và không bị nhiễu H.264 làm mất sprite nhỏ.
- Một lần đọc tốn khoảng 1,6 giây so với 25 ms của một ảnh chụp, nên chỉ dùng ở những chỗ vốn đã chấp nhận trả giá cho một câu trả lời dứt khoát — không bao giờ dùng để quét liên tục.
- Bật/tắt bằng cài đặt **Đọc overlay PGSharp**.

### Không ném bóng vào bản đồ, không bấm nhầm ra ngoài thanh

- **Encounter phải có hai tín hiệu độc lập**: nút chọn bóng và nút camera AR. Nút chọn bóng hay báo ma ngay sau khi Flee khiến bot ném thẳng vào bản đồ; nút camera thì hay sót encounter trên cảnh cháy sáng. Hai kiểu lỗi khác nhau nên đòi cả hai sẽ cắt được cái ma mà không rước cái sót.
- Sau lần xác nhận đầu, **vị trí nút chọn bóng được ghi nhớ** và các lần nhận sau phải nằm gần đó — cái ma đo được cách tới 120 px.
- **Không bao giờ bấm vào thanh bên khi chưa chứng minh được thanh đang hiện.** Trước đây ở chế độ ô cố định không có gì kiểm tra, nên một ô "có Pokémon" trong khi thanh đang ẩn thực chất là bản đồ lộ ra phía sau, và cú bấm rơi xuống bản đồ.
- Hộp thoại **"Stop AutoWalk?"** mà PGSharp bật lên khi bị bấm nhầm vào bản đồ nay được nhận ra theo hình dạng nút và trả lời **CANCEL**, thay vì chặn cứng cả luồng.

### Giãn nhịp bắt để giữ an toàn tài khoản

- Mỗi cú bấm Nearby là một lần dịch chuyển người chơi, nên bắt nhanh hết mức màn hình cho phép đồng nghĩa với một tốc độ di chuyển mà game không chấp nhận. Sau khi sửa được lỗi stream, một vòng rút từ ~52 giây xuống ~2,7 giây và **cooldown bắt đầu nổi lên ngay**.
- Bot **giữ một khoảng cách tối thiểu giữa hai lần bắt**, và ở nơi đọc được overlay thì **ngồi chờ hết cooldown** PGSharp báo thay vì cố bắt xuyên qua.

### Stream tự hồi phục

- Một lần khởi động stream không ra khung hình trước đây bị hiểu là máy từ chối kích thước thu nhỏ, và kích thước đó bị tắt cho cả phiên chạy. Suy luận này sai: adbd khởi động lại, hay bất cứ thứ gì chiếm mất khe screenrecord duy nhất của máy, đều trông y hệt.
- Khi dính lỗi đó, stream **không bao giờ trở lại**: mọi khung hình đều rơi xuống hết 5 giây timeout cộng một lần chụp riêng, và một vòng bắt ~2,7 giây kéo thành ~52 giây.
- Nay bot **đổi qua đổi lại giữa hai kích thước** thay vì chốt cứng một cái, nên kích thước máy thật sự hỗ trợ luôn được tìm lại.

### Nhanh hơn

- **Tìm ngôi sao menu: 619 ms xuống 11,6 ms.** Vị trí ngôi sao trước đây được dò lại từ đầu mỗi lần nhìn, trên toàn khung 1220x2712. Nay nhớ vị trí lần trước và soi quanh đó trước; trượt thì mới quét rộng lại và học lại.
- **Chặn vòng lặp căn chỉnh 3,07 giây.** Lượt căn chỉnh chỉ được đánh dấu xong khi đạt điểm ≥ 0,82, nên một ngôi sao bị che, bị thu gọn, hoặc đơn giản là bản PGSharp này vẽ khác đi sẽ tính 3,07 giây vào **mọi vòng** cho tới hết phiên, không có cài đặt nào tắt được. Nay giới hạn số lần thử; bỏ cuộc là an toàn vì không khóa được vốn đã là đường lui có sẵn.
- **Chờ tại chỗ khi giãn nhịp.** Khoảng nghỉ giữa hai lần bắt trước đây được trả góp từng giây một, mà mỗi giây lại chạy lại toàn bộ phần đầu vòng — chụp màn hình, quét popup, kiểm tra cooldown, kiểm tra hết bóng. Đứng yên 3 giây mặc định tốn ba lần phần đầu thay vì một. Popup vẫn được dọn trong lúc chờ, và Dừng/Tạm dừng vẫn ăn ngay.

### Cài đặt mới: nhóm "Nhịp bắt & an toàn tài khoản"

- **Khoảng cách tối thiểu giữa 2 lần bắt** — nhịp giữ cho tốc độ di chuyển ngầm hiểu vẫn hợp lý.
- **Chờ giữa cú bấm đơn và bấm kép** trên một ô.
- **Tôn trọng cooldown** PGSharp báo (tự mờ đi khi tắt đọc overlay, vì cooldown lấy từ overlay).
- **Đọc overlay PGSharp** để kiểm tra Nearby chắc chắn hơn.
- **Ghi thời gian từng bước** để gỡ lỗi — không bao giờ tự bật, vì nó sẽ phình `timing.log` mãi.

### Khởi động một chạm

- Thêm `KhoiDong.bat`: lần đầu tự tạo môi trường, tự cài thư viện nếu thiếu, rồi mở giao diện không kèm cửa sổ đen. Mọi lỗi đều báo bằng tiếng Việt kèm việc cần làm, thay vì đổ ra một đống traceback.

---

## English

### No more idling in front of a full Nearby bar

- **Scans every slot on the Nearby bar**, not just the first. With a calibrated fixed slot the lower ones were never looked at, so a bar whose top slot happened to be empty read as an empty bar while catchable Pokémon sat below it.
- **Judges a slot by brightness range** (98th minus 20th percentile) instead of standard deviation. The old measure fails on a night scene — a dark sprite on a dark sidebar spreads little. Measured over 37 slots on a 1220x2712 MuMu, a night Combee scores 17.9 against map clutter at 27.9, so no threshold on it is right.
- **Corroborates a sighting over a time window** rather than over consecutive frames, so one smeared stream frame no longer wipes the evidence and leaves the bot idle in front of a full bar.
- Before finally declaring the bar empty, it re-reads it on a one-shot capture and on **PGSharp's own view tree**.

### Reading the PGSharp overlay directly

- PGSharp draws its overlay as real Android views, so the view tree **states outright** how many Pokémon sit on the Nearby bar, where each one is, and how long the current cooldown has left. That is an answer rather than an estimate: no threshold, no calibration, and immune to the H.264 smear that hides a small sprite from the pixel path.
- A dump costs ~1.6 s against ~25 ms for a screenshot, so it is strictly for places that already pay for a decisive answer, never for polling.
- Toggled by the **Read the PGSharp overlay** setting.

### No throwing at the map, no taps landing off the bar

- **An encounter now requires two independent signals**: the ball selector and the AR camera button. The selector's failure is a phantom just after a Flee, which had the bot throwing at the map; the camera button's is missing a real encounter on a washed-out scene. Different failure modes, so demanding both cuts the phantom without inheriting the miss.
- Once confirmed, **the selector's position is remembered** and later detections must land near it — the phantom was measured 120 px away.
- **Never taps the sidebar without proving it is there.** In fixed-slot mode nothing checked, so a slot reading occupied while the bar was hidden was really the map showing through, and the tap went to the map.
- PGSharp answers a map tap with its **"Stop AutoWalk?"** dialog, which used to block the flow until dismissed. It is now recognised by the shape of its buttons and answered with **CANCEL**.

### Pacing the catches for account safety

- Each Nearby tap moves the player, so catching as fast as the screen allows implies a speed the game rejects. Once the stream was fixed a cycle went from ~52 s to ~2.7 s and **cooldowns began immediately**.
- The bot now **holds a floor between encounters**, and where the overlay is readable **sits out the cooldown** it reports rather than catching through it.

### The screen stream recovers itself

- A launch that produced no frames was taken as proof the device rejected the reduced size, and that size was then disabled for the rest of the run. The inference is wrong: adbd restarting, or anything else claiming the device's single screenrecord slot, looks identical from here.
- When it happened **the stream never came back**: every frame fell through the full 5 s timeout plus a one-shot capture, and a ~2.7 s catch cycle took ~52 s.
- It now **alternates between the two sizes** instead of latching, so whichever size the device actually supports is always rediscovered.

### Faster

- **Menu-star search: 619 ms down to 11.6 ms.** The star's position was re-derived from scratch on every look, over the whole 1220x2712 frame. It now caches the last hit and re-checks a box around it first; a miss falls back to the full search and re-learns.
- **The 3.07 s calibration sweep is capped.** The sweep was only marked done on a score ≥ 0.82, so a star that is covered, collapsed, or simply drawn differently by this PGSharp build charged 3.07 s to **every cycle** for the rest of the run, with no setting able to switch it off. Giving up is safe because not locking is already the documented fallback.
- **The pacing floor is held in place.** It used to be served a second at a time, and each second re-paid the whole cycle preamble — screenshot, popup sweep, cooldown check, out-of-balls badge — so standing still for the default 3 s floor cost three full preambles instead of one. Popups are still drained during the hold, and Stop and Pause are still honoured.

### New settings: "Pacing & account safety"

- **Minimum gap between catches** — the pacing that keeps the implied travel speed plausible.
- **Gap between the single tap and the double tap** on a slot.
- **Respect the cooldown** PGSharp reports (greyed out when the overlay read is off, since the cooldown comes from the overlay).
- **Read the PGSharp overlay** for a surer Nearby check.
- **Per-step timings** for debugging — never persisted as on, since it would grow a `timing.log` forever.

### One-click launcher

- Adds `KhoiDong.bat`: creates the environment on first run, installs the requirements if they are missing, then opens the GUI with no console window left behind. Every failure path says what to do next in Vietnamese rather than dumping a traceback.
