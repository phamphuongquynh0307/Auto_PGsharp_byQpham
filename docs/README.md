# Website giới thiệu (GitHub Pages)

Trang landing page song ngữ Việt–Anh của Auto Catch Pokémon cho PGSharp. Chỉ gồm HTML, CSS và JavaScript thuần: **không cần cài đặt hay build**, sửa file rồi push lên GitHub là xong.

## Bật GitHub Pages (làm một lần)

1. Push thư mục `docs/` lên nhánh `master`.
2. Trên GitHub: **Settings → Pages → Build and deployment**.
3. **Source**: *Deploy from a branch* · **Branch**: `master` · thư mục `/docs` → **Save**.
4. Sau 1–2 phút, trang có tại `https://phamphuongquynh0307.github.io/Auto_PGsharp_byQpham/`.

Nếu dùng tên miền khác, thay URL trên ở: `assets/js/data.js` (`siteUrl`), các thẻ `<meta>`/`<link rel="alternate">` trong `index.html`, `robots.txt` và `sitemap.xml`.

Xem thử trên máy: mở thẳng `index.html` bằng trình duyệt. Khi mở kiểu `file://`, trình duyệt chặn font tự host nên chữ hiển thị bằng font hệ thống; trên GitHub Pages font Be Vietnam Pro tải bình thường.

## Cấu trúc

```text
docs/
├── index.html                 Khung trang, metadata SEO / Open Graph
├── favicon.svg, apple-touch-icon.png, og-image-vi.png, og-image-en.png
├── robots.txt, sitemap.xml, .nojekyll
└── assets/
    ├── css/styles.css         Toàn bộ giao diện (màu nằm ở :root)
    ├── css/fonts.css          Font Be Vietnam Pro tự host (assets/fonts)
    ├── js/locales/vi.js       Toàn bộ chữ tiếng Việt
    ├── js/locales/en.js       Toàn bộ chữ tiếng Anh
    ├── js/data.js             Link tải, thứ tự tính năng / chế độ / FAQ / ảnh
    ├── js/icons.js            Icon SVG (Lucide, Simple Icons)
    ├── js/app.js              Đổi ngôn ngữ, tabs, FAQ, gallery, lightbox
    └── img/guide/*.webp       Ảnh hướng dẫn đã nén
```

## Sửa nội dung thường gặp

- **Sửa chữ**: sửa cùng một khóa trong cả `vi.js` và `en.js`. Viết `**đậm**` hoặc `` `mã` `` để định dạng. Nếu hai file lệch khóa, Console của trình duyệt sẽ cảnh báo.
- **Thêm câu hỏi FAQ**: thêm `id` vào mảng `faq` trong `data.js`, rồi thêm `faq.items.<id>` (`q` và mảng đoạn `a`) vào cả hai file locale.
- **Thêm tính năng**: thêm `{ id, icon }` vào `features` trong `data.js` và `features.items.<id>` vào hai file locale. Tên icon lấy từ `icons.js`.
- **Đổi link tải**: sửa `links` trong `data.js`.
- **Cập nhật ảnh hướng dẫn**: xuất ảnh sang WebP ở hai chiều rộng 480 px và 1024 px (ví dụ bằng https://squoosh.app), đặt tên `<tên>-480.webp` và `<tên>-1024.webp` trong `assets/img/guide/`. Ảnh mới thì thêm vào mảng `gallery` trong `data.js` và thêm `gallery.items.<id>` (`caption`, `alt`) vào hai file locale.

## Ngôn ngữ

Thứ tự chọn ngôn ngữ: tham số `?lang=vi` / `?lang=en` trên URL → lựa chọn đã lưu (localStorage) → ngôn ngữ trình duyệt → mặc định tiếng Việt. Khi đổi ngôn ngữ, trang cập nhật ngay nội dung, `<html lang>`, tiêu đề, meta description và Open Graph mà không tải lại.
