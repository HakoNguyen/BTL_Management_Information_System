# Kịch bản demo có ảnh minh họa

9 kịch bản cốt lõi, mỗi kịch bản 2–4 ảnh chụp từ giao diện thật. Trên ảnh: **khung đỏ** là chỗ cần nhìn hoặc bấm,
**số tròn** là thứ tự thao tác, **nhãn đỏ** cùng số là chú giải của khung đó, **thanh dưới cùng** là ý chính của bước.
Số thứ tự trong các bước dưới đây trùng với số trên ảnh.

| # | Kịch bản | Vai trò | Tài khoản (CN1) |
| --- | --- | --- | --- |
| 1 | Đăng nhập, phân quyền theo vai trò | Mọi vai trò | `nv-bh1`, `admin` |
| 2 | Lập và chốt đơn | NV bán hàng | `nv-bh1` |
| 3 | Thu tiền (thẻ) | Thu ngân | `nv-tn1` |
| 4 | Hóa đơn | Thu ngân | `nv-tn1` |
| 5 | Trả hàng | NV bán hàng lập, QL duyệt | `nv-bh1`, `nv-ql1` |
| 6 | Hoàn tiền | Thu ngân | `nv-tn1` |
| 7 | Ca thu ngân: đóng ca, chốt ca | Thu ngân, QL | `nv-tn1`, `nv-ql1` |
| 8 | Phiếu kho, cảnh báo tồn | NV kho lập, QL duyệt | `nv-kho1`, `nv-ql1` |
| 9 | Báo cáo doanh thu | Trụ sở | `admin` |

Mật khẩu không ghi ở đây: dùng mật khẩu nhóm đang giữ; quên thì Trụ sở cấp lại ở trang Nhân viên.

## Video demo đủ chức năng

[video/demo-day-du-chuc-nang.webm](video/demo-day-du-chuc-nang.webm) (khoảng 9 phút, 1440×900, mở bằng Chrome,
Edge hoặc VLC). Một phiên trình duyệt, đăng nhập lần lượt từng vai trò; viền đỏ mảnh chỉ chỗ đang thao tác, phụ đề
ở dưới giải thích từng bước và mã chức năng.

| Chương | Vai trò | Nội dung |
| --- | --- | --- |
| 1 | Trụ sở | Chi nhánh (6.4); nhân viên: lọc, thêm, phân công, cấp tài khoản (6.1–6.3); nhóm, thêm sản phẩm, đổi giá, lịch sử giá (1.1–1.4) |
| 2 | NV bán hàng | Danh sách, sửa khách, lịch sử mua có xác minh (2.2–2.4); lập đơn khách mới, khách lẻ, khách đã lưu; chốt, mở lại, hủy đơn (2.1, 3.1, 3.4) |
| 3 | Thu ngân | Mở ca (3.5); thu tiền mặt; thẻ thất bại rồi thành công (3.2); hóa đơn (3.3) |
| 4 | NV bán hàng | Phiếu trả tìm đơn theo số điện thoại, hàng còn tốt (3.4) |
| 5 | NV kho | Tồn kho (4.1), ghi nhập theo phiếu giao (4.2), xuất hủy (4.3), xuất điều chuyển sang CN2 (4.6), yêu cầu bổ sung (4.4) |
| 6 | Quản lý | Duyệt phiếu trả, phiếu xuất hủy, phiếu điều chuyển; đặt ngưỡng tồn (4.5); cảnh báo tồn (5.4) |
| 7 | NV kho CN2 | Nhận hàng điều chuyển (4.6) |
| 8 | Thu ngân → Quản lý | Hoàn tiền mặt; đóng ca có chênh lệch; QL xác nhận chốt ca |
| 9 | Trụ sở | Báo cáo doanh thu, sản phẩm bán, tồn kho, doanh số nhân viên (5.1, 5.2, 5.3, 5.5) |

## 1. Đăng nhập

