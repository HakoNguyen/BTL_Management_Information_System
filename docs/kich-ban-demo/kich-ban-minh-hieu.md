# Kịch bản nói – Minh Hiếu (demo 18/11/2026)

Nguồn: "Kịch bản demo – HTTTQL Nhóm 3" (PDF), đối chiếu `docs/spec.md`, báo cáo Word và code hiện tại.

## 1. Việc của Hiếu

| Lúc | Việc | Thời lượng | Căn cứ |
| --- | --- | --- | --- |
| Tối nay | Tập trọn kịch bản 2 lần cùng nhóm, bấm giờ | | |
| 15' trước giờ | Hồ sơ Chrome 5 (`admin`, Trụ sở) mở **Báo cáo › Doanh thu**, CN1, kỳ hôm nay → **chụp màn hình + chép số** (bảng mục 4) | | DT-01→05 |
| 0:00–0:45 | **Phần 0 – Phân quyền**: mở màn, lướt 5 cửa sổ | 45 giây | K-01, Bảng 6, Hình 11–13 |
| ~11:00–12:00 | **Bước 4.3 – Báo cáo doanh thu** + câu kết cả buổi (sau khi Chung làm 4.1–4.2) | ~1 phút | DT-01→05, Hình 28–29 |
| Hỏi đáp | Câu "chuyển nhân viên sang chi nhánh khác thì doanh số cũ đi đâu?" | | DT-05, NV-02, KT-15 |
| Nếu thầy yêu cầu | Các thao tác dùng hồ sơ Trụ sở (mục 6) | | |

> Kịch bản PDF chỉ ghi "Ngọc Chung, Minh Hiếu" cho Phần 4, không chia bước. Chia như trên là suy ra (Chung trả
> lời câu "Tổng doanh thu ca", Hiếu cầm hồ sơ Trụ sở). **Chốt lại với Chung tối nay.**

## 2. Kiến thức phải nắm chắc (theo thứ tự ưu tiên)

1. **K-01** – quyền gắn với vai trò + chi nhánh hiện tại, kiểm tra *tại thời điểm thao tác*; tài khoản Bị khóa không
   làm được gì. Trong code: mọi endpoint qua `require_role` (sai vai trò → lỗi 403, mã K-01); mỗi request đọc lại
   nhân viên từ CSDL nên khóa là mất quyền ngay; báo cáo của QL luôn bị ép về chi nhánh mình.
2. **Bảng 6 (ma trận phân quyền)** – menu từng vai trò (mục 3). Trụ sở không bán, không thu tiền; chỉ danh mục,
   nhân sự, chi nhánh, duyệt thay, báo cáo toàn chuỗi.
3. **DT-01 → DT-05** và **ba mốc thời gian không trộn**:
   - Doanh thu gộp theo lúc **đơn Hoàn tất** (DT-01), kể cả đơn sau đó bị trả.
   - Hàng bán bị trả theo lúc **phiếu trả Đã duyệt** (DT-02); Chờ duyệt, Từ chối không tính.
   - Thuần = gộp − trả, có thể âm (DT-03).
   - Tiền thu/hoàn theo lúc **giao dịch Thành công**, trình bày riêng theo phương thức, **không trừ lần hai** vào
     doanh thu; giao dịch Thất bại, Chờ kết quả, đơn Hủy không tạo doanh thu (DT-04).
   - Ghi cho **chi nhánh và người lập của đơn gốc**; tổng theo NV = tổng theo CN = tổng chuỗi (DT-05).
4. **Nhóm 5 không có kho riêng**: báo cáo tính lại từ chứng từ gốc mỗi lần mở, không lưu số tổng (đặc tả 4.5;
   dữ liệu dẫn xuất không lưu thành cột).
5. **K-05 + NV-02 + KT-15** (câu hỏi của mình) – xem mục 5.
6. **CA-02, CA-03** để đỡ lời cho Chung: tiền mặt kỳ vọng = đầu ca + thu tiền mặt Thành công − hoàn tiền mặt
   Thành công; thẻ/chuyển khoản/Thất bại không tính; lệch ≠ 0 bắt buộc lý do; còn giao dịch Chờ kết quả thì QL không
   chốt được; Đã chốt thì không sửa. "Tổng doanh thu ca" là **thu ròng của ca**, không phải doanh thu.
7. **K-02, K-03, K-04** (người duyệt ≠ người lập; lưu người–lúc–lý do; không sửa chứng từ đã hiệu lực) – thầy hay
   hỏi chéo.

Lưu ý lệch chữ: báo cáo mục 6.2.1 viết "tài khoản do Bộ phận nhân sự cấp", còn đặc tả 6.3 và kịch bản viết "Trụ sở
cấp". Khi nói dùng **"Trụ sở cấp"**.

## 3. Phần 0 – Phân quyền (45 giây)

Mỗi cửa sổ ~7 giây. Chỉ tay vào **góc phải** (vai trò · chi nhánh) rồi **menu trái**.

