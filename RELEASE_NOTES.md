# v1.4.21

## Tiếng Việt

### Không còn báo "Hết Poké Ball" khi túi vẫn còn bóng

- Bot từng báo hết bóng, thoát encounter và đi nạp 10 phút trong khi túi còn 199 Poké Ball,
  532 Great Ball và 186 Ultra Ball.
- Nguyên nhân: quả bóng ở chỗ ném thỉnh thoảng tự nghiêng, che mất nút tròn xám ở giữa hơn
  1 giây (3/15 ảnh chụp thật). Bot cũ chờ 2 giây không thấy nút đó là kết luận hết bóng.
- Giờ trước khi báo hết bóng, bot bấm nút chọn bóng ở góc phải dưới. Còn loại bóng nào thì chọn
  loại đó và ném tiếp, nên hết bóng đỏ sẽ tự dùng Great/Ultra. Chỉ báo hết bóng khi bảng chọn
  không còn gì.
- Mỗi lần báo hết bóng, bot lưu ảnh `no-balls.png` cạnh `timing.log` để dễ kiểm tra.
- **317 test đạt**.

---

## English

### No more "out of Poké Balls" with a full bag

- The routine fled and paused to refill with 199 Poké, 532 Great and 186 Ultra Balls in hand.
- The resting ball periodically tilts and hides its grey centre hub for over a second (3 of 15
  live captures), and a 2s missing hub was treated as an empty bag.
- Before declaring the bag empty, the bottom-right ball picker is now opened and the first
  offered ball type is loaded, so running out of one type moves on to the next.
- Each empty-bag decision saves `no-balls.png` next to `timing.log`.
- **317 tests pass**.

---

# v1.4.19

## Tiếng Việt

### Tap Nearby bị mất: thử lại sau 2 giây thay vì ~6 giây

- Quay màn hình lúc bot chạy cho thấy: sau khi bắt, PGSharp có thể xếp lại danh sách Nearby thêm
  một đợt khoảng 0,7 giây sau khi map hiện lại. Double-tap rơi đúng lúc đó thì mất, map đứng yên.
  Bot cũ chờ hết ~5,8 giây mới thử lại.
- Mỗi cú tap mở được encounter đều làm màn hình loé trắng trong khoảng 1 giây. Giờ bot so độ sáng
  với frame ngay trước tap: sau 2 giây mà map vẫn y nguyên, không loé, thì tap lại luôn.
- Không tap Nearby khi màn hình đang loé trắng, để không chạm vào encounter vừa mở muộn.
- **309 test đạt**.

---

## English

### Lost Nearby taps retried after 2s instead of ~6s

- A screen recording showed PGSharp re-sorting the Nearby list a second time ~0.7s after the map
  returns; a double-tap landing on that re-sort is lost while the map stays unchanged.
- Every accepted tap flashes white within about a second. A map whose brightness has not changed
  2s after the tap is now retried immediately, and no Nearby tap is sent during the flash.
- **309 tests pass**.

---

# v1.4.18

## Tiếng Việt

### Hết "chậm 1 nhịp" khi chuyển sang con kế tiếp

- Đo trên `timing.log` thật: tap Nearby gửi chưa tới 0,3 giây sau khi thoát encounter thì ~70%
  không mở được gì, và mỗi lần hụt mất trọn ~6 giây chờ encounter rồi mới thử lại. Từ 0,6 giây trở
  lên chỉ còn ~15%, ngang một cú tap bình thường.
- Chốt chờ Nearby làm mới sau khi bắt được áp dụng cho **cả** chế độ chỉ Nearby, và mức sàn tăng
  từ 0,25 lên 0,6 giây. Vẫn đi tiếp ngay khi 2 frame cho thấy slot đã đổi; trần 1,2 giây giữ nguyên.
- Tốn thêm ~0,4 giây mỗi con nhưng bỏ được phần lớn các lần hụt 6 giây.
- **307 test đạt**, không có lỗi.

---

## English

