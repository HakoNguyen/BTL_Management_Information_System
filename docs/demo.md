# Kịch bản demo đi tay

Đi qua đủ năm quy trình P1–P5 của đặc tả mục 3 và 11 tình huống KT trên giao diện, khoảng 25 phút.
Mọi con số dưới đây tính từ dữ liệu của `make seed-demo` chạy trên CSDL trống; làm đúng thứ tự cảnh thì
số trên màn hình phải khớp đúng. Lệch số là lỗi, ghi lại để sửa.

## 0. Chuẩn bị (trước giờ demo)

1. Dựng lại sạch và nạp dữ liệu demo (trong Git Bash, đã `source .venv/Scripts/activate`):

   ```bash
   make reset
   ```

   ```bash
   make seed-demo
   ```

   Lệnh thứ hai in mật khẩu tạm của 5 tài khoản **một lần duy nhất**: chép ra giấy.
2. Mở ba cửa sổ trình duyệt độc lập (thường, ẩn danh, trình duyệt khác), vì mỗi cửa sổ chỉ giữ một phiên
   đăng nhập. Gợi ý: cửa sổ 1 = NVBH, cửa sổ 2 = Thu ngân, cửa sổ 3 = QL / NV kho / Trụ sở (đăng xuất rồi
   đăng nhập lại khi đổi vai).
3. Mở một terminal để đổi chế độ cổng thanh toán giả lập. Lệnh mẫu (thay `SUCCESS` bằng `FAILED`, `SILENT`,
   `DUPLICATE`):

   ```bash
   curl -X PUT localhost:8001/mode -H "Content-Type: application/json" -d '{"mode":"SUCCESS"}'
   ```

Dữ liệu sau `seed-demo`:

| Loại | Giá trị |
| --- | --- |
| Chi nhánh | CN1, CN2 (đóng cửa 22:00) |
| Tài khoản | `admin` (trụ sở ban đầu), `nv-ts` (Trụ sở), `nv-ql1` (QL CN1), `nv-bh1` (NVBH CN1), `nv-tn1` (Thu ngân CN1), `nv-kho1` (NV kho CN1) |
| Sản phẩm | A, B, C, D thuộc nhóm `NHOM1`, giá 100.000 |
| Tồn CN1 | mỗi sản phẩm 20 (phiếu nhập `DEMO-TON-DAU-KY`) |
| Khách | Nguyễn Văn An 0901000001, Trần Thị Bình 0901000002, Lê Minh Châu 0901000003 |

## Bảng theo dõi số liệu

Sau mỗi cảnh, số đúng phải là:

| Sau cảnh | Tồn A | Tồn B | Tồn C | Tồn D | Tiền mặt kỳ vọng của ca | Doanh thu gộp hôm nay |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 18 | 20 | 20 | 20 | 700.000 | 200.000 |
| 2 | 18 | 15 | 20 | 20 | 700.000 | 700.000 |
| 3 | 18 | 15 | 17 | 20 | 700.000 | 1.000.000 |
| 4 | 18 | 15 | 17 | 20 | 700.000 | 1.000.000 |
| 5 | 18 | 16 | 17 | 20 | 500.000 | 1.000.000 |
| 6 | 18 | 16 | 17 | 25 | 500.000 | 1.000.000 |

## Cảnh 1 – Bán tiền mặt (P1, KT-01)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| Thu ngân | **Ca thu ngân** → Mở ca, tiền đầu ca `500000` | Ca Đang mở, tiền mặt kỳ vọng 500.000 |
| NVBH | **Khách hàng** → tra `0901000001` | Ra hồ sơ Nguyễn Văn An (2.3) |
| NVBH | **Đơn hàng** → Lập đơn: khách An, 2 × A → chốt đơn | Đơn Chờ thanh toán, tổng 200.000 (BH-02) |
| Thu ngân | **Thu tiền** → chọn đơn, Tiền mặt → xác nhận đã nhận đủ | Đơn Hoàn tất (TT-03) |
| Thu ngân | **Hóa đơn** → mở hóa đơn của đơn, in, in lại | Số hóa đơn giữ nguyên, số lần in tăng (TT-04) |
| NV kho | **Tồn kho chi nhánh** | A = 18 |

Câu nói: "Thu tiền thành công thì xuất kho, hoàn tất đơn và phát hành hóa đơn trong một giao dịch CSDL."

## Cảnh 2 – Thẻ thất bại rồi thành công (KT-04)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| Terminal | Đổi chế độ `FAILED` | |
| NVBH | Lập đơn khách lẻ (KHLE), 5 × B → chốt | Chờ thanh toán, 500.000 |
| Thu ngân | **Thu tiền** → đơn đó, Thẻ | Giao dịch Thất bại; đơn vẫn Chờ thanh toán; tồn B vẫn 20 (hàng giữ đã nhả) |
| Terminal | Đổi chế độ `SUCCESS` | |
| Thu ngân | Thu lại bằng Thẻ | Đơn Hoàn tất; đơn có 2 giao dịch (1 Thất bại, 1 Thành công), 1 hóa đơn |

