Tự duyệt thay đổi hiện tại (`git status`, `git diff`; nếu repo chưa có commit nào thì đọc các file của vòng vừa làm)
trước khi commit.

1. Đối chiếu với từng ý trong checklist ở `.github/pull_request_template.md`.
   Với mỗi ý: ĐẠT / KHÔNG ĐẠT / KHÔNG ÁP DỤNG, kèm file và dòng code làm bằng chứng.
2. Kiểm tra mọi tên bảng, cột, endpoint, tên trường, mã lỗi, mã trạng thái trong thay đổi đều có trong `docs/`.
   Liệt kê tên nào không tìm thấy.
3. Đối chiếu từng quy tắc của vòng này (cột "Quy tắc" ở `docs/plan.md` mục 1) với code: quy tắc nào được ép ở đâu
   (file:dòng) và test nào chứng minh. Liệt kê quy tắc chưa có test.
4. Tìm lệnh ghi vào bảng của kho khác (`docs/db.md` mục 2), lệnh sửa `stock.quantity` ngoài `services/inventory.py`,
   chỗ dùng `datetime.now()` hoặc `now()` của SQL, chuỗi trạng thái viết trực tiếp, `float` cho tiền.
5. Chạy `make check` và ghi kết quả thật.
6. Viết mô tả thay đổi theo mẫu `.github/pull_request_template.md` để tôi dùng làm nội dung pull request.
Không tự sửa code ở bước này; chỉ báo cáo. Ý nào KHÔNG ĐẠT thì đề xuất cách sửa và dừng lại.
Mọi ý đều ĐẠT thì làm theo CLAUDE.md mục Git: commit trên nhánh của vòng với message tiếng Anh, liệt kê commit và
file sẽ được đẩy, rồi hỏi tôi trước khi push.