### Fix the "one beat late" start on the next Pokémon

- Measured from the live `timing.log`: a Nearby tap sent <0.3s after the encounter closed opened
  nothing ~70% of the time, each miss paying the full ~6s encounter timeout; at >=0.6s the miss
  rate falls to ~15%, the same as an ordinary tap.
- The post-catch Nearby refresh guard now runs in Nearby-only mode too, with its floor raised from
  0.25s to 0.6s. It still proceeds as soon as two frames show the row changed; the 1.2s ceiling
  is unchanged.
- **307 tests pass**.

---

# v1.4.17

## Tiếng Việt

- Chế độ chỉ Nearby bỏ bước chờ Nearby làm mới sau khi bắt. Bản này làm tap con kế tiếp hụt
  nhiều hơn và đã được thay bằng v1.4.18.

---

## English

- Nearby-only mode skipped the post-catch refresh wait. This raised the miss rate of the next
  tap and is superseded by v1.4.18.

---

# v1.4.16

## Tiếng Việt

### Chỉ kiểm tra cooldown khi bật nguồn Feed

- Khi **Nearby hết Pokémon: lấy 1 con từ Feed** đang tắt, vòng bắt bỏ hẳn bước kiểm tra cooldown:
  không UI dump định kỳ, không chờ deadline cũ và tiếp tục bắt Nearby liên tục.
- Khi Feed được bật, bảo vệ cooldown vẫn hoạt động đầy đủ sau teleport. Tùy chọn cooldown trên giao
  diện được ghi rõ là của Feed và tự khóa khi Feed đang tắt.
- Hạ ngưỡng nhận diện `0:00:00` từ `0.94` xuống `0.88` để chịu được frame stream nửa độ phân giải;
  kiểm tra riêng lòng của cả năm số 0 vẫn chặn timer khác 0 như `0:00:08`.

### Kiểm chứng

- **306 test đạt**, không có lỗi; 21 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.
- Có test hồi quy xác nhận Nearby-only trả về ngay cả khi routine đang giữ một deadline cooldown.

---

## English

### Cooldown checks belong only to the optional Feed source

- Nearby-only catching no longer performs periodic cooldown dumps or waits on a stale deadline.
- Enabling Feed retains full post-teleport cooldown protection; the UI now exposes that dependency.
- The exact-zero visual threshold tolerates half-resolution stream frames while retaining the
  five-hole guard against non-zero timers.
- **306 tests pass** (21 desktop-only tests skipped).

---

# v1.4.15

## Tiếng Việt

### Bắt nhanh hơn nhưng vẫn giữ chốt an toàn cooldown

- Khi màn hình đã chắc chắn là map hoặc encounter, quét popup nặng được giới hạn còn một lần mỗi
  8 giây; màn hình không xác định vẫn được quét ngay để không bỏ sót hộp thoại chặn.
- Nhận diện riêng đúng chuỗi cooldown `0:00:00` từ frame hiện tại trong khoảng 2 ms, tránh UI dump
  Android vốn mất 2–7 giây. Timer khác 0, thiếu nét hoặc ảnh không đủ rõ vẫn quay về UI dump cũ.
- Bộ nhận diện zero kiểm tra cả năm lòng số `0`, nên timer gần giống như `0:00:08` không thể được
  xem nhầm là đã hết cooldown chỉ vì điểm tương quan toàn chuỗi còn cao.
- Cú tap Nearby bị bỏ qua được xác nhận bằng ba frame có cùng fingerprint sau cửa sổ chuyển màn
  hình 3 giây, thay vì luôn chờ hết timeout và chụp ADB chậm. Lần thử lại dùng một primer ADB độc
  lập và tăng nhẹ khoảng nghỉ để giảm khả năng scrcpy tiếp tục làm rơi tap.

### Kiểm chứng

- **303 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.
- Fast-path cooldown đạt khoảng **1,8 ms** trên ảnh thật 1220×2712; ảnh nén quá mờ bị từ chối và
  tự động dùng đường đọc an toàn cũ.