Không có ô chọn vai trò: vai trò và chi nhánh gắn với tài khoản do Trụ sở cấp (6.3), menu hiện theo vai trò.

1. Nhập tên đăng nhập, mật khẩu (lần đầu là mật khẩu tạm), bấm **Đăng nhập**.
2. Vào trang chủ: menu bên trái chỉ có chức năng của vai trò; góc phải ghi vai trò và chi nhánh.
3. Cùng màn hình, tài khoản Trụ sở thấy thêm chi nhánh, nhân viên, sản phẩm và báo cáo toàn chuỗi.

![](01-dang-nhap-1.png)
![](01-dang-nhap-2.png)
![](01-dang-nhap-3.png)

## 2. Lập và chốt đơn (P1, BH-01..BH-03)

1. **Đơn hàng** → **Lập đơn**. Chọn **Khách lẻ / Khách đã lưu / Khách mới**; khách đã lưu thì gõ tên hoặc số điện thoại.
2. Chọn sản phẩm (danh sách hiện sẵn tồn khả dụng), nhập số lượng, **+ Thêm sản phẩm** nếu nhiều dòng, **Lưu**.
3. Đơn ở **Đang lập**: còn sửa dòng, chưa giữ hàng. Bấm **Chốt**.
4. Đơn chuyển **Chờ thanh toán**: đơn giá và tổng tiền được khóa (mở dòng bằng dấu + để xem). Khách đổi ý thì
   **Mở lại** hoặc **Hủy đơn** kèm lý do.

![](02-lap-don-1.png)
![](02-lap-don-2.png)
![](02-lap-don-3.png)

## 3. Thu tiền (P1, TT-01..TT-03)

1. **Thu tiền**: danh sách đơn Chờ thanh toán của chi nhánh → **Thu tiền** ở đơn cần thu.
2. Chọn phương thức (Tiền mặt / Chuyển khoản / Thẻ). Số tiền luôn bằng tổng đơn, không nhập tay. **Lưu**: hệ thống
   giữ hàng rồi gửi yêu cầu sang ngân hàng.
3. Giao dịch thẻ, chuyển khoản nằm ở **Chờ kết quả**. Khách quẹt thẻ hoặc chuyển khoản xong, máy POS/app ngân hàng
   báo kết quả thì bấm **Ngân hàng báo thành công** hoặc **Ngân hàng báo thất bại** (thất bại: đơn vẫn chờ, hàng giữ
   được nhả, thu lại được). Tiền mặt thì bấm **Đã nhận đủ tiền**.
4. Thành công: đơn **Hoàn tất**, xuất kho và phát hành hóa đơn trong cùng một giao dịch CSDL.

![](03-thu-tien-1.png)
![](03-thu-tien-2.png)
![](03-thu-tien-3.png)
![](03-thu-tien-4.png)

## 4. Hóa đơn (TT-04)

1. **Hóa đơn**: mỗi đơn đã thanh toán có đúng một hóa đơn. Lọc theo ngày và theo ca; bấm **Xem hóa đơn**.
2. Chi tiết: số hóa đơn, đơn, chi nhánh, thời điểm, phương thức, số lần in. **In hóa đơn** dùng máy in của trình
   duyệt; in lại thì số hóa đơn giữ nguyên, số lần in tăng.

![](04-hoa-don-1.png)
![](04-hoa-don-2.png)

## 5. Trả hàng (P3, TH-01..TH-05)

1. NV bán hàng: **Phiếu trả** → **Lập phiếu trả**. Khách mang hóa đơn thì tìm **theo mã đơn**; khách có hồ sơ mất hóa
   đơn thì **theo số điện thoại** → **Tìm đơn** → chọn đơn gốc (chỉ hiện đơn Hoàn tất hoặc Đã trả một phần ở chi nhánh; hạn 7 ngày do API
   kiểm tra khi lưu).
   Ghi lý do, chọn sản phẩm, nhập **Còn tốt** (nhập lại kho) và **Bị lỗi** (không vào kho), **Lưu**.
