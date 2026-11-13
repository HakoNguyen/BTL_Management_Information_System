// 5.3 Tồn kho: tồn, khả dụng, mức ngưỡng (TK-01, TK-05) và biến động xuất hủy, điều chỉnh trong kỳ.
import { useQuery } from "@tanstack/react-query";
import { Card, Table, Tag, Typography, type TableColumnsType } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { LEVEL_STATUS_LABEL, SLIP_TYPE_LABEL } from "../../labels";
import { ReportFilter, ReportHeader, type ReportParams } from "./ReportFilter";

const LEVEL_COLOR: Record<Schemas["LevelStatus"], string> = {
  BELOW_MIN: "red",
  OK: "green",
  NOT_SET: "default",
};

/** Cột tồn tại thời điểm lập (dòng `StockReportLine`); dùng chung với trang tồn kho chi nhánh. */
export const stockLineColumns: TableColumnsType<Schemas["StockReportLine"]> = [
  { title: "Chi nhánh", dataIndex: "branch_id" },
  { title: "Mã", dataIndex: "product_id" },
  { title: "Tên", dataIndex: "name" },
  { title: "Tồn", dataIndex: "quantity", align: "right" },
  { title: "Khả dụng", dataIndex: "available", align: "right" },
  {
    title: "Ngưỡng tối thiểu",
    dataIndex: "min_level",
    align: "right",
    render: (level: number | null) => level ?? "—",
  },
  {
    title: "Mức tồn",
    dataIndex: "level_status",
    render: (status: Schemas["LevelStatus"]) => (
      <Tag color={LEVEL_COLOR[status]}>{LEVEL_STATUS_LABEL[status]}</Tag>
    ),
  },
];

export function StockReportPage() {
  const [params, setParams] = useState<ReportParams | null>(null);
  const report = useQuery({
    queryKey: ["reports", "stock", params],
    queryFn: () => unwrap(client.GET("/reports/stock", { params: { query: params! } })),
    enabled: params !== null,
  });
  const data = report.data;

  return (
    <Card title="Báo cáo tồn kho">
      <ReportFilter onSubmit={setParams} />
      <ReportHeader report={data} error={report.error} />
      {data && (
        <>
          <Typography.Title level={5}>Tồn tại thời điểm lập</Typography.Title>
          <Table<Schemas["StockReportLine"]>
            rowKey={(line) => `${line.branch_id}-${line.product_id}`}
            dataSource={data.lines}
            scroll={{ x: true }}
            columns={stockLineColumns}
          />
          <Typography.Title level={5}>Xuất hủy và điều chỉnh trong kỳ</Typography.Title>
          <Table<Schemas["StockMovementLine"]>
            rowKey={(line) => `${line.branch_id}-${line.type}-${line.reason}-${line.product_id}`}
            dataSource={data.movements}
            columns={[
              { title: "Chi nhánh", dataIndex: "branch_id" },
              {
                title: "Loại",
                dataIndex: "type",
                render: (type: Schemas["SlipType"]) => SLIP_TYPE_LABEL[type],
              },
              { title: "Lý do", dataIndex: "reason" },
              { title: "Mã SP", dataIndex: "product_id" },
              { title: "Số lượng", dataIndex: "quantity", align: "right" },
            ]}
          />
        </>
      )}
    </Card>
  );
}
