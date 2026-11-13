Theo kế hoạch đã duyệt, viết test trước cho: $ARGUMENTS

- Trước hết tạo nhánh của vòng (tên ở `docs/plan.md` mục 1, cách tách ở CLAUDE.md mục Git): `git switch -c <nhánh>`.
- Ghi các tên trường đã duyệt vào `docs/api.md` và thêm model tương ứng vào `common/models.py`
  (chỉ model, chưa có code xử lý).
- Đặt test trong `tests/<module>/` theo quy ước ở `docs/tests.md` mục 1. Tình huống KT: một file
  `test_ktXX_<ten_ngan>.py` cho đúng một tình huống, assert đủ mọi ý trong cột "Kết quả kỳ vọng".
- Test theo quy tắc: mỗi quy tắc ít nhất một test cho trường hợp hợp lệ và một test cho từng cách vi phạm; assert
  `error_code` và `details.rule`. Có cả test phân quyền: vai trò không được phép nhận `FORBIDDEN`, và nhân viên chi
  nhánh khác không thao tác được chứng từ của chi nhánh này.
- Dùng mã và hàm dựng dữ liệu trong `tests/fixtures.py`; cần dữ liệu mới thì thêm hàm vào đó.
- Ngày giờ dùng `clock.freeze(...)`.
- Chưa viết code nghiệp vụ. Chạy pytest và xác nhận test đang đỏ vì thiếu chức năng (404, thiếu hàm), không phải vì
  lỗi cú pháp, lỗi import hay lỗi dựng dữ liệu. Báo số test và lý do đỏ.
