// 5.4 Cảnh báo tồn: sản phẩm Đang bán có tồn dưới ngưỡng, và riêng danh sách Chưa thiết lập ngưỡng (TK-05).
// Tính lúc mở trang, luôn là chi nhánh của người xem; số liệu lấy nguyên từ API.
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Table, Typography } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime } from "../../format";

type Line = Schemas["LowStockLine"];

const columns = [
  { title: "Mã", dataIndex: "product_id" },
  { title: "Tên", dataIndex: "name" },
  { title: "Tồn", dataIndex: "quantity", align: "right" as const },
];

export function LowStockReportPage() {
  const report = useQuery({
    queryKey: ["reports", "low-stock"],
    queryFn: () => unwrap(client.GET("/reports/low-stock")),
  });
  const data = report.data;

  return (
    <Card
      title="Cảnh báo tồn dưới ngưỡng"
      extra={
        <Button loading={report.isFetching} onClick={() => report.refetch()}>
          Tải lại
        </Button>
      }
    >
      {report.error && <Alert type="error" showIcon message={report.error.message} />}
      {data && (
        <>
          <Typography.Paragraph type="secondary">
            Chi nhánh {data.branch_id}, lập lúc {dateTime(data.generated_at)}
          </Typography.Paragraph>
          <Typography.Title level={5}>Dưới mức tồn tối thiểu</Typography.Title>
          <Table<Line>
            rowKey="product_id"
            pagination={false}
            dataSource={data.below_min}
            columns={[
              ...columns,
              { title: "Ngưỡng tối thiểu", dataIndex: "min_level", align: "right" },
            ]}
          />
          <Typography.Title level={5} style={{ marginTop: 24 }}>
            Chưa thiết lập ngưỡng
          </Typography.Title>
          <Table<Line>
            rowKey="product_id"
            pagination={false}
            dataSource={data.not_set}
            columns={columns}
          />
        </>
      )}
    </Card>
  );
}
