// 5.5 Doanh số nhân viên, xếp hạng trong chi nhánh (DT-05).
import { useQuery } from "@tanstack/react-query";
import { Card, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { moneyColumn } from "../../ui";
import { ReportFilter, ReportHeader, type ReportParams } from "./ReportFilter";

export function StaffSalesReportPage() {
  const [params, setParams] = useState<ReportParams | null>(null);
  const report = useQuery({
    queryKey: ["reports", "staff-sales", params],
    queryFn: () => unwrap(client.GET("/reports/staff-sales", { params: { query: params! } })),
    enabled: params !== null,
  });
  const data = report.data;

  return (
    <Card title="Doanh số nhân viên">
      <ReportFilter onSubmit={setParams} />
      <ReportHeader report={data} error={report.error} />
      {data && (
        <Table<Schemas["StaffSalesLine"]>
          rowKey={(line) => `${line.branch_id}-${line.employee_id}`}
          dataSource={data.lines}
          scroll={{ x: true }}
          columns={[
            { title: "Chi nhánh", dataIndex: "branch_id" },
            { title: "Hạng", dataIndex: "rank", align: "right" },
            { title: "Mã NV", dataIndex: "employee_id" },
            { title: "Họ tên", dataIndex: "full_name" },
            { title: "Số đơn", dataIndex: "order_count", align: "right" },
            moneyColumn("Doanh thu gộp", "gross_revenue"),
            moneyColumn("Giá trị hàng trả", "returns_value"),
            moneyColumn("Doanh thu thuần", "net_revenue"),
            { title: "Đơn hủy", dataIndex: "cancelled_count", align: "right" },
            moneyColumn("Thuần kỳ trước", "previous_net_revenue"),
          ]}
        />
      )}
    </Card>
  );
}
