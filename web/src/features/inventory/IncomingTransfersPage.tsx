// 4.6 Hàng điều chuyển đang chuyển đến chi nhánh mình (TK-07). NV kho nhận đúng số đã xuất, ghi nhận ngay;
// sai lệch khi kiểm đếm xử lý bằng phiếu điều chỉnh (TK-04). QL chỉ xem.
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Popconfirm, Table } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime } from "../../format";
import { useWrite } from "../../ui";

type Slip = Schemas["StockSlip"];

export function IncomingTransfersPage() {
  const isWarehouse = useAuth().user?.role === "WAREHOUSE";
  const incoming = useQuery({
    queryKey: ["stock-slips", "incoming-transfers"],
    queryFn: () => unwrap(client.GET("/stock-slips/incoming-transfers")),
  });
  const receive = useWrite(
    (slipId: string) =>
      unwrap(client.POST("/stock-slips/{slip_id}/receive", { params: { path: { slip_id: slipId } } })),
    ["stock-slips", "stock", "reports"],
  );

  return (
    <Card title="Hàng điều chuyển đến">
      <Table<Slip>
        rowKey="slip_id"
        loading={incoming.isPending}
        dataSource={incoming.data}
        scroll={{ x: true }}
        columns={[
          { title: "Phiếu xuất", dataIndex: "slip_id" },
          { title: "Từ chi nhánh", dataIndex: "branch_id" },
          {
            title: "Hàng",
            render: (_, slip) =>
              slip.items.map((item) => `${item.product_id} × ${item.quantity}`).join(", "),
          },
          { title: "Lý do", dataIndex: "reason" },
          { title: "Xuất lúc", dataIndex: "finalized_at", render: dateTime },
          ...(isWarehouse
            ? [
                {
                  title: "Thao tác",
                  render: (_: unknown, slip: Slip) => (
                    <Popconfirm
                      title={`Ghi nhận đã nhận đủ hàng của phiếu ${slip.slip_id}? Tồn tăng ngay.`}
                      onConfirm={() => receive.mutate(slip.slip_id)}
                    >
                      <Button size="small" type="primary">
                        Nhận hàng
                      </Button>
                    </Popconfirm>
                  ),
                },
              ]
            : []),
        ]}
      />
    </Card>
  );
}
