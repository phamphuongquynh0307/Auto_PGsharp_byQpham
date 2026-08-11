# Discord Coord Collector (Edge)

[Tải extension v0.3.0](https://github.com/phamphuongquynh0307/Auto_PGsharp_byQpham/releases/latest/download/discord-coord-collector-v0.3.0.zip)

Tiện ích Edge chạy tuần tự:

1. Tìm link `coord.pokedex100.com` trong Discord Web.
2. Xếp link mới nhất lên trước và chỉ mở một trang coord tại một thời điểm.
3. Đọc trực tiếp giá trị tọa độ trong ô HTML của trang Pokedex100.
4. Lưu cục bộ trong bộ nhớ của tiện ích, đóng tab và xử lý link kế tiếp.
5. Tự gửi coord sang app desktop.

Phiên bản hiện tại: **0.3.0**. Popup có nút đổi giữa **Bắt đầu** và **Tắt**. Tab tạm được tự đóng cả khi lấy thành công lẫn khi trang hết hạn/
không đọc được coord. Các trang yêu cầu Bronze/donor role mà tài khoản không có sẽ được nhận diện,
đóng ngay và bỏ qua vĩnh viễn trong lượt thu hiện tại.

Popup cũng cho phép dán một danh sách `latitude,longitude` từ clipboard rồi nhập tối đa 2.000 coord mỗi lần.
Các coord nhập theo cách này có chú thích mặc định **Từ Discord Pokedex100**, được lưu vào lịch sử và gửi sang
app desktop giống coord lấy tự động. Nút **Xóa dữ liệu cũ** xóa lịch sử, hàng chờ của extension và hàng chờ
coord trong app desktop sau khi người dùng xác nhận.

Collector chỉ nhận đúng anchor có nhãn **Click for Coords**; các link **Donor** và **Support Us**
trong cùng message bị bỏ qua dù chúng có dùng chung domain Pokedex100.

Chỉ tab Discord Web đang active trong cửa sổ Edge hiện tại được theo dõi. Link gửi từ tab Discord
khác bị từ chối, tránh lấy nhầm channel khi người dùng mở nhiều tab Discord.

Mỗi coord mới được gửi tới app desktop qua `http://127.0.0.1:8765/coords`. Hãy mở app desktop
trước khi bấm **Bắt đầu** để coord được đưa thẳng vào hàng đợi tạm của chế độ
**Shundo từ Discord Coord**.

Collector không lấy toàn bộ lịch sử đang hiển thị. Khi bấm **Bắt đầu**, các link hiện tại được ghi
nhớ làm mốc; mỗi đợt Discord chèn message mới chỉ coord mới nhất/đầu tiên được xử lý. Mỗi lần
bấm **Bắt đầu**, hàng chờ và trạng thái phiên cũ được tự làm sạch nhưng lịch sử coord đã lấy vẫn giữ lại.

## Cài thử trên Microsoft Edge

1. Mở `edge://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked**.
4. Chọn thư mục `discord-coord-collector` này.
5. Đăng nhập Pokedex100 và Discord Web trong cùng profile Edge.
6. Mở kênh Discord cần theo dõi tại `https://discord.com/channels/...`.
7. Bấm biểu tượng **Discord Coord Collector** rồi chọn **Bắt đầu**.

Khi bấm **Bắt đầu**, Collector lấy trước ba coord mới nhất đang thấy để làm bộ đệm. Sau đó nó
dừng lấy thêm. Mỗi khi app desktop xác nhận chấm xong một Pokémon, Collector mới lấy thêm đúng
một coord. Các bài xuất hiện trong lúc chưa có lượt được giữ trên Discord và chọn khi app cần.

## Dữ liệu

Dữ liệu lịch sử nằm trong `chrome.storage.local` của profile Edge. Hàng chờ tạm được làm sạch
mỗi lần bấm **Bắt đầu**.

## Giới hạn bản thử

- Tự lấy link yêu cầu dùng Discord Web trong Edge; Discord desktop không cho extension đọc DOM.
- Trang Pokedex100 phải đăng nhập sẵn và phải hiện coord trong vòng 20 giây.
- Discord chỉ tải các message đang ở trong vùng đã cuộn tới; extension không tự cuộn toàn bộ lịch sử.
- Hãy tuân thủ quy định của Discord server và trang Pokedex100 về việc sử dụng tọa độ.