---

## English

### Faster catch loop with cooldown safety preserved

- Heavy popup recognition is rate-limited on known map/encounter frames while unknown screens are
  still checked immediately.
- An exact visual `0:00:00` fast path avoids the 2–7 second Android hierarchy dump. Any non-zero,
  incomplete, or uncertain timer falls back to the existing authoritative reader.
- Rejected Nearby taps are confirmed from three unchanged slot fingerprints after the measured
  transition window; retries use an independent ADB primer with a small adaptive delay.
- **303 tests pass** (19 desktop-only tests skipped).

---

# v1.4.14

## Tiếng Việt

### Không nhầm icon trạng thái thành Special Background

- Sửa ca shiny Gible `IV100 15/15/15` không có Background nhưng bot vẫn báo có và tạm dừng.
- Nguyên nhân là biểu tượng trạng thái màu trắng sau dấu shiny cao hơn rộng, chỉ có hai cạnh giống
  khung nhưng detector cũ vẫn cho qua. Badge Background giờ phải gần vuông và có đủ bốn cạnh;
  trường hợp ảnh bị thu nhỏ mất một cạnh chỉ được nhận khi ba cạnh còn rõ và phần icon đủ đặc.
- Giữ hỗ trợ các artwork Background khác nhau giữa máy/sự kiện: detector vẫn kiểm tra hình học
  của khung, không đóng đinh hình vẽ bên trong.
- Đối chiếu trực tiếp hai ảnh người dùng cung cấp: ảnh có badge vẫn được nhận, Gible không badge
  bị từ chối.

### Kiểm chứng

- **293 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.
- Thêm test hồi quy bằng đúng hình dạng threshold của biểu tượng gây dừng nhầm.

---

## English

### Do not mistake an encounter-status glyph for a Special Background

- Fixes a shiny `IV100 15/15/15` Gible without a Background being reported as a target.
- Background candidates must now remain square and retain a real four-sided frame. A compressed
  three-sided badge is accepted only when its enclosed artwork is sufficiently dense.
- Detection remains artwork-independent, and the reported false-positive shape has a dedicated
  regression test.

---

# v1.4.13

## Tiếng Việt

### Đọc đúng IV khi PGSharp không đưa chữ vào UI dump

- Sửa trường hợp encounter hiện rõ IV như `11/7/15` nhưng log vẫn báo **Không đọc được IV**.
  Một số bản PGSharp vẽ dòng Encounter IV trực tiếp lên màn hình và không tạo node chữ Android,
  nên UI dump dù hợp lệ vẫn không có dữ liệu để đọc.
- Thêm bộ đọc ảnh CRNN chạy hoàn toàn cục bộ và đóng gói sẵn trong EXE. Bộ đọc chỉ tìm ba cụm
  số quanh hai dấu `/`, giới hạn từng chỉ số trong 0–15 và đối chiếu thêm IV% khi nhìn thấy để
  giảm khả năng nhận nhầm nền hoặc icon.
- Vẫn ưu tiên UI dump vì nhanh; OCR chỉ chạy khi đường đó không có IV. Nếu cả hai chưa đủ chắc,
  bot tiếp tục giữ encounter thay vì tự thoát nhầm Pokémon.
- Đã kiểm tra trực tiếp ảnh phản hồi `IV73 11/7/15`: kết quả đọc là **11/7/15**.

### Kiểm chứng

- **292 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.
- Có test mới cho IV bất kỳ, từ chối chuỗi thiếu hai dấu phân cách và fallback khi UI dump rỗng.

---

## English

### Exact IV OCR when PGSharp exposes no accessibility text

- Fixes visible triplets such as `11/7/15` being reported as unreadable when PGSharp paints the
  Encounter IV pill without Android text nodes.
- Adds a bundled, fully local CRNN fallback scoped to the three slash-delimited stat fields. It
  validates each value as 0–15 and uses the displayed IV percentage as extra consistency evidence.