Tiền mặt kỳ vọng của ca **không đổi** (thẻ không tính vào tiền mặt, CA-02).

## Cảnh 3 – Mất phản hồi và phản hồi lặp (KT-05)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| Terminal | Đổi chế độ `SILENT` | |
| NVBH | Lập đơn khách Bình (0901000002), 3 × C → chốt | 300.000 |
| Thu ngân | Thu bằng Chuyển khoản | Giao dịch Chờ kết quả; không thu thêm được cho đơn này (TT-02) |
| NV kho | Tồn kho chi nhánh | C: tồn 20, khả dụng 17 (đang giữ hàng) |
| Thu ngân | Tra soát giao dịch: kết quả Thành công, mã tham chiếu `R1` | Đơn Hoàn tất, tồn C = 17 |
| Terminal | Đổi chế độ `SUCCESS` | |

Nói thêm: mất phản hồi không bị coi là thất bại, đơn không tự hủy lúc đóng cửa (BH-05). Phản hồi lặp của ngân hàng
bị bỏ qua (có test KT-05); muốn trình diễn thì dùng chế độ `DUPLICATE` cho một đơn khác.

## Cảnh 4 – Đổi giá, khách đổi ý (P2, KT-02, KT-03)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| Trụ sở (`nv-ts`) | **Sản phẩm** → A → Đổi giá `110000` → Lịch sử giá | Thêm một bản ghi lịch sử giá (SP-02) |
| NVBH | **Đơn hàng** → đơn của cảnh 1 | Vẫn 200.000: giá đã chốt không đổi (SP-03) |
| NVBH | Lập đơn KHLE 1 × A → chốt | 110.000 (giá mới) |
| NVBH | Mở lại → thêm 1 × D → chốt lại | Đang lập rồi Chờ thanh toán, 210.000 (BH-03) |
| NVBH | Hủy đơn, lý do "Khách đổi ý" | Đã hủy; tồn và doanh thu không đổi (BH-04) |

## Cảnh 5 – Trả hàng, hoàn thẻ thất bại, duyệt thay (P3, KT-08, KT-09, KT-15)

Dùng đơn 5 × B thanh toán thẻ của cảnh 2.

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| NVBH | **Phiếu trả** → Lập phiếu trả: đơn cảnh 2, B tốt 1, lỗi 1, lý do "Hàng lỗi" | Phiếu Chờ duyệt, giá trị 200.000 (TH-04); hàng vẫn do khách giữ |
| NVBH | Lập thêm phiếu: B tốt 4 | Bị từ chối: vượt lượng còn được trả (TH-02) |
| QL (`nv-ql1`) | **Phiếu trả** → duyệt phiếu 200.000 | Đã duyệt; đơn Đã trả một phần; tồn B = 16 (chỉ hàng tốt vào tồn, TH-05) |
| Terminal | Đổi chế độ `FAILED` | |
| Thu ngân | **Hoàn tiền** → phiếu đó → hoàn | Hoàn thẻ Thất bại; phiếu vẫn Đã duyệt, Chưa hoàn (KT-09) |
| QL | Phiếu trả → **Hoàn tiền mặt**, lý do "Thẻ khách đã hủy" | Đã duyệt hoàn tiền mặt thay thế |
| Thu ngân | Hoàn lại → tiền mặt → xác nhận đã chi | Đã hoàn; tiền mặt kỳ vọng 500.000 (−200.000) |
| Terminal | Đổi chế độ `SUCCESS` | |
| QL | Tự lập một phiếu trả cho đơn cảnh 1 (1 A tốt), rồi thử duyệt | Không tự duyệt được (K-02) |
| Trụ sở | **Phiếu trả** → duyệt thay phiếu đó, ghi lý do | Đã duyệt, lưu người duyệt và lý do (K-02, K-03) |

Phiếu duyệt thay ở dòng cuối làm tồn A lên 19 và giảm doanh thu thuần thêm 100.000. Muốn giữ đúng bảng theo dõi
số liệu thì **từ chối** phiếu đó thay vì duyệt, hoặc bỏ hai dòng cuối.

