# v1.1.14

## Tiếng Việt

### Hotfix: Feed chỉ teleport một lần rồi chờ Nearby

- Khi bật **“Nearby hết Pokémon: lấy 1 con từ Feed”**, bot tap Feed đúng một lần rồi **đứng chờ ngay trong cùng luồng** cho tới khi Pokémon thật sự xuất hiện trên Nearby.
- Bỏ hoàn toàn đường timeout quay lại vòng chính — nguyên nhân khiến bot thấy Nearby vẫn trống và teleport liên tục qua các mục Feed kế tiếp.
- Trong lúc chờ, bot không quay lại nhánh Feed, không AutoWalk và không gửi thêm lệnh teleport.
- Mỗi 10 giây bot kiểm tra thêm cây giao diện PGSharp và một ảnh ADB nét để không bỏ sót Pokémon vì frame stream bị nhòe.
- Chỉ nút **Dừng** mới hủy trạng thái chờ. Sau khi Pokémon xuất hiện, bot chuyển sang bắt trên Nearby; mục Feed kế tiếp chỉ được mở khóa khi encounter đã xử lý xong.

### Kiểm thử

- 17 bài test đều đạt, bao gồm chuỗi nhiều frame Nearby trống trước khi Pokémon xuất hiện và xác nhận trong toàn bộ thời gian đó Feed chỉ nhận đúng một tap.

---

## English

### Hotfix: tap Feed once, then wait for Nearby

- With **“When Nearby is empty: take 1 Pokémon from Feed”** enabled, the bot taps Feed exactly once and **waits inside the same flow** until a Pokémon actually appears on Nearby.
- Removes the timeout path that returned to the main loop, saw Nearby still empty, and repeatedly teleported through subsequent Feed entries.
- While waiting, the bot cannot re-enter Feed, start AutoWalk, or send another teleport command.
- Every 10 seconds it additionally checks PGSharp's view tree and a crisp ADB screenshot so a smeared stream frame cannot hide the loaded Pokémon.
- Only **Stop** cancels the wait. Once the Pokémon appears, Catch handles it through Nearby; the next Feed entry remains locked until that encounter is complete.

### Tests

- All 17 tests pass, including multiple empty Nearby frames before the Pokémon appears and proof that only one Feed tap is sent throughout the wait.