- Accessibility text remains the fast path. An uncertain result still keeps the encounter open
  instead of fleeing a potentially matching Pokémon.

---

# v1.4.12

## Tiếng Việt

### Background là điều kiện cuối sau Shiny và đúng IV

- Sửa đúng thứ tự lọc theo yêu cầu: **Shiny → đúng cả ba IV mục tiêu → có Special Background**.
- Khi bật **Yêu cầu đúng IV phải có Special Background**, bot chỉ soi icon Background sau khi đã
  xác nhận IV khớp. Shiny sai IV không chạy detector Background.
- Shiny đúng IV nhưng thiếu Background được xem là chưa đạt đủ mục tiêu và xử lý theo lựa chọn
  Thoát/Tạm dừng dành cho shiny chưa đạt; log và Discord nói rõ lý do thiếu Background.
- Giữ khả năng nhận mọi artwork Background khác nhau giữa máy/sự kiện và tự chuyển setting đã
  lưu từ v1.4.11 sang ngữ nghĩa mới.

### Kiểm chứng

- Có test riêng cho ba nhánh: sai IV không soi Background, đúng IV + Background thì giữ, và đúng
  IV nhưng thiếu Background thì không xem là đạt đủ mục tiêu.

---

## English

### Background is the final condition after shiny and exact IV

- Corrects the filter order to **Shiny → exact three-stat target IV → Special Background**.
- With the Background requirement enabled, its detector runs only after the IV target matches.
- A matching-IV shiny without a Background follows the configured non-target shiny action, with
  explicit local and Discord messages; v1.4.11's saved checkbox value migrates automatically.

---

# v1.4.11

## Tiếng Việt

### Dừng khi shiny có Special Background

- Thêm tùy chọn **Dừng khi shiny có Special Background (mọi icon)** trong chế độ Chấm shiny theo
  IV, áp dụng cho cả nguồn Feed và Discord Coord. Tùy chọn mặc định tắt để giữ nguyên hành vi cũ.
- Background là một mục tiêu độc lập với bộ IV: khi thấy icon ở cuối dòng Encounter IV, bot giữ
  encounter và Tạm dừng/Dừng hẳn theo lựa chọn đang dùng cho IV mục tiêu.
- Không đóng đinh artwork của một sự kiện. App ưu tiên tên view của PGSharp, rồi nhận diện khung
  vuông của badge; vì vậy các máy săn những bộ icon Background khác nhau không cần cài ảnh mẫu.
- Tín hiệu ảnh phải lặp lại trên hai ảnh nét trước khi được chấp nhận, tránh nhầm dấu shiny hoặc
  chữ số thành Background. Thông báo Discord kèm ảnh ghi rõ kết quả Special Background.

---

## English

### Stop on a shiny with any Special Background

- Adds an opt-in **Stop on a shiny with any Special Background icon** setting to both Feed and
  Discord-coordinate shiny modes. It defaults off, preserving existing behaviour.
- A Background is a target independently of the selected IV triplet and obeys the existing
  pause/stop action while keeping the encounter open.
- Detection uses PGSharp's semantic view hint first, then the badge's framed-square geometry,
  so phones hunting different event artwork do not need separate image templates.
- Vision evidence must agree on two crisp frames to reject shiny glyphs and text, and Discord
  alerts identify the Special Background result explicitly.

---

# v1.4.10

## Tiếng Việt

### Đọc IV Shiny ổn định hơn

- Cây giao diện Android giờ được đọc thẳng trong một lệnh ADB, không còn dùng lại file tạm cũ
  khi lần đọc mới thất bại giữa lúc encounter đang chuyển động.
- Bộ đọc IV nhận thêm nhiều cách PGSharp hiển thị ba chỉ số: dấu phân cách khác nhau, nhãn
  ATK/DEF/HP, `content-desc`, ba ô text không có id và các tên resource ở phiên bản PGSharp cũ/mới.
