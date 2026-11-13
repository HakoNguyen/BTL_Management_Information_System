## Vòng và chức năng đã làm
<!-- ví dụ: Vòng 5 – 3.1 lập, chốt, mở lại đơn; 3.4 hủy đơn (BH-01..04) -->

## Test
<!-- file test và kết quả: KT-02 xanh, KT-03 xanh; tests/orders 31 đạt; kết quả make check -->

## File đã sửa
<!-- theo mẫu ở docs/plan.md mục 4; file nào ngoài mẫu thì ghi lý do -->

## Checklist
- [ ] Mọi tên bảng, cột, endpoint, tên trường, mã lỗi, mã trạng thái có trong `docs/`; dùng enum trong `common/constants.py`
- [ ] `docs/api.md` đã có tên trường của endpoint mới; `web/src/api/schema.d.ts` đã sinh lại (`make gen-api`)
- [ ] Chỉ ghi vào bảng của kho mình sở hữu; thay đổi kho khác đi qua hàm giao ở `docs/api.md` mục 5, cùng transaction
- [ ] Tồn chỉ đổi trong `services/inventory.py`, qua phiếu kho; giữ hàng có khóa dòng `stock`
- [ ] Cập nhật trạng thái có điều kiện trạng thái liền trước; không sửa, xóa chứng từ đã có hiệu lực (K-04, K-05)
- [ ] Người duyệt khác người lập; quyết định lưu người, thời điểm, lý do (K-02, K-03)
- [ ] Endpoint nào cũng qua `require_role`; service kiểm tra chi nhánh của người dùng (K-01)
- [ ] Thời gian lấy từ `clock.now()`; không gọi HTTP trong transaction; tiền và số lượng là số nguyên
- [ ] Dữ liệu dẫn xuất không lưu thành cột (`docs/db.md` mục 6)
- [ ] Lỗi nghiệp vụ là `AppError` kèm mã quy tắc; không có lỗi ràng buộc CSDL lọt ra thành 500
- [ ] Mỗi quy tắc của vòng có test; tình huống KT assert đủ cột "Kết quả kỳ vọng"; `make check` xanh
- [ ] Đã cập nhật tiến độ ở `docs/plan.md` mục 1 và `docs/tests.md` mục 3

## Giả định còn mở