## Cảnh 6 – Kho: nhập nhầm, nhập trùng, ngưỡng, bổ sung (P5, KT-12, KT-14)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| NV kho (`nv-kho1`) | **Phiếu kho** → Ghi nhập hàng: bên giao Kho tổng, số phiếu giao `PG-0815`, D số lượng `50` (cố ý nhập nhầm, phiếu ghi 5) | Tồn D = 70 |
| NV kho | Ghi nhập lại `PG-0815` | Bị từ chối: trùng phiếu giao (TK-02) |
| NV kho | Lập phiếu Điều chỉnh giảm D 45, lý do "Nhập nhầm", phiếu bị sai = phiếu vừa nhập | Chờ xử lý; tồn D 70, khả dụng 25 |
| QL | **Phiếu kho** → duyệt | Đã ghi nhận, tồn D = 25; phiếu nhập gốc không bị sửa (TK-04) |
| QL | **Tồn kho chi nhánh** → ngưỡng A = `18`, C = `18` | |
| NV kho | **Cảnh báo tồn** | C (17 < 18) bị cảnh báo; A (18 = 18) không; B, D ở mục Chưa thiết lập (TK-05) |
| NV kho | **Yêu cầu bổ sung** → gửi Kho tổng, C 20 | Lưu yêu cầu; tồn C vẫn 17 (TK-06) |

## Cảnh 7 – Đóng ca và đối soát (P4, KT-11)

| Vai | Thao tác | Kết quả phải thấy |
| --- | --- | --- |
| Thu ngân | **Ca thu ngân** → Đóng ca, tiền kiểm đếm `490000`, chưa nhập lý do | Bị từ chối: chênh lệch −10.000 phải có lý do (CA-02) |
| Thu ngân | Nhập lý do "Thối nhầm" → đóng | Ca Chờ xác nhận; kết quả đối soát: tiền mặt kỳ vọng 500.000 = 500.000 + 200.000 − 200.000; thẻ và chuyển khoản ghi riêng |
| QL | **Ca thu ngân** → xem ca → xác nhận chốt | Ca Đã chốt (CA-03) |

Biến thể KT-16 (thay cho hai dòng trên): QL **đóng ca thay** với người làm chứng `NV-BH1` và lý do; QL không xác
nhận được, phải đăng nhập Trụ sở để xác nhận chốt (CA-04).

## Cảnh 8 – Báo cáo (nhóm 5, KT-10)

Đăng nhập QL (chi nhánh mình) rồi Trụ sở (toàn chuỗi), kỳ là hôm nay.

| Báo cáo | Kết quả phải thấy (theo đúng thứ tự cảnh, phiếu duyệt thay ở cảnh 5 đã bị từ chối) |
| --- | --- |
| Doanh thu | 3 đơn bán; doanh thu gộp 1.000.000; hàng bán bị trả 200.000; doanh thu thuần 800.000; 1 đơn hủy lý do "Khách đổi ý"; tổng chênh lệch tiền ca −10.000; số còn phải hoàn 0 |
| Doanh số nhân viên | Toàn bộ ghi cho NV-BH1 tại CN1 (DT-05); NVBH đăng nhập chỉ thấy dòng của mình |
| Sản phẩm bán | B: bán 5, trả 2, thuần 3 |
| Báo cáo tồn kho | Tồn, khả dụng, ngưỡng như bảng theo dõi; điều chỉnh giảm 45 lý do "Nhập nhầm" |

## Cảnh 9 (tùy chọn, làm cuối cùng) – Giờ đóng cửa (KT-07)

Cảnh này hủy **mọi** đơn chưa thanh toán và từ chối mọi phiếu trả chờ duyệt của CN1, nên để cuối.

1. NVBH lập một đơn Đang lập; lập một phiếu trả Chờ duyệt (đơn cảnh 1, 1 A).
2. Trụ sở → **Chi nhánh** → sửa giờ đóng cửa CN1 thành giờ hiện tại cộng 1 phút.
3. Chờ khoảng 2 phút (tác vụ nền quét mỗi 60 giây), tải lại trang.
4. Kết quả: đơn chuyển Đã hủy, lý do "Quá hạn", người hủy Hệ thống (BH-05); phiếu trả chuyển Từ chối,
   lý do "Quá hạn duyệt" (TH-03).
5. Đặt lại giờ đóng cửa 22:00.

## Phân công trình bày (gợi ý theo docs/plan.md mục 6)

| Cảnh | Vai trình bày |
| --- | --- |
| Chuẩn bị, kiến trúc, cảnh 9 | Vai 1 – Nền tảng (trưởng nhóm) |
| Cảnh 4, cảnh 8 | Vai 2 – Danh mục và báo cáo |
| Cảnh 5 phần phiếu trả | Vai 3 – Đơn hàng và trả hàng |
| Cảnh 1, 2, 3, 7; cảnh 5 phần hoàn tiền | Vai 4 – Thanh toán, ca |
| Cảnh 6 | Vai 5 – Tồn kho |

KT-06 (tranh hàng cuối cùng) và KT-13 (đóng chi nhánh) khó dựng tay trong vài phút; trình bày bằng kết quả test
tự động `make test` (349 test, gồm 16 file KT) thay vì đi tay.