- Nếu vẫn không đọc chắc chắn, app tiếp tục giữ encounter và tạm dừng; không bỏ nhầm Pokémon.

### Feed và Nearby tự phục hồi khi nhận diện ảnh hụt

- Nhận diện ảnh vẫn là đường nhanh. Khi stream bị nhòe hoặc nền xuyên qua sidebar làm mất mẫu
  RSS/@, app dùng chính ListView Android của PGSharp để lấy tọa độ hàng đang có Pokémon.
- App nhận ra cả một sidebar đang trống, phân biệt Feed với Nearby theo đúng cột và từ chối bấm
  nếu chỉ có một thanh không xác định — tránh đổi độ ổn định lấy rủi ro teleport/bấm nhầm.
- Tùy chọn **Đọc overlay PGSharp** giờ áp dụng cho cả chế độ Chấm shiny theo IV.

### Kiểm chứng

- **283 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.
- Đã đối chiếu trực tiếp trên thiết bị 1220×2712: đường UI nhận đúng Feed có 6 mục và Nearby trống
  ở hai phía khác nhau.

---

## English

### More reliable shiny IV reads

- The Android hierarchy is now returned directly by one ADB command, preventing a failed dump
  during an encounter transition from serving an old temporary map hierarchy.
- The IV parser accepts more PGSharp representations: alternate separators, ATK/DEF/HP labels,
  content descriptions, three anonymous text children, and resource names used by older/newer
  PGSharp builds.
- An IV that still cannot be proven keeps the encounter open and pauses as before; the app never
  risks fleeing the requested Pokémon.

### Feed and Nearby recover from missed image matches

- Image detection remains the fast path. If stream smear or a translucent map background hides
  the small RSS/@ templates, the app falls back to PGSharp's native Android ListViews and uses
  their exact occupied-row coordinates.
- Empty sidebars are represented too. Feed and Nearby are selected by the correct column, and an
  ambiguous lone sidebar is never tapped.
- **Read PGSharp overlay** now controls this fallback in the exact-IV shiny mode as well.

### Verification

- **283 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is
  available.
- A live 1220×2712 device check correctly separated a six-entry Feed from an empty Nearby bar on
  opposite sides of the screen.

---

# v1.4.9

## Tiếng Việt

### Chạy lâu ổn định hơn

- Mỗi lần Android `screenrecord` tự khởi động lại, app giờ đóng hẳn bộ giải mã video, pipe và
  process cũ thay vì để thread/handle tích tụ theo thời gian.
- Giới hạn bộ giải mã còn 2 thread để dành CPU cho nhận dạng màn hình; các phiên chạy nhiều giờ
  không còn chậm dần sau hàng chục lần stream khởi động lại.

### Nhận dạng nhanh hơn mà vẫn giữ đường lui an toàn

- Tìm template trong một vùng nhỏ giờ crop ảnh trước khi đổi sang grayscale và tái sử dụng trực
  tiếp score map, giảm chuyển đổi pixel và cấp phát bộ nhớ không cần thiết.
- Bộ dò nút đóng vẫn thử scale đã căn ở mọi chu kỳ, còn lượt quét rộng 17 scale được giới hạn một
  lần mỗi giây. Popup lạ vẫn được bắt, nhưng map bình thường không còn trả thêm khoảng 90 ms ở
  từng vòng lặp.

### Có số liệu thật để sửa lệch trên máy khác

- Khi app đã đọc overlay PGSharp vì công việc sẵn có, app âm thầm đối chiếu tọa độ do ảnh nhận ra
  với tọa độ thật trong view Android cho Nearby, AutoWalk và nút CANCEL.
- Kết quả nằm trong `doi-chieu.log` và tự đi kèm gói **Xuất báo cáo lỗi**. Phần đo không thay đổi
  bất kỳ tọa độ bấm hay cache nào của phiên chạy, không tự chụp ảnh chậm khi stream mất, và tự
  dừng sau khi đủ mẫu để không tốn CPU mãi.

