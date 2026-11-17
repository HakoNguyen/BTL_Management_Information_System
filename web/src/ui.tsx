// Mẫu dùng chung cho các trang: ghi dữ liệu qua useMutation và hộp thoại biểu mẫu.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, DatePicker, Form, Modal, Select, message } from "antd";
import { useState, type ReactNode } from "react";
import { client, unwrap, type Schemas } from "./api/client";
import type { DateRange } from "./dateRange";
import { money } from "./format";

/** Màu chủ đạo (xanh dương) và nền thanh bên, dùng ở theme và trang đăng nhập. */
export const BRAND = "#1677ff";
export const NAVY = "#0b2e5c";

type StatusCode =
  | Schemas["BranchStatus"]
  | Schemas["EmployeeStatus"]
  | Schemas["AccountStatus"]
  | Schemas["ProductStatus"]
  | Schemas["LevelStatus"]
  | Schemas["TxnStatus"]
  | Schemas["ShiftStatus"]
  | Schemas["SlipStatus"]
  | Schemas["OrderStatus"]
  | Schemas["ReturnStatus"]
  | Schemas["RefundStatus"];

const POSITIVE = "blue";
const NEGATIVE = "volcano";
const WAITING = "gold";
const NEUTRAL = "default";

/** Màu tag trạng thái: tích cực xanh, tiêu cực đỏ cam, chờ người khác xử lý vàng, còn lại xám. */
export const STATUS_COLOR: Record<StatusCode, string> = {
  ACTIVE: POSITIVE,
  INACTIVE: NEGATIVE,
  WORKING: POSITIVE,
  LEFT: NEGATIVE,
  LOCKED: NEGATIVE,
  ON_SALE: POSITIVE,
  DISCONTINUED: NEGATIVE,
  OK: POSITIVE,
  BELOW_MIN: NEGATIVE,
  NOT_SET: NEUTRAL,
  SUCCESS: POSITIVE,
  FAILED: NEGATIVE,
  PENDING: WAITING,
  OPEN: NEUTRAL,
  AWAITING_CONFIRMATION: WAITING,
  SETTLED: POSITIVE,
  POSTED: POSITIVE,
  CANCELLED: NEGATIVE,
  DRAFT: NEUTRAL,
  AWAITING_PAYMENT: WAITING,
  COMPLETED: POSITIVE,
  PARTIALLY_RETURNED: WAITING,
  FULLY_RETURNED: NEGATIVE,
  APPROVED: POSITIVE,
  REJECTED: NEGATIVE,
  NOT_REFUNDED: NEGATIVE,
  REFUNDED: POSITIVE,
};

/** Ghi dữ liệu: báo kết quả (lỗi hiện đúng thông báo của API), rồi tải lại các khóa trong `keys`. */
export function useWrite<V, R>(fn: (values: V) => Promise<R>, keys: string[]) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      message.success("Đã lưu");
      keys.forEach((key) => queryClient.invalidateQueries({ queryKey: [key] }));
    },
    onError: (error) => message.error(error.message, 6),
  });
}

type FormModalProps<T> = {
  title: string;
  initialValues?: Partial<T>;
  onClose: () => void;
  onSubmit: (values: T) => Promise<unknown>;
  children: ReactNode;
};

/** Hộp thoại biểu mẫu; trang chỉ render khi cần mở. Ghi thành công thì đóng, lỗi thì giữ để sửa. */
export function FormModal<T extends object>(props: FormModalProps<T>) {
  const { title, initialValues, onClose, onSubmit, children } = props;
  const [form] = Form.useForm<T>();
  const [saving, setSaving] = useState(false);

  const finish = async (values: T) => {
    // Ô để trống gửi null (xóa giá trị), không gửi chuỗi rỗng
    const body = Object.fromEntries(
      Object.entries(values).map(([key, value]) => [key, value === "" ? null : value]),
    ) as T;
    setSaving(true);
    try {
      await onSubmit(body);
      onClose();
    } catch {
      // Lỗi đã được useWrite báo
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      title={title}
      okText="Lưu"
      cancelText="Hủy"
      confirmLoading={saving}
      onOk={form.submit}
      onCancel={onClose}
    >
      <Form<T> form={form} layout="vertical" initialValues={initialValues} onFinish={finish}>
        {children}
      </Form>
    </Modal>
  );
}

/** Ô lọc chi nhánh cho danh sách nhiều chi nhánh (Trụ sở); để trống = mọi chi nhánh. */
export function BranchFilter({
  value,
  onChange,
}: {
  value?: string;
  onChange: (branchId?: string) => void;
}) {
  const branches = useQuery({ queryKey: ["branches"], queryFn: () => unwrap(client.GET("/branches")) });
  return (
    <Select
      allowClear
      placeholder="Mọi chi nhánh"
      style={{ minWidth: 170 }}
      value={value}
      onChange={onChange}
      options={(branches.data ?? []).map((b) => ({ value: b.branch_id, label: `${b.branch_id} – ${b.name}` }))}
    />
  );
}

/** Nút bỏ một dòng trong danh sách dòng của biểu mẫu (dòng hàng đơn, phiếu kho, phiếu trả…). */
export function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <Button type="text" danger title="Bỏ dòng" aria-label="Bỏ dòng" onClick={onClick}>
      ✕
    </Button>
  );
}

/** Nút thêm dòng, viền nét đứt dài hết hàng, đặt dưới danh sách dòng của biểu mẫu. */
export function AddButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <Button type="dashed" block onClick={onClick}>
      {children}
    </Button>
  );
}

/** Ô chọn khoảng ngày để lọc danh sách chứng từ; xóa trống = mọi ngày. */
export function DateRangeFilter({ onChange }: { onChange: (range: DateRange) => void }) {
  return (
    <DatePicker.RangePicker
      allowClear
      format="DD/MM/YYYY"
      placeholder={["Từ ngày", "Đến ngày"]}
      onChange={(values) =>
        onChange(
          values?.[0] && values[1]
            ? [values[0].format("YYYY-MM-DD"), values[1].format("YYYY-MM-DD")]
            : null,
        )
      }
    />
  );
}

/** Cột tiền của Table, căn phải. */
export const moneyColumn = (title: string, dataIndex: string) => ({
  title,
  dataIndex,
  align: "right" as const,
  render: money,
});
