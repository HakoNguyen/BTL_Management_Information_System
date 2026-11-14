# Việc cần sửa sau đợt rà soát nghiệp vụ (13/11/2026)

Kết quả rà soát toàn bộ code so với `docs/spec.md` (đặc tả, ERD 5.7, DFD 6.1–6.3, BFD). Đã khớp: đủ 27 chức năng,
18 bảng, ranh giới ghi kho, đường chuyển trạng thái, 16/16 tình huống KT có test. Các mục dưới đây là phần còn lệch.
Nhánh làm việc: `refactor/spec-gaps`. Làm xong mục nào thì đánh dấu `[x]` và ghi tên test chứng minh.

Mức ảnh hưởng: **Cao** = sai tiền, tồn hoặc làm kẹt nghiệp vụ; **Vừa** = sai đặc tả, có thể lộ khi bảo vệ;
**Thấp** = chỉ là hiển thị hoặc dữ liệu thừa.

## A. Sai so với đặc tả – sửa trước

- [x] **A1. Chi nhánh Ngừng hoạt động vẫn lập được đơn** (NV-04). Mức: Thấp.
  - Chỗ lỗi: `api/services/orders.py:117` (`create_order`) không đọc `branches.status`; đơn chỉ bị chặn khi chốt (`:164`).
  - Ảnh hưởng: chỉ sinh đơn Đang lập rác, không chốt, không thu tiền được và bị tự hủy lúc đóng cửa. Không sai tiền, tồn.
  - Cách sửa: kiểm trạng thái chi nhánh trong `create_order`, trả `RULE_VIOLATION` `rule` = NV-04 (giống `confirm_order`).
  - Test: `tests/orders/test_orders.py` thêm `test_create_inactive_branch`. **Đã xong**, chứng minh bởi
    `test_create_inactive_branch`.

- [x] **A2. Khách lẻ (KHLE) không có hóa đơn vẫn trả được hàng** (TH-01). Mức: Vừa.
  - Chỗ lỗi: `api/services/returns.py` (`create_return`, khoảng dòng 204–262) không xét khách KHLE;
    `ReturnCreate` (`common/models.py:455`) chỉ có `order_id`; `web/src/features/returns/ReturnsPage.tsx:52–58`
    cho chọn mọi đơn của chi nhánh.
  - Ảnh hưởng: hoàn tiền cho người không chứng minh được đã mua; đúng chỗ đặc tả muốn kiểm soát (mục tiêu 1.2).
  - Cách sửa: thêm trường `invoice_presented: bool` vào `ReturnCreate`; đơn của KHLE mà `false` thì `RULE_VIOLATION`
    `rule` = TH-01. Ghi trường mới vào `docs/api.md` TRƯỚC, chạy `make gen-api`, thêm ô "Khách xuất trình hóa đơn" ở form.
  - Test: `tests/returns/test_returns.py` thêm trường hợp KHLE có và không có hóa đơn; khách có hồ sơ không cần hóa đơn.
  - **Đã xong** (`invoice_presented` chỉ ở request, không lưu CSDL), chứng minh bởi `test_walk_in_needs_invoice`,
    `test_registered_customer_without_invoice`.

- [ ] **A3. Lập yêu cầu bổ sung (4.4) không hiện tồn và ngưỡng hiện tại.** Mức: Thấp.
  - Chỗ lỗi: `web/src/features/inventory/ReplenishmentPage.tsx` dùng `ItemsField`, chỉ hiện "khả dụng"
    (`web/src/features/orders/ItemsField.tsx:47–52`).
  - Ảnh hưởng: chỉ giao diện; số liệu vẫn xem được ở trang Tồn kho chi nhánh.
  - Cách sửa: ở trang yêu cầu bổ sung, hiện tồn và ngưỡng của sản phẩm đang chọn (lấy từ `GET /stock`), không đổi API.

- [x] **A4. Giao diện không tra soát được giao dịch Chờ kết quả của ca đã đóng.** Mức: Vừa (gần Cao khi chạy thật).
  - Chỗ lỗi: `web/src/features/payments/PendingTransactions.tsx:19` chỉ dùng `useCurrentShift()` (ca đang mở);
    `web/src/features/shifts/ShiftsPage.tsx:174` liệt kê giao dịch chờ nhưng không có nút.
  - Ảnh hưởng: ngân hàng không phản hồi rồi thu ngân đóng ca thì giao dịch kẹt, ca không chốt được (CA-03); KT-05 và
    KT-16 không đi hết trên giao diện. API `POST /transactions/{id}/reconcile` vẫn làm được.
  - Cách sửa: thêm nút Tra soát cho giao dịch Chờ kết quả trong chi tiết ca (ca Chờ xác nhận của thu ngân), dùng lại
    hộp thoại tra soát hiện có.
  - **Đã xong**, chứng minh bởi `web/src/features/shifts/shiftActions.test.ts` "tra soát giao dịch điện tử Chờ kết
    quả trong ca Chờ xác nhận, chỉ thu ngân" (`canReconcile`).

## B. Lệch có chủ đích – cần chốt: sửa code hay sửa đặc tả (`/doc-change`)

