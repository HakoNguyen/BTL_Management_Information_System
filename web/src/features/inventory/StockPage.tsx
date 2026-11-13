// Tồn kho chi nhánh: tồn, tồn khả dụng, ngưỡng và mức tồn so ngưỡng (TK-01, TK-05); QL đặt ngưỡng (4.5).
// NV kho, QL xem tồn qua 5.3 (ma trận 2.2): GET /stock không có mức tồn, nên lấy phần tồn tại thời điểm lập
// của GET /reports/stock; giao diện không tự tính khả dụng hay so ngưỡng.
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, InputNumber, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime } from "../../format";
import { FormModal, useWrite } from "../../ui";
import { today } from "../reports/ReportFilter";
import { stockLineColumns } from "../reports/StockReportPage";

type Line = Schemas["StockReportLine"];

export function StockPage() {
  const isManager = useAuth().user?.role === "MANAGER";
  const report = useQuery({
    queryKey: ["reports", "stock", "now"],
    queryFn: () =>
      unwrap(client.GET("/reports/stock", { params: { query: { from: today(), to: today() } } })),
  });
  const [editing, setEditing] = useState<Line | null>(null);
  const setMinLevel = useWrite(
    // Ô để trống = null = Chưa thiết lập (TK-05), khác 0
    ({ min_level }: Schemas["MinLevelChange"]) =>
      unwrap(
        client.PUT("/stock/{product_id}/min-level", {
          params: { path: { product_id: editing!.product_id } },
          body: { min_level: min_level ?? null },
        }),
      ),
    ["reports", "stock"],
  );

  return (
    <Card
      title="Tồn kho chi nhánh"
      extra={report.data && `Lập lúc ${dateTime(report.data.generated_at)}`}
    >
      {report.error && <Alert type="error" showIcon message={report.error.message} />}
      <Table<Line>
        rowKey="product_id"
        loading={report.isPending}
        dataSource={report.data?.lines}
        scroll={{ x: true }}
        columns={[
          ...stockLineColumns,
          ...(isManager
            ? [
                {
                  title: "Thao tác",
                  render: (_: unknown, line: Line) => (
                    <Button size="small" onClick={() => setEditing(line)}>
                      Đặt ngưỡng
                    </Button>
                  ),
                },
              ]
            : []),
        ]}
      />

      {editing && (
        <FormModal<Schemas["MinLevelChange"]>
          title={`Mức tồn tối thiểu: ${editing.product_id} – ${editing.name}`}
          initialValues={{ min_level: editing.min_level }}
          onClose={() => setEditing(null)}
          onSubmit={setMinLevel.mutateAsync}
        >
          <Form.Item
            label="Mức tồn tối thiểu"
            name="min_level"
            extra="Để trống = Chưa thiết lập (khác 0)"
          >
            <InputNumber min={0} precision={0} style={{ width: "100%" }} />
          </Form.Item>
        </FormModal>
      )}
    </Card>
  );
}
