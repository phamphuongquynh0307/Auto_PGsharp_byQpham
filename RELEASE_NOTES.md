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
