# Reels View Scanner

Tool desktop (PySide6) quét **view · mô tả · thumbnail** reels của Facebook Page
(10–300 reel mỗi Page, tự phân trang). Nhập danh sách **ID Page** (mỗi dòng 1 ID) → quét song song hàng loạt,
xem theo kiểu master–detail (danh sách Page bên trái, lưới reels bên phải).

![icon](icon.png)

## Chạy từ mã nguồn
```bash
pip install -r requirements.txt
python scan_reels_gui.py
```

## Hoặc chạy bản đóng gói
`build_nuitka/ReelsViewScanner.exe` — file exe độc lập (không cần cài Python),
one-file, không hiện cửa sổ console, có icon riêng. Chép đi đâu cũng chạy; nó
tạo `config.json` ngay cạnh exe nên chép cả 2 file là giữ nguyên cấu hình.

## Cách dùng

1. Bấm **“Nhập ID Page”**, dán danh sách — mỗi dòng 1 ID Page (số) hoặc username.
   VD: `100051080350208` hoặc `HungVlogOfficial`.
2. Chỉnh **“Reel/Page”** (số reel tối đa mỗi Page, 10–300, mặc định 10) và
   **“Luồng”** (số Page quét song song, mặc định 8) nếu cần.
3. Bấm **“Quét”**. Mỗi Page xong hiện ngay ở sidebar; click để xem lưới reels.
4. Chọn **bộ lọc** ở hàng dưới thanh công cụ và kiểu **sắp xếp** ở sidebar (xem mục dưới).
5. Bấm **“Xuất CSV”** để lưu kết quả — ra **2 file**: chi tiết từng reel và bảng
   xếp hạng Page (xem mục dưới).

Bấm vào thumbnail để mở reel trên trình duyệt. Danh sách ID, số reel/Page, số
luồng, kiểu sắp xếp và bộ lọc được nhớ trong `config.json` — file này nằm **cạnh
file đang chạy**: cạnh `scan_reels_gui.py` khi chạy mã nguồn, cạnh
`ReelsViewScanner.exe` khi chạy bản đóng gói.

## Lọc reel

Hàng **“Lọc”** ngay dưới thanh công cụ chọn tập reel được đưa vào thống kê:

| Chế độ | Ý nghĩa |
|--------|---------|
| **Tất cả** (mặc định) | Dùng toàn bộ reel quét được |
| **Video gần nhất** | Chỉ **N reel mới nhất** (ô số bên cạnh, 1 → “Reel/Page”) |
| **Theo ngày** | Chỉ reel đăng **trong N ngày** trở lại (1–365) |

- Lọc áp dụng **ngay lập tức**, không cần quét lại.
- View đỉnh, tổng view, số reel ở sidebar và lưới reels đều tính lại theo bộ lọc,
  nên **thứ tự sắp xếp Page cũng đổi theo** — VD lọc 7 ngày + xếp “View đỉnh”
  sẽ cho ra Page đang có video viral **trong tuần**.
- **Xuất CSV** chỉ ghi các reel qua bộ lọc.
- Page không còn reel nào sau khi lọc vẫn nằm trong danh sách (0 reels, xuống cuối).
- Chế độ “Theo ngày” dựa vào `creation_time` của reel; reel không có mốc thời gian
  thì bỏ qua bước lọc này.

> GraphQL của Facebook trả tối đa **10 reel/request**, nên đặt “Reel/Page” = 50 là
> tool tự gọi 5 lượt nối nhau bằng `end_cursor` (đặt càng cao càng lâu). Page ít
> reel hơn thì dừng sớm — số reel hiện ra là toàn bộ dữ liệu có được, không phải
> lỗi lọc.

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

## Xuất CSV

Một lần bấm **“Xuất CSV”** ghi ra **2 file** cạnh nhau (chọn tên `reels_x.csv` thì
được `reels_x.csv` + `reels_x_rank.csv`):

| File | Nội dung |
|------|----------|
| `<tên>.csv` | **Chi tiết từng reel** — Page ID, Author, Rank, Views, Views(num), Description, URL, Video ID, Thumbnail |
| `<tên>_rank.csv` | **Xếp hạng Page** — mỗi Page 1 dòng, để theo dõi tổng quan |

Cột của file `_rank`: `Hạng`, `Page ID`, `Tên Page`, `Số reel`, `View đỉnh`,
`View đỉnh (số)`, `Tổng view`, `Tổng view (số)`, `View TB/reel`, `Reel mới nhất`,
`Link reel đỉnh`, `Mô tả reel đỉnh`, `Trạng thái`.

- View có **2 cột**: bản đọc nhanh (`1.2M`) và bản số thuần (`1200000`).
- Hạng xếp theo tiêu chí đang chọn ở sidebar (**View đỉnh** / **Tổng view**);
  chế độ “Mặc định” thì xếp theo view đỉnh. Page lỗi xuống cuối, bỏ trống hạng
  và ghi lý do ở cột `Trạng thái`.
- Cả 2 file đều tôn trọng **bộ lọc** đang bật.

