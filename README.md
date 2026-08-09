# Reels View Scanner

Tool desktop (PySide6) quét **view · mô tả · thumbnail** của 10 reel đầu mỗi
Facebook Page. Nhập danh sách **ID Page** (mỗi dòng 1 ID) → quét song song hàng loạt,
xem theo kiểu master–detail (danh sách Page bên trái, lưới reels bên phải).

![icon](icon.png)

## Chạy từ mã nguồn
```bash
pip install -r requirements.txt
python scan_reels_gui.py
```

## Hoặc chạy bản đóng gói
`build_nuitka/ReelsViewScanner.exe` — file exe độc lập (không cần cài Python),
one-file, không hiện cửa sổ console, có icon riêng. Chép đi đâu cũng chạy.

## Cách dùng

1. Bấm **“Nhập ID Page”**, dán danh sách — mỗi dòng 1 ID Page (số) hoặc username.
   VD: `100051080350208` hoặc `HungVlogOfficial`.
2. Chỉnh **“Luồng”** (số Page quét song song, mặc định 8) nếu cần.
3. Bấm **“Quét”**. Mỗi Page xong hiện ngay ở sidebar; click để xem lưới reels.
4. Chọn **bộ lọc** ở hàng dưới thanh công cụ và kiểu **sắp xếp** ở sidebar (xem mục dưới).
5. Bấm **“Xuất CSV”** để lưu kết quả (view, mô tả, URL, thumbnail…).

Bấm vào thumbnail để mở reel trên trình duyệt. Danh sách ID, số luồng, kiểu
sắp xếp và bộ lọc được nhớ trong `config.json`.

## Lọc reel

Hàng **“Lọc”** ngay dưới thanh công cụ chọn tập reel được đưa vào thống kê:

| Chế độ | Ý nghĩa |
|--------|---------|
| **Tất cả** (mặc định) | Dùng toàn bộ 10 reel quét được |
| **Video gần nhất** | Chỉ **N reel mới nhất** (ô số bên cạnh, 1–10) |
| **Theo ngày** | Chỉ reel đăng **trong N ngày** trở lại (1–365) |

- Lọc áp dụng **ngay lập tức**, không cần quét lại.
- View đỉnh, tổng view, số reel ở sidebar và lưới reels đều tính lại theo bộ lọc,
  nên **thứ tự sắp xếp Page cũng đổi theo** — VD lọc 7 ngày + xếp “View đỉnh”
  sẽ cho ra Page đang có video viral **trong tuần**.
- **Xuất CSV** chỉ ghi các reel qua bộ lọc.
- Page không còn reel nào sau khi lọc vẫn nằm trong danh sách (0 reels, xuống cuối).
- Chế độ “Theo ngày” dựa vào `creation_time` của reel; reel không có mốc thời gian
  thì bỏ qua bước lọc này.

> Mỗi Page chỉ quét được **10 reel** (GraphQL của Facebook trả tối đa 10/lần, muốn
> nhiều hơn phải phân trang bằng `end_cursor`). Nên lọc “30 ngày” với Page đăng dày
> có thể vẫn ra đủ 10 reel — đó là toàn bộ dữ liệu đang có, không phải lỗi lọc.

## Sắp xếp Page

Dải nút ngay dưới chữ `PAGES` chọn cách xếp thứ tự danh sách Page:

| Chế độ | Ý nghĩa |
|--------|---------|
| **View đỉnh** (mặc định) | Page có **reel nhiều view nhất** lên đầu — tìm nhanh Page đang có video viral |
| **Tổng view** | Cộng view toàn bộ reel của Page rồi xếp giảm dần |
| **Mặc định** | Giữ đúng thứ tự ID đã nhập |

- Mỗi Page hiện số view của reel cao nhất ở mép phải (nhãn **“đỉnh”**).
- Page lỗi luôn nằm cuối danh sách.
- Danh sách tự sắp lại ngay trong lúc quét, mỗi khi có Page mới xong.
- **Xuất CSV** ghi theo đúng thứ tự đang hiển thị.

## Cơ chế (2 bước, viết thẳng trong `fb_reels.py`)

1. **Lấy node id:** GET `facebook.com/<page_id>` → cắt id ở
   `[{"tab_key":"owner_reels","id":"…"}]` (đã là Base64 `app_collection:pfbid…`).
2. **Lấy view:** POST GraphQL `ProfileCometAppCollectionReelsRendererPaginationQuery`
   (doc_id `27781898651406539`) với `variables.id` = node id → 10 reel đầu.
3. **Parse** theo `data.node.aggregated_fb_shorts.edges[].profile_reel_node.node`:
   - Mô tả: `message.text`
   - View: `short_form_video_context.play_count_reduced` (vd `219K`, `1.4M`)
   - Thumbnail: `short_form_video_context.video.first_frame_thumbnail`

Quét nhiều Page chạy song song bằng `ThreadPoolExecutor` (số luồng cấu hình được).

## Hiệu năng & luồng

- Mặc định **8 luồng** — an toàn, khó bị Facebook chặn.
- 100 Page: để **15–20 luồng** là cân bằng tốc độ/ổn định.
- Đẩy quá cao (50–100) khi quét nhiều dễ bị rate-limit → nhiều Page báo lỗi;
  gặp vậy thì giảm luồng và quét lại.

## Khi hết hạn token

Cookie/token phiên nằm trong `fb_reels.py` (hàm `get_pfbid` và `get_view`). Khi quét
báo lỗi “không tìm thấy node id / hết hạn token”: lấy request mới từ trình duyệt
(đăng nhập facebook.com → DevTools → Network) và cập nhật `Cookie`, `lsd`,
`x-fb-lsd`, `__spin_t`… trong hai hàm đó. `app.py` là bản gốc để đối chiếu.

## Đóng gói lại exe

```bash
python make_icon.py    # (nếu muốn đổi icon) sinh icon.ico
python -m nuitka --onefile --assume-yes-for-downloads --enable-plugin=pyside6 \
  --windows-console-mode=disable --windows-icon-from-ico=icon.ico \
  --include-data-files=icon.ico=icon.ico \
  --output-filename=ReelsViewScanner.exe --output-dir=build_nuitka scan_reels_gui.py
```
Cần Nuitka + một C compiler (đang dùng TDM-GCC). Build PySide6 mất vài phút.

## File

| File | Vai trò |
|------|---------|
| `scan_reels_gui.py` | Giao diện PySide6 — **chạy file này** |
| `fb_reels.py` | Lõi: page_id → node id → view, parse (logic app.py viết thẳng ở đây) |
| `app.py` | Request gốc (tham khảo / nguồn cookie-token) |
| `make_icon.py` | Sinh `icon.ico` / `icon.png` |
| `icon.ico`, `icon.png` | Icon của app/exe |
| `config.json` | Tự sinh — lưu danh sách ID, số luồng, kiểu sắp xếp (`sort_mode`) & bộ lọc (`filter_mode`, `filter_count`, `filter_days`) |
| `build_nuitka/ReelsViewScanner.exe` | Bản đóng gói one-file |