### Kiểm chứng

- **272 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.

---

## English

### More stable long-running sessions

- Every Android `screenrecord` relaunch now closes the previous video decoder, pipe, and process
  instead of accumulating threads and handles over time.
- The decoder is capped at two threads so screen recognition keeps the CPU it needs, preventing
  multi-hour sessions from slowing down after repeated stream restarts.

### Faster recognition with the safety net intact

- Region-based template searches now crop before grayscale conversion and reuse the score map
  directly, avoiding unnecessary full-frame work and memory allocations.
- Calibrated popup-close scales are still checked every cycle, while the expensive 17-scale safety
  sweep is limited to once per second. Unexpected popup sizes remain detectable without adding
  roughly 90 ms to every ordinary map pass.

### Real cross-device alignment evidence

- Whenever the app already reads the PGSharp overlay, it passively compares image-derived
  coordinates with Android view coordinates for Nearby, AutoWalk, and CANCEL controls.
- Results are stored in `doi-chieu.log` and included in **Export error report** bundles. Measurement
  never changes tap coordinates or detector caches, never buys a slow one-shot screenshot when
  the stream is unavailable, and stops after enough samples have been collected.

### Verification

- **272 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is
  available.

---

# v1.4.8

## Tiếng Việt

### Nhận dạng đa máy

- Điểm ném tự bám tâm quả bóng thật theo cấu trúc hub sáng + vòng đen, không còn phụ thuộc hoàn
  toàn vào tọa độ của máy mẫu; căn tay vẫn là override cuối cùng.
- AutoWalk dùng view Android của PGSharp khi template icon không khớp và nhận cả hai nhãn
  `AutoWalk`/`AW(Paused)`; vị trí và trạng thái hàng vì vậy không phụ thuộc DPI/font/icon theme.
- Hộp thoại Android phải được view tree xác nhận đúng nút `CANCEL/HỦY` trước khi bấm trên cấu hình
  mặc định, ngăn màn thông tin Pokémon bị nhầm thành hộp hai nút.
- Xem bot nhìn hiển thị tâm bóng/điểm ném thật và trạng thái AutoWalk đọc được bằng ảnh.
- Bổ sung profile emulator chuẩn tùy chọn `1220 × 2712 @ 480 dpi`; điện thoại thật không bị yêu cầu
  đổi độ phân giải.

### Bỏ hẳn việc tự bật Go Plus

- Pokémon GO thêm một nút tròn nữa vào dải icon mép phải có đúng hình dạng mà bộ dò Go Plus tìm
  (nắp đỏ nửa trên, tâm tối). Khi hết bóng, app dò trúng nút mới đó rồi **bấm vào** — tức là tự
  bật Go Plus lên. Go Plus bật thì PGSharp chặn mọi teleport, mà teleport là thứ Shundo và nguồn
  Feed sống bằng nó. App đang tự khoá chính mình, và Shundo sau đó dừng với thông báo
  *"Go Plus đang kết nối"*.
- Không có ngưỡng nào chữa được chuyện này: nút kia **trông thật sự giống** nút đang tìm. Nên bỏ
  hẳn phần tự bật Go Plus — cả ô tick *"Hết bóng: khởi động Go Plus sau AutoWalk"*, bộ dò và
  đường gọi nó.
- Nạp bóng giờ đi qua **quay PokéStop**, vốn đã có sẵn, không cần PGSharp key, và chỉ bấm vào thứ
  nó đã nhận diện chắc chắn là stop.
- App vẫn bấm CANCEL nếu gặp cảnh báo teleport thật của Go Plus — chỗ đó là an toàn tài khoản,
  không đụng tới.

### Shundo không còn dừng oan vì một hộp thoại lạ

- Trước đây bất kỳ hộp thoại hai nút nào ở giữa màn hình, có một nút CANCEL, cũng đủ để Shundo
  kết luận "Go Plus đang kết nối" và **dừng hẳn run**. Chứng cứ đó quá yếu so với kết luận: rất
  nhiều hộp thoại Android trông y như vậy.
