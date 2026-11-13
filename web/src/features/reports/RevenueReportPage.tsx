// 5.1 Doanh thu (DT-01..DT-05). Mọi số liệu do API tính; trang chỉ hiển thị.
import { useQuery } from "@tanstack/react-query";
import { Card, Space, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { TXN_METHOD_LABEL, TXN_TYPE_LABEL } from "../../labels";
import { moneyColumn } from "../../ui";
import { ReportFilter, ReportHeader, type ReportParams } from "./ReportFilter";

type Summary = Schemas["RevenueSummary"];
type Row = Summary & { key: string; label: string };

export function RevenueReportPage() {
  const [params, setParams] = useState<ReportParams | null>(null);
  const report = useQuery({
    queryKey: ["reports", "revenue", params],
    queryFn: () => unwrap(client.GET("/reports/revenue", { params: { query: params! } })),
    enabled: params !== null,
  });

  const data = report.data;
  const rows: Row[] = data
    ? [
        ...data.branches.map((s) => ({ ...s, key: s.branch_id ?? "", label: s.branch_id ?? "" })),
        { ...data.total, key: "total", label: "Tổng" },
        { ...data.previous, key: "previous", label: "Kỳ trước (tổng)" },
      ]
    : [];

  return (
    <Card title="Báo cáo doanh thu">
      <ReportFilter onSubmit={setParams} />
      <ReportHeader report={data} error={report.error} />
      {data && (
        <Table<Row>
          rowKey="key"
          dataSource={rows}
          pagination={false}
          scroll={{ x: true }}
          expandable={{ expandedRowRender: (row) => <Details summary={row} /> }}
          columns={[
            { title: "Chi nhánh", dataIndex: "label" },
            { title: "Số đơn", dataIndex: "order_count", align: "right" },
            moneyColumn("Doanh thu gộp", "gross_revenue"),
            moneyColumn("Giá trị hàng trả", "returns_value"),
            moneyColumn("Doanh thu thuần", "net_revenue"),
            moneyColumn("Giá trị đơn TB", "average_order_value"),
            moneyColumn("Khách có hồ sơ", "registered_revenue"),
            moneyColumn("Khách lẻ", "walk_in_revenue"),
            moneyColumn("Chênh lệch ca", "shift_variance"),
            moneyColumn("Còn phải hoàn", "outstanding_refunds"),
          ]}
        />
      )}
    </Card>
  );
}

/** Tiền thu, hoàn theo phương thức (DT-04) và đơn hủy theo lý do của một dòng. */
function Details({ summary }: { summary: Summary }) {
  return (
    <Space align="start" size="large" wrap>
      <Table<Schemas["MoneyByMethod"]>
        size="small"
        rowKey={(line) => `${line.type}-${line.method}`}
        dataSource={summary.payments}
        pagination={false}
        title={() => "Tiền thu và hoàn theo phương thức"}
        columns={[
          { title: "Loại", dataIndex: "type", render: (t: Schemas["TxnType"]) => TXN_TYPE_LABEL[t] },
          {
            title: "Phương thức",
            dataIndex: "method",
            render: (m: Schemas["TxnMethod"]) => TXN_METHOD_LABEL[m],
          },
          moneyColumn("Số tiền", "amount"),
        ]}
      />
      <Table<Schemas["CountByReason"]>
        size="small"
        rowKey="reason"
        dataSource={summary.cancellations}
        pagination={false}
        title={() => "Đơn hủy theo lý do"}
        columns={[
          { title: "Lý do", dataIndex: "reason" },
          { title: "Số đơn", dataIndex: "count", align: "right" },
        ]}
      />
    </Space>
  );
}