**Mở (đang ở cửa sổ Bán hàng):**
> "Em là Minh Hiếu. Trước khi vào nghiệp vụ, em chứng minh nguyên tắc K-01. Hệ thống không có ô chọn vai trò:
> vai trò và chi nhánh gắn với tài khoản do Trụ sở cấp, và quyền được kiểm tra ở mọi thao tác chứ không chỉ ẩn menu."

| Cửa sổ | Góc phải ghi | Menu thấy | Câu nói |
| --- | --- | --- | --- |
| 1 · Bán hàng | Nhân viên bán hàng · CN1 | Trang chủ, Doanh số nhân viên, Khách hàng, Đơn hàng, Phiếu trả | "Bán hàng chỉ có khách, đơn, phiếu trả và doanh số của chính mình." |
| 2 · Thu ngân | Thu ngân · CN1 | Ca thu ngân, Thu tiền, Hóa đơn, Hoàn tiền | "Thu ngân thu tiền, hoàn tiền nhưng không lập được đơn." |
| 3 · Quản lý | Quản lý cửa hàng · CN1 | Báo cáo, Đơn hàng, Phiếu trả, Ca, Tồn kho, Phiếu kho, Yêu cầu bổ sung, Cảnh báo tồn | "Quản lý duyệt và xem báo cáo, nhưng chỉ của CN1." |
| 4 · Kho | Nhân viên kho · CN1 | Báo cáo tồn kho, Tồn kho chi nhánh, Phiếu kho, Yêu cầu bổ sung, Cảnh báo tồn | "Kho chỉ thao tác hàng hóa." |
| 5 · Trụ sở | Trụ sở (không có CN) | thêm **Chi nhánh, Nhân viên, Nhóm sản phẩm, Sản phẩm**, báo cáo toàn chuỗi | "Trụ sở không thuộc chi nhánh nào, thấy thêm chi nhánh, nhân viên, sản phẩm. Đúng Bảng 6, Hình 12 và 13." |

**Chốt và chuyển lời:**
> "Ẩn menu chỉ là lớp giao diện; phía máy chủ mỗi thao tác đều kiểm tra lại vai trò và chi nhánh. Em mời bạn Danh
> vào phần bán hàng."

## 4. Bước 4.3 – Báo cáo doanh thu (~1 phút)

**Số chép trước demo (điền tối nay/sáng mai):**

| Chỉ tiêu (cột trên bảng) | Trước demo | Phải tăng | Sau demo |
| --- | --- | --- | --- |
| Số đơn | | +1 | |
| Doanh thu gộp | | +300.000 | |
| Giá trị hàng trả | | +200.000 | |
| Doanh thu thuần | | +100.000 | |
| Khách có hồ sơ | | +300.000 | |
| Chênh lệch ca | | −10.000 | |
| Còn phải hoàn | | 0 (không đổi) | |
| Thẻ – Thu (bấm **+** mở dòng CN1) | | +300.000 | |
| Thẻ – Hoàn | | +200.000 | |

Nếu nhóm đã chèn tình huống: W1 → cộng thêm đơn Q (+1 đơn, +200.000 gộp, +200.000 thẻ thu);
"QL tự lập phiếu trả" → hàng trả thêm +100.000, thuần −100.000.

**Nhận lời từ Chung (ca vừa Đã chốt):**
> "Ca đã chốt. Giờ em sang góc nhìn Trụ sở. Theo DT-01 đến DT-05, báo cáo không lưu số tổng mà tính lại từ chứng
> từ gốc mỗi lần mở. Em mở doanh thu CN1, kỳ hôm nay, so với ảnh chụp trước demo."

**Chỉ tay theo thứ tự:**
1. Số đơn, Doanh thu gộp: "Tăng một đơn, 300.000, đúng A×2 + B×1, ghi theo lúc đơn Hoàn tất (DT-01). Lần quẹt
   thẻ thất bại lúc nãy không tạo doanh thu (DT-04)."
2. Giá trị hàng trả: "Tăng 200.000, ghi theo lúc QL duyệt phiếu trả (DT-02), gồm cả ốp lưng lỗi dù hàng lỗi không
   vào tồn."
3. Doanh thu thuần: "Tăng 100.000, bằng 300 trừ 200 (DT-03)."
4. Bấm **+** mở dòng CN1, chỉ bảng phương thức: "Tiền thu và hoàn trình bày riêng: thẻ thu 300.000, hoàn 200.000.
   Tiền hoàn không trừ thêm vào doanh thu vì hàng trả đã trừ rồi (DT-04). Còn phải hoàn không đổi vì đã hoàn xong."
5. (Nếu còn giờ) "Chênh lệch ca −10.000 chính là ca bạn Chung vừa đóng; Khách có hồ sơ +300.000 vì đơn của Khách
   demo."

