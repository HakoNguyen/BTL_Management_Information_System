# web/

Giao diện React 18 + Vite + TypeScript + Ant Design 5 + TanStack Query 5, phục vụ qua nginx ở cổng 3000.

- `src/api/client.ts`: cách DUY NHẤT để gọi API: `unwrap(client.GET("/đường-dẫn"))`. Không dùng `fetch` trực tiếp,
  không thêm axios. Lỗi API thành `ApiError` (`code`, `message`, `details.rule`).
- `src/api/schema.d.ts`: sinh từ OpenAPI bằng `make gen-api`. Không sửa tay. Kiểu dữ liệu lấy từ đây
  (`Schemas["TênModel"]`), không tự khai báo lại tên trường.
- `src/features/<module>/`: trang của từng module, cùng tên với `api/services/<module>.py`.
- `src/menu.tsx`: mỗi trang đăng ký bằng một dòng, kèm danh sách vai trò được thấy (ma trận 2.2).
- `src/labels.ts`: nhãn tiếng Việt cho mã vai trò, trạng thái, loại. Giao diện không hiển thị mã thô.
- `src/auth.tsx`: phiên đăng nhập. Ẩn menu theo vai trò chỉ để tiện dùng; quyền thật do API kiểm tra.
- Dữ liệu từ server dùng `useQuery`/`useMutation`; không tự viết `useEffect` để gọi API. Sau khi ghi thì
  `invalidateQueries` đúng khóa liên quan.
- Thành phần giao diện dùng của Ant Design (Table, Form, Modal, Descriptions…); không thêm thư viện giao diện khác,
  không viết lại thành phần đã có sẵn.
- Tiền hiển thị bằng `toLocaleString("vi-VN")`; không làm tính toán nghiệp vụ ở giao diện, số liệu lấy từ API.
- Test (`*.test.ts`, vitest) chỉ cho logic thuần. Kiểm tra: `npm run typecheck`, `npm test`.

Quy tắc chung xem CLAUDE.md ở gốc repo.