2. Phiếu **Chờ duyệt**: hàng vẫn do khách giữ, tồn chưa đổi; giá trị trả tính theo đơn giá đã chốt.
3. QL (`nv-ql1`): **Phiếu trả** → **Duyệt** → ghi chú → **Lưu**. Người duyệt phải khác người lập (K-02); từ chối bắt
   buộc lý do.
4. Phiếu **Đã duyệt, Chưa hoàn**: hàng tốt đã nhập lại kho, chuyển sang thu ngân hoàn tiền.

![](05-tra-hang-1.png)
![](05-tra-hang-2.png)
![](05-tra-hang-3.png)
![](05-tra-hang-4.png)

## 6. Hoàn tiền (TH-04)

1. Thu ngân: **Hoàn tiền** → phiếu chờ hoàn → **Khởi tạo hoàn** → **Đồng ý**. Hoàn đúng phương thức khách đã trả;
   không tự chọn được.
2. Đơn gốc trả tiền mặt nên hoàn tiền mặt từ két: đưa tiền cho khách rồi bấm **Đã chi đủ tiền** (két không đủ thì
   **Không chi được**, phiếu vẫn Chưa hoàn).
3. Thành công: phiếu **Đã hoàn**, tiền mặt kỳ vọng của ca giảm tương ứng.

Hoàn thẻ hoặc chuyển khoản thất bại (thẻ đã hủy): QL vào **Ca thu ngân** → mở ca → **Duyệt hoàn tiền mặt** kèm lý do,
thu ngân bấm **Thử lại** thì lần này hoàn tiền mặt (KT-09).

![](06-hoan-tien-1.png)
![](06-hoan-tien-2.png)
![](06-hoan-tien-3.png)

## 7. Ca thu ngân (P4, CA-01..CA-03)

1. Thu ngân: **Ca thu ngân** → **Ca hiện tại**: tổng thu, tổng hoàn, **tổng doanh thu ca**; tiền mặt kỳ vọng
   = tiền đầu ca + thu tiền mặt − hoàn tiền mặt. Cuối ca bấm **Đóng ca**.
2. Đếm tiền thật trong két, nhập vào **Tiền mặt kiểm đếm**. Lệch với kỳ vọng thì bắt buộc ghi lý do (ảnh: thiếu
   10.000, lý do "Thối nhầm"). Thẻ, chuyển khoản không đếm.
3. QL: **Ca thu ngân** → ca **Chờ xác nhận** → **Xác nhận chốt** sau khi nhận tiền.
4. Ca **Đã chốt**: không sửa được nữa; mở dòng xem kết quả đối soát (tổng ca, tiền mặt, chênh lệch, lý do). Chênh
   lệch hiện ở cột "Chênh lệch ca" của báo cáo doanh thu.

Ca mới: thu ngân bấm **Mở ca**, nhập tiền đầu ca (quỹ tiền lẻ nhận từ QL).

![](07-ca-thu-ngan-1.png)
![](07-ca-thu-ngan-2.png)
![](07-ca-thu-ngan-3.png)
![](07-ca-thu-ngan-4.png)

## 8. Phiếu kho và cảnh báo tồn (P5, TK-01..TK-05)

1. NV kho: **Phiếu kho** → **Ghi nhập hàng**. Nguồn hàng (kho tổng / nhà cung cấp), bên giao và số phiếu giao chép
   từ tờ phiếu giao giấy (demo tự đặt, ví dụ `ANK-171126-01`), số lượng là số thực nhận. **Lưu**: tồn tăng ngay.
   Nhập lại cùng số phiếu giao bị từ chối (chống nhập trùng).
2. **Lập phiếu điều chỉnh, xuất**: xuất hủy, xuất trả kho tổng, điều chỉnh tăng/giảm, bắt buộc lý do. Phiếu
   **Chờ xử lý**: hàng bị giữ (khả dụng giảm), tồn chưa đổi.
