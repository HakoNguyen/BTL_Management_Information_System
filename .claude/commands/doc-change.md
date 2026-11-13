Thay đổi tài liệu: $ARGUMENTS

1. Tìm mọi chỗ trong `docs/` (spec.md, db.md, api.md, tests.md, plan.md) và CLAUDE.md của các thư mục có nhắc tới
   nội dung này.
2. Đề xuất bản sửa cho từng chỗ, dạng bảng: file, mục, câu cũ, câu mới. CHƯA sửa, chờ tôi duyệt.
3. Sau khi tôi duyệt: sửa đúng các chỗ đó, giữ nguyên văn phong và định dạng bảng.
4. Kiểm tra nhất quán: tên, trạng thái, con số liên quan ở các file khác vẫn khớp (ví dụ mã trạng thái ở db.md mục 3
   với `common/constants.py` và CHECK trong migration). Liệt kê chỗ nào còn lệch.
5. Liệt kê file code và test đang dùng nội dung cũ (tìm trong `common/`, `api/`, `db/`, `web/src/`, `tests/`) để tôi
   biết cần sửa ở đâu. Không tự sửa code. Thay đổi schema cần file migration mới, không sửa file đã có.