- Giờ app vẫn bấm CANCEL (không bao giờ xác nhận một teleport đang bị cảnh báo) nhưng **chạy
  tiếp**. Chỉ đúng ảnh mẫu cảnh báo Go Plus, khớp trong vùng riêng của nó, mới được phép dừng run.

### Bot tự thoát khi kẹt

- Popup nào app chưa biết mặt thì trước đây bot đứng im đến khi có người phát hiện. Giờ khi màn
  hình không đọc được liên tục quá 12 giây, bot **tự bấm phím Back** — đúng thứ người thật làm.
  Không cần ảnh mẫu, không cần toạ độ, không phụ thuộc ngôn ngữ hay bản game, và người dùng
  không phải thao tác gì. Tối đa 8 giây một lần.
- Hai rào chắn cứng: **không bao giờ** bấm Back khi đang gặp Pokémon (mất con đó), và không bấm
  khi thanh Nearby đang hiện (đang ở map). Nếu lỡ rơi vào hộp "Thoát Pokémon GO?" thì đó là
  hộp thoại Android thật, phần xử lý sẵn có đã biết bấm CANCEL.
- Mỗi lần kẹt, app lưu một ảnh màn hình vào thư mục `stuck/` cạnh EXE. Popup gây kẹt thường xuất
  hiện lúc không ai ngồi canh; có ảnh thì báo lỗi được sau, không phải bắt đúng lúc.
- Tắt được ở Cài đặt (mục nâng cao) nếu không muốn app bấm Back.

### Sửa lỗi đọc nhầm hàng AutoWalk

- Khi cả hai icon hàng AutoWalk (`⊘` đang dừng và glyph đang chạy) cùng vượt ngưỡng, app giờ chọn
  cái **khớp cao hơn** thay vì cái được thử trước. Đo trên máy 1220×2712 thật: ảnh `⊘` ăn 0.72 ở một
  hàng menu bên cạnh trong khi hàng AutoWalk thật ăn 0.97 ở vị trí thấp hơn 100px — app đọc walk
  đang chạy thành đang dừng, bấm nhầm hàng ở mỗi chu kỳ Nearby trống, rồi chờ một icon `⊘` vốn
  chưa từng ở đó biến mất.

### Kiểm chứng

- **255 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test
  không có desktop Tk.

---

## English

### Better multi-device recognition

- Throwing now follows the detected center of the actual ball instead of relying entirely on
  coordinates captured from one device; manual alignment remains the final override.
- AutoWalk falls back to PGSharp's Android view data when icon templates differ and recognizes
  both `AutoWalk` and `AW(Paused)` labels across DPI, font, and icon-theme variations.
- Native Android dialogs must expose an exact `CANCEL/HỦY` button in the view tree before the
  default geometry-based handler taps them, reducing false positives on Pokémon detail screens.
- The vision preview now shows the detected ball center, throw point, and AutoWalk state.
- Documents an optional `1220 × 2712 @ 480 dpi` emulator support profile without requiring real
  phones to change their display configuration.

### Removed automatic Go Plus startup

- Pokémon GO added another round side control that genuinely resembles the disconnected Go Plus
  button. The old detector could tap that control, start Go Plus, and then block the teleports used
  by Shundo and Feed modes.
- Automatic Go Plus startup and its setting have therefore been removed. Out-of-ball recovery now
  relies on the existing PokéStop spinning path, which does not require a PGSharp key.
- Genuine Go Plus teleport warnings are still cancelled for account safety.

### Safer Shundo dialog handling

- A generic two-button dialog with a CANCEL button no longer permanently stops a Shundo run.
  The app cancels the dialog and continues; only the dedicated Go Plus warning template can mark
  teleporting as blocked.

### Automatic recovery from unknown screens

- After a screen remains unrecognized for 12 seconds, the bot sends a rate-limited Android Back
  command to dismiss unknown popups without depending on language, templates, or coordinates.