- [x] **B1. Trụ sở không xác nhận chốt được ca thường khi QL vắng** (quyết định 14). Mức: Vừa. **Nên sửa.**
  - `api/services/shifts.py:285–288` chặn HQ; đặc tả 2.2 ghi "3.5 Xác nhận chốt ca: Trụ sở Duyệt thay".
  - Hệ quả dây chuyền: ca kẹt Chờ xác nhận, kéo theo chặn đổi phân công (NV-02) và đóng chi nhánh (NV-04).
  - Cách sửa: cho HQ xác nhận ca thường kèm lý do bắt buộc (như duyệt thay phiếu trả); sửa
    `tests/shifts/test_shifts.py::test_confirm_shift_forbidden` theo quy tắc mới; cập nhật quyết định 14 ở `docs/plan.md`.
  - **Đã xong** (cột `shifts.confirm_reason`, migration 004), chứng minh bởi `test_hq_confirm_requires_reason`,
    `test_manager_confirm_reason_optional`, `test_confirm_shift_forbidden` (đã sửa), `shiftActions.test.ts`.
- [ ] **B2. Cảnh báo 5.4 không chạy theo lịch mỗi sáng** (quyết định 6). Mức: Thấp.
  - Đặc tả dòng 310, 520: "tự chạy mỗi sáng". Code tính lúc mở trang (`api/services/reports.py:55`).
  - Chọn một: giữ cách hiện tại và sửa đặc tả bằng `/doc-change`, hoặc thêm worker giống `api/workers/closing.py`.
- [ ] **B3. Trụ sở duyệt thay phiếu trả, hoàn tiền mặt bất cứ lúc nào** (quyết định 15). Mức: Thấp. Hệ thống không biết
  QL vắng; giữ nguyên, ghi vào báo cáo phần quyết định thiết kế.
- [ ] **B4. Duyệt hoàn tiền mặt ghi lên giao dịch Hoàn đã Thất bại** (`api/services/payments.py:355–361`). Mức: Thấp.
  Chạm K-04; cũng không chặn khi ca của giao dịch đó đã chốt. Tối thiểu: chặn khi ca đã chốt.
- [ ] **B5. QL duyệt phiếu trả, xác nhận chốt ca không bắt buộc lý do** (`api/services/returns.py:313`,
  `api/services/shifts.py:296`). K-03 ghi mọi quyết định duyệt lưu lý do. Mức: Thấp.

## C. Kẹt nghiệp vụ, đặc tả không rõ – ghi vào báo cáo, sửa nếu còn thời gian

- [ ] **C1.** Thu ngân vắng mà còn giao dịch tiền mặt Chờ kết quả: QL không đóng ca thay được (CA-02 chặn,
  `api/services/shifts.py:200`) và không có quyền xác nhận tiền mặt (`api/routers/payments.py:24, 36`).
- [ ] **C2.** Khe tối đa 60 giây sau giờ đóng cửa (`api/workers/closing.py:21`): vẫn duyệt phiếu trả, thu tiền được cho
  chứng từ lẽ ra đã quá hạn.
- [ ] **C3.** Tranh chấp đồng thời NV-02, NV-04: mở ca, nhập hàng, lập đơn không khóa dòng chi nhánh hoặc nhân viên
  (`api/services/shifts.py:161`, `api/services/inventory.py:265`, `api/services/staff.py:103, 284`).
- [ ] **C4.** Thu ngân xác nhận tiền mặt, tra soát được giao dịch thuộc ca của thu ngân khác cùng chi nhánh
  (`api/services/payments.py:224, 236`).

## D. Thiếu test

- [ ] KT-05 chưa kiểm ý "đơn có giao dịch Chờ kết quả không bị hủy lúc đóng cửa" (gọi `run_closing` trong test).
- [ ] TH-02: bước kiểm tra lại khi duyệt (`api/services/returns.py:329`).
- [ ] TT-03: cả giao dịch cuộn lại khi `confirm_sale` hoặc phát hành hóa đơn lỗi.
- [ ] Phản hồi lặp của ngân hàng mang kết quả khác (Thành công đến sau Thất bại) bị bỏ qua mà không log
  (`api/services/payments.py:251–252`); thêm log cảnh báo và test.
- [ ] SP-04: sản phẩm Ngừng bán vẫn được nhận trả.
- [ ] KT-11 đang dựng giao dịch hoàn bằng SQL dù API đã có; KT-01, KT-04, KT-09 kiểm doanh thu không qua báo cáo 5.1.

## E. Lệch nhỏ

- 5.1 tỷ trọng khách có hồ sơ/KHLE chỉ hiện số tiền, chưa có %; so kỳ trước chỉ ở dòng tổng.
- 5.2 không có mục top 10 riêng; chưa ghi "theo nhóm sản phẩm hiện tại" trên báo cáo (DT-05).
- Phiếu xuất trả kho tổng không lưu bên nhận (`StockSlipCreate`, `common/models.py:263`).
- So trùng phiếu giao phân biệt hoa thường, khoảng trắng của bên giao (TK-02).
- Trụ sở có thể tự khóa tài khoản trụ sở cuối cùng; nhân viên Đã nghỉ đăng nhập nhận thông báo "đang bị khóa".

## Thứ tự gợi ý

A1 → A4 → B1 → A2 (cần sửa `docs/api.md` trước) → A3 → D (KT-05) → phần còn lại nếu còn thời gian.
Mỗi mục làm xong: `make check` xanh, đánh dấu `[x]` ở file này.