**Câu kết cả buổi:**
> "Tiền hoàn không trừ thêm lần thứ hai vào doanh thu, và báo cáo tính lại từ chứng từ gốc chứ không lưu số tổng.
> Nhóm em xin kết thúc phần demo, mời thầy đặt câu hỏi."

## 5. Hỏi đáp phần của Hiếu

**"Chuyển nhân viên sang chi nhánh khác thì doanh số cũ đi đâu?"** (DT-05, NV-02, KT-15)
> "Doanh số và hàng trả luôn ghi cho chi nhánh và người lập của đơn gốc, vì chứng từ chép mã chi nhánh và nhân viên
> lúc phát sinh, không suy lại từ hồ sơ hiện tại (K-05). Ví dụ KT-15: An bán đơn 1 triệu ở CN1 tháng 10, ngày 1/11
> chuyển sang CN2; phiếu trả 200.000 của đơn đó duyệt tháng 11 vẫn trừ vào An tại CN1, không vào CN2. Còn việc chuyển
> thì theo NV-02: nếu An còn ca chưa chốt, đơn Đang lập hoặc Chờ thanh toán, hay phiếu trả, phiếu kho chờ xử lý do
> mình lập thì Trụ sở đổi chi nhánh bị từ chối."

**Câu thầy dễ hỏi thêm sau Phần 0 / 4.3:**

| Câu hỏi | Trả lời ngắn |
| --- | --- |
| Gõ thẳng đường dẫn trang không có trong menu? | Giao diện đưa về trang chủ; máy chủ vẫn từ chối 403 với mã K-01 vì endpoint nào cũng qua kiểm tra vai trò. |
| Khóa tài khoản đang đăng nhập thì sao? | Mỗi thao tác đọc lại trạng thái từ CSDL, nên thao tác kế tiếp bị chặn ngay (K-01). |
| QL CN1 xem báo cáo CN2 được không? | Không. QL luôn bị giới hạn chi nhánh mình; chỉ Trụ sở chọn chi nhánh hoặc để trống là toàn chuỗi. |
| Sao Trụ sở không có Đơn hàng, Thu tiền? | Ma trận 2.2: Trụ sở không bán, không thu; chỉ danh mục, nhân sự, chi nhánh, duyệt thay, báo cáo. |
| Doanh thu thuần âm được không? | Được, nếu kỳ đó chỉ có hàng trả của đơn kỳ trước (DT-03). |
| Báo cáo lưu ở bảng nào? | Không lưu. Nhóm 5 chỉ đọc, tính lại từ chứng từ gốc mỗi lần lập. |
| Phiếu trả Chờ duyệt có trừ doanh thu không? | Không, chỉ phiếu Đã duyệt, theo thời điểm duyệt (DT-02). |
| Đổi nhóm sản phẩm thì báo cáo theo nhóm? | Dùng nhóm hiện tại và ghi rõ cơ sở này (DT-05). |

Câu hỏi CSDL: không tự chỉ vào CSDL; nếu bị hỏi, trả lời theo báo cáo mục 5.5 (18 tệp, tên không dấu, "#" là khóa;
tên bảng khi triển khai có thể khác nhưng ý nghĩa, liên kết, ràng buộc giữ nguyên).

## 6. Nếu thầy yêu cầu thêm và mình cầm hồ sơ Trụ sở

| Tình huống | Hiếu làm | Phải thấy |
| --- | --- | --- |
| W3 đổi giá sau chốt | Sản phẩm › C › đổi giá 120.000; xong đặt lại 100.000 | Đơn đã chốt vẫn 100.000 (SP-03, KT-02) |
| QL tự lập phiếu trả | Phiếu trả › Duyệt thay, **ghi lý do** | Trụ sở duyệt được; QL tự duyệt bị chặn (K-02, KT-15) |
| Sản phẩm ngừng bán | Sản phẩm › B › Ngừng bán; xong chuyển lại Đang bán | Chốt đơn có B bị chặn (SP-04, KT-13) |
| Đơn bỏ quên cuối ngày | Chi nhánh › CN1 giờ đóng cửa = giờ hiện tại + 2'; chờ ~1' sau mốc; **đặt lại 22:00** | Đơn chưa thu tự hủy "Quá hạn" (BH-05, KT-07). Chỉ làm cuối cùng. |
| Phiên hết hạn, quên mật khẩu | Nhân viên › cấp lại mật khẩu tạm | |

## 7. Đừng

- Không mở trang điều chuyển, không nói "đã kết nối ngân hàng", không chạy `make check` hay sửa SQL trước thầy.
- Không đổi giờ đóng cửa CN1 trừ tình huống cuối ngày; đổi xong đặt lại 22:00.
- Hết giờ: bỏ Phần 3 và bước 1.2, **giữ 4.3** (một trong hai điểm mạnh nhất).
- Bước báo lỗi lạ: đọc to thông báo và mã quy tắc; đúng quy tắc thì nói "hệ thống đang chặn đúng" rồi đi tiếp.