- Hard safety guards prevent Back from being pressed during a Pokémon encounter or on the map.
- Each recovery attempt saves a screenshot under `stuck/` for later diagnosis, and the watchdog
  can be disabled in advanced settings.

### Correct AutoWalk row selection

- When both running and paused icon templates clear their thresholds, the stronger match now wins,
  preventing the bot from tapping a neighboring row because a weaker paused-icon match happened
  to be checked first.

### Verification

- **255 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is
  available.

---

# v1.4.7

## Tiếng Việt

### Wireless Debugging ổn định hơn

- Chờ ADB xác nhận transport thật sự ở trạng thái `device` trước khi báo kết nối thành công; không còn vòng lặp “tự kết nối lại Wi-Fi” dù điện thoại đã online.
- Tuần tự hóa các lệnh `adb connect`, chấp nhận thông báo thành công từ cả stdout/stderr và thử lại ngắn khi transport còn `offline`.
- Tự thử lại mDNS trong thời gian giới hạn để bắt đúng cổng TLS mới khi Android vừa bật Wireless Debugging hoặc đổi cổng.
- Sau khi kết nối thành công, danh sách thiết bị và trạng thái GUI được cập nhật mà không tự khởi động thêm một reconnect cạnh tranh.

### Discord Coord Collector v0.3.3

- Chuyển bridge coord sang cổng riêng `127.0.0.1:8766`, hoàn toàn tách khỏi cổng ADB/Wireless Debugging đang xoay của điện thoại.
- Popup hiển thị rõ phiên bản extension, trạng thái kết nối và endpoint đang dùng.
- Extension tự chèn lại bộ quét vào tab Discord đã mở trước khi extension được reload; không còn đứng ở “Đang chờ link mới” chỉ vì content script cũ chưa được nạp lại.
- Reset session tạm khi nâng phiên bản và cải thiện đọc tọa độ từ input, text, thuộc tính `data-*` hoặc tham số URL của Pokedex100.
- Gói cài mới `discord-coord-collector-v0.3.3.zip` được đính kèm trực tiếp trong release.

### Kiểm chứng

- **238 test đạt**, không có lỗi; 19 test giao diện được bỏ qua đúng điều kiện khi môi trường test không có desktop Tk.
- Kiểm tra cú pháp toàn bộ JavaScript của extension và xác nhận manifest v0.3.3 chỉ dùng bridge `127.0.0.1:8766`.
- Xác nhận ADB thật nhận thiết bị Wireless Debugging ở trạng thái `device` sau kết nối.

---

## English

### More reliable Wireless Debugging

- Waits for ADB to report the transport as an actual `device` before declaring success, preventing endless Wi-Fi reconnect loops while the phone is already online.
- Serializes `adb connect` operations, accepts success output from stdout or stderr, and briefly retries while the transport is still `offline`.
- Performs bounded mDNS retries to discover a newly advertised or rotated Android TLS port.
- Refreshes the device list and GUI state after a verified connection without launching a competing reconnect worker.

### Discord Coord Collector v0.3.3

- Moves the coordinate bridge to dedicated port `127.0.0.1:8766`, fully separate from the phone's rotating ADB/Wireless Debugging port.
- Shows the extension version, connection state, and active endpoint in the popup.
- Automatically injects the scanner into Discord tabs that were already open when the extension was reloaded, preventing a false permanent “waiting for new links” state.
- Resets transient session state on extension upgrades and reads coordinates from inputs, visible text, `data-*` attributes, or Pokedex100 URL parameters.
- Includes the new `discord-coord-collector-v0.3.3.zip` package in the release.

### Verification

- **238 tests pass** with no failures; 19 GUI tests are skipped as expected when no Tk desktop is available.
- All extension JavaScript files pass syntax validation, and the v0.3.3 manifest uses only the dedicated `127.0.0.1:8766` bridge.
- A live ADB check confirms the Wireless Debugging transport reaches the `device` state after connection.