3. QL: **Phiếu kho** → **Duyệt** → **Đồng ý**: tồn giảm ngay. Phiếu xuất bán, nhập hàng trả do hệ thống tự tạo.
4. **Cảnh báo tồn**: mặt hàng có tồn dưới ngưỡng QL đã đặt (ở **Tồn kho chi nhánh**) → gửi **Yêu cầu bổ sung**
   về kho tổng.

![](08-phieu-kho-1.png)
![](08-phieu-kho-2.png)
![](08-phieu-kho-3.png)
![](08-phieu-kho-4.png)

## 9. Báo cáo doanh thu (DT-01..DT-05)

1. Trụ sở: **Báo cáo → Doanh thu**. Chọn kỳ, chi nhánh (trống = toàn chuỗi), **Xem báo cáo**. Biểu đồ theo thời
   gian xem được theo ngày, tháng, quý, năm và lọc nhóm sản phẩm.
2. So sánh chi nhánh (gộp, hàng trả, thuần) và tiền thu, hoàn theo phương thức.
3. Bảng số liệu: doanh thu thuần = gộp − giá trị hàng trả; chênh lệch tiền ca; số còn phải hoàn. Bấm **+** để xem
   tiền theo phương thức và đơn hủy theo lý do. QL chỉ xem được chi nhánh mình.

![](09-bao-cao-1.png)
![](09-bao-cao-2.png)
![](09-bao-cao-3.png)

## Dữ liệu mẫu và cách dựng lại

Dữ liệu trong ảnh là bộ mẫu cửa hàng phụ kiện công nghệ: 3 chi nhánh, 11 nhóm, 72 sản phẩm (ốp lưng, cáp, sạc, tai
nghe, loa, đồng hồ…); tồn CN1 986, CN2 670, CN3 480 sản phẩm; ngưỡng tồn CN1 theo giá; 12 khách có hồ sơ; một lượt
bán khoảng 60 đơn ở ba chi nhánh, vài đơn hủy, vài phiếu trả đã hoàn. Mọi thứ tạo qua API như người dùng thật, nên
chứng từ, tồn và báo cáo khớp nhau. Đơn chỉ có ngày hôm chạy vì hệ thống không cho lập chứng từ lùi ngày.

Dựng lại từ đầu (giữ chi nhánh, tài khoản, danh mục; xóa đơn, giao dịch, hóa đơn, phiếu trả, ca, phiếu kho, tồn,
khách, mã chứng từ chạy lại từ `…000001`):

```powershell
docker exec qlbh-db psql -U postgres -d qlbh -c "TRUNCATE customers, orders, order_items, invoices, transactions, return_slips, return_slip_items, shifts, stock, stock_slips, stock_slip_items, replenishment_requests, replenishment_request_items RESTART IDENTITY CASCADE" -c "INSERT INTO customers (customer_id, full_name, phone, registered_on) VALUES ('KHLE', 'Khách lẻ', NULL, CURRENT_DATE)"
.venv\Scripts\python scripts/seed-catalog.py --login admin=<mk> --login nv-kho1=<mk> --login nv-kho2=<mk> --login nv-kho3=<mk> --login nv-ql1=<mk>
.venv\Scripts\python scripts/seed-sales.py --login admin=<mk> --login nv-bh1=<mk> --login nv-tn1=<mk> --login nv-ql1=<mk> --login nv-bh2=<mk> --login nv-tn2=<mk> --login nv-bh3=<mk> --login nv-tn3=<mk>
```

Lệnh đầu xóa dữ liệu không lấy lại được. NV kho không có mật khẩu trong `--login` thì `seed-catalog` cấp lại mật
khẩu tạm và in ra. Cổng thanh toán giả lập để chế độ `SILENT`: kết quả thẻ, chuyển khoản do thu ngân bấm.
