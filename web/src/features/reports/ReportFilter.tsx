// Bộ lọc và phần đầu chung của báo cáo 5.1, 5.2, 5.3, 5.5 (docs/api.md nhóm 5).
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Form, Input, Select } from "antd";
import type { ReactNode } from "react";
import { client, unwrap } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime } from "../../format";

/** Kỳ lọc tính cả hai đầu; `branch_id` bỏ trống = toàn chuỗi (chỉ Trụ sở được chọn). */
export type ReportParams = { from: string; to: string; branch_id?: string };

// Ngày hôm nay theo giờ Việt Nam, dạng YYYY-MM-DD, làm kỳ mặc định
export const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });

export function ReportFilter<T extends ReportParams>(props: {
  onSubmit: (params: T) => void;
  initialValues?: Partial<T>;
  children?: ReactNode;
}) {
  // Chỉ Trụ sở được chọn chi nhánh; vai trò khác API luôn lấy chi nhánh mình (nhóm 5)
  const isHQ = useAuth().user?.role === "HQ";
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => unwrap(client.GET("/branches")),
    enabled: isHQ,
  });
  return (
    <Form<T>
      layout="inline"
      style={{ marginBottom: 16, rowGap: 8 }}
      initialValues={{ from: today(), to: today(), ...props.initialValues } as T}
      onFinish={props.onSubmit}
    >
      <Form.Item label="Từ ngày" name="from" rules={[{ required: true }]}>
        <Input type="date" />
      </Form.Item>
      <Form.Item label="Đến ngày" name="to" rules={[{ required: true }]}>
        <Input type="date" />
      </Form.Item>
      {isHQ && (
        <Form.Item label="Chi nhánh" name="branch_id">
          <Select
            allowClear
            placeholder="Toàn chuỗi"
            style={{ minWidth: 200 }}
            options={(branches.data ?? []).map((branch) => ({
              value: branch.branch_id,
              label: `${branch.branch_id} – ${branch.name}`,
            }))}
          />
        </Form.Item>
      )}
      {props.children}
      <Button type="primary" htmlType="submit">
        Xem báo cáo
      </Button>
    </Form>
  );
}

type Header = { branch_id: string | null; from_date: string; to_date: string; generated_at: string };

/** Phạm vi chi nhánh, kỳ lọc, thời điểm lập; hoặc lỗi của API. */
export function ReportHeader({ report, error }: { report?: Header; error: Error | null }) {
  if (error) return <Alert type="error" showIcon message={error.message} />;
  if (!report) return null;
  return (
    <Descriptions
      size="small"
      style={{ marginBottom: 16 }}
      items={[
        { key: "branch", label: "Phạm vi", children: report.branch_id ?? "Toàn chuỗi" },
        { key: "period", label: "Kỳ", children: `${report.from_date} đến ${report.to_date}` },
        { key: "at", label: "Lập lúc", children: dateTime(report.generated_at) },
      ]}
    />
  );
}
