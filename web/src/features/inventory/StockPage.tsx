// Tồn kho chi nhánh: tồn, tồn khả dụng, ngưỡng và mức tồn so ngưỡng (TK-01, TK-05).
// NV kho xem tồn qua 5.3 (ma trận 2.2): GET /stock không có mức tồn, nên lấy phần tồn tại thời điểm lập
// của GET /reports/stock; giao diện không tự tính khả dụng hay so ngưỡng.
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Table } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime } from "../../format";
import { today } from "../reports/ReportFilter";
import { stockLineColumns } from "../reports/StockReportPage";

export function StockPage() {
  const report = useQuery({
    queryKey: ["reports", "stock", "now"],
    queryFn: () =>
      unwrap(client.GET("/reports/stock", { params: { query: { from: today(), to: today() } } })),
  });

  return (
    <Card
      title="Tồn kho chi nhánh"
      extra={report.data && `Lập lúc ${dateTime(report.data.generated_at)}`}
    >
      {report.error && <Alert type="error" showIcon message={report.error.message} />}
      <Table<Schemas["StockReportLine"]>
        rowKey="product_id"
        loading={report.isPending}
        dataSource={report.data?.lines}
        scroll={{ x: true }}
        columns={stockLineColumns}
      />
    </Card>
  );
}