> **Mọi ô đều ghi dạng text** (`="..."`) để Excel/Google Sheets không tự ép kiểu:
> Page ID / Video ID không thành `1.00064E+14`, số view không bị format lại, ngày
> không bị đổi theo locale, mô tả bắt đầu bằng `=` `+` `-` `@` không bị hiểu là
> công thức. Muốn tính toán trên cột số thì dùng `=VALUE(ô)` hoặc Text-to-Columns.

## Cơ chế (2 bước, viết thẳng trong `fb_reels.py`)

1. **Lấy node id:** GET `facebook.com/<page_id>` → cắt id ở
   `[{"tab_key":"owner_reels","id":"…"}]` (đã là Base64 `app_collection:pfbid…`).
2. **Lấy view:** POST GraphQL `ProfileCometAppCollectionReelsRendererPaginationQuery`
   (doc_id `27781898651406539`) với `variables.id` = node id → 10 reel.
3. **Phân trang:** lần gọi đầu không có `cursor`; các lần sau chèn
   `variables.cursor` = `end_cursor` của response trước, lặp tới khi đủ số reel
   hoặc `has_next_page = false`.
4. **Parse** theo `data.node.aggregated_fb_shorts.edges[].profile_reel_node.node`:
   - Mô tả: `message.text`
   - View: `short_form_video_context.play_count_reduced` (vd `219K`, `1.4M`)
   - Thumbnail: `short_form_video_context.video.first_frame_thumbnail`

> **Cursor nào mới đúng:** response có rất nhiều field tên `cursor` —
> `edges[i].cursor` là cursor của *từng reel*, các chunk `@defer` phía sau còn
> cursor của connection con (comment, reaction…). Cursor phân trang **duy nhất
> đúng** là `data.node.aggregated_fb_shorts.page_info.end_cursor`, và chỉ dùng
> khi `page_info.has_next_page = true` (xem `next_cursor()` trong `fb_reels.py`).

Quét nhiều Page chạy song song bằng `ThreadPoolExecutor` (số luồng cấu hình được);
mỗi Page dùng 1 `requests.Session` để tái dùng kết nối khi phân trang, và mỗi
response chỉ đọc **dòng JSON đầu** rồi ngắt (các chunk `@defer` phía sau nặng
~10 MB mà tool không dùng).

## Hiệu năng & luồng

- Mặc định **8 luồng** — an toàn, khó bị Facebook chặn.
- 100 Page: để **15–20 luồng** là cân bằng tốc độ/ổn định.
- Đẩy quá cao (50–100) khi quét nhiều dễ bị rate-limit → nhiều Page báo lỗi;
  gặp vậy thì giảm luồng và quét lại.
- **Reel/Page** ảnh hưởng trực tiếp tới thời gian: mỗi 10 reel = thêm 1 lượt gọi
  cho *mỗi* Page (30 reel = 3 lượt). Đo thực tế: 11 Page × 30 reel, 11 luồng
  ≈ **6.7 giây**; 9 Page × 30 reel, 9 luồng ≈ **6.1 giây**.
- Page ít reel hơn trần đã đặt thì tự dừng sớm (`has_next_page = false`), không
  tốn request thừa — VD đặt 30 mà Page có 28 reel thì chỉ gọi 3 lượt.

## Khi hết hạn token

Cookie/token phiên nằm trong `fb_reels.py` (hàm `get_pfbid` và `get_view`). Khi quét
báo lỗi “không tìm thấy node id / hết hạn token”: lấy request mới từ trình duyệt
(đăng nhập facebook.com → DevTools → Network) và cập nhật `Cookie`, `lsd`,
`x-fb-lsd`, `__spin_t`… trong hai hàm đó. `app.py` là bản gốc để đối chiếu.

## Đóng gói lại exe

```bash
pip install nuitka zstandard    # zstandard = nén payload one-file
python make_icon.py    # (nếu muốn đổi icon) sinh icon.ico
python -m nuitka --onefile --assume-yes-for-downloads --enable-plugin=pyside6 \
  --windows-console-mode=disable --windows-icon-from-ico=icon.ico \
  --include-data-files=icon.ico=icon.ico \
  --output-filename=ReelsViewScanner.exe --output-dir=build_nuitka scan_reels_gui.py
```
Cần Nuitka + một C compiler (đang dùng MSVC `cl`, TDM-GCC cũng chạy được).
Build PySide6 mất vài phút. Thiếu `zstandard` thì exe ra ~77 MB, có thì nén còn
**~23 MB** (Nuitka báo `compression ratio 29.75%`).

## File

| File | Vai trò |
|------|---------|
| `scan_reels_gui.py` | Giao diện PySide6 — **chạy file này** |
| `fb_reels.py` | Lõi: page_id → node id → view, phân trang bằng cursor, parse (logic app.py viết thẳng ở đây) |
| `app.py` | Request gốc (tham khảo / nguồn cookie-token) |
| `make_icon.py` | Sinh `icon.ico` / `icon.png` |
| `icon.ico`, `icon.png` | Icon của app/exe |
| `config.json` | Tự sinh **cạnh file đang chạy** (mã nguồn hoặc exe) — lưu danh sách ID, số luồng, số reel/Page (`max_reels`), kiểu sắp xếp (`sort_mode`) & bộ lọc (`filter_mode`, `filter_count`, `filter_days`) |
| `build_nuitka/ReelsViewScanner.exe` | Bản đóng gói one-file |
