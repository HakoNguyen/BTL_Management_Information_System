Viết code để các test vừa viết chuyển xanh, cho việc: $ARGUMENTS

- Làm đúng thứ tự các bước xử lý của chức năng trong đặc tả. Không thêm bước, không thêm tính năng ngoài đặc tả.
- Chỉ sửa các file đã liệt kê trong kế hoạch. Cần sửa file khác thì dừng và hỏi.
- Tuân thủ mục "Quy tắc nghiệp vụ không được vi phạm" và "Cách làm" trong CLAUDE.md: mỗi kho một chủ, trạng thái chỉ
  đi tới, `clock.now()`, enum trong `common/constants.py`, `AppError` kèm mã quy tắc, router mỏng.
- Không sửa test để cho xanh. Nếu thấy test sai so với đặc tả thì dừng và nêu rõ chỗ sai.
- Đăng ký router bằng một dòng trong `api/main.py`. Chạy `make gen-api` để cập nhật `web/src/api/schema.d.ts`.
- Chạy `make check` tới khi xanh. Báo kết quả thật: số test đạt, số test trượt, phần nào chưa làm.
- Cập nhật tiến độ: `docs/plan.md` mục 1 và cột "Trạng thái" trong `docs/tests.md` mục 3.
