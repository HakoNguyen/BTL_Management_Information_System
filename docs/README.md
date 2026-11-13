# docs/ – Nguồn sự thật của dự án

Các file trong thư mục này là hợp đồng mà code phải theo. Khi tài liệu và code lệch nhau thì dừng và báo.

| File | Nội dung |
|---|---|
| [spec.md](spec.md) | Đặc tả nghiệp vụ (chuẩn cao nhất): quy trình, chức năng, quy tắc, dữ liệu, 16 tình huống kiểm tra |
| [db.md](db.md) | Thiết kế CSDL: đối chiếu 18 bảng, mã trạng thái, ràng buộc, dữ liệu dẫn xuất, mã chứng từ |
| [api.md](api.md) | Hợp đồng API: dạng lỗi, endpoint theo nhóm chức năng, hàm giao giữa các module |
| [tests.md](tests.md) | Quy ước kiểm thử, mã cố định, bảng tình huống KT và trạng thái |
| [plan.md](plan.md) | Tiến độ, thứ tự các vòng, phân vai, quyết định đã chốt |
| [img/](img/) | BFD, DFD mức 0 và mức 1, ERD, sơ đồ vòng đời đơn hàng |

## Quy tắc sửa
- Thứ tự ưu tiên khi mâu thuẫn: `spec.md` > `db.md` > `api.md`.
- `spec.md` là bản chuyển nguyên văn từ file Word của nhóm; không sửa tay.
- Thay đổi hợp đồng đã chốt (tên, endpoint, mã lỗi, trạng thái, quy tắc): dùng lệnh `/doc-change` để mọi chỗ liên quan
  được sửa cùng lúc, và sửa `docs/` TRƯỚC khi sửa code.
- Bổ sung phần còn để khung (tên trường của endpoint mới ở `api.md`, trạng thái tình huống ở `tests.md`, tiến độ ở
  `plan.md`) là việc thường xuyên của mỗi vòng, làm trong bước `/plan-task` và khi kết thúc vòng.
