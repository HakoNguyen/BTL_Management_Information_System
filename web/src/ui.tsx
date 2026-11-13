// Mẫu dùng chung cho các trang: ghi dữ liệu qua useMutation và hộp thoại biểu mẫu.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Form, Modal, message } from "antd";
import { useState, type ReactNode } from "react";
import { money } from "./format";

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

/** Cột tiền của Table, căn phải. */
export const moneyColumn = (title: string, dataIndex: string) => ({
  title,
  dataIndex,
  align: "right" as const,
  render: money,
});
