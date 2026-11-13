// 3.4 Hoàn tiền (TN): phiếu trả Đã duyệt chưa hoàn, khởi tạo hoàn, xác nhận đã chi/tra soát, thử lại khi thất bại.
// TH-04 do API kiểm tra; số tiền hoàn = giá trị phiếu và phương thức hoàn do API quyết định.
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Popconfirm, Table } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { PendingTransactions, TXN_KEYS } from "../payments/PendingTransactions";
import { useCurrentShift } from "../shifts/ShiftsPage";
import { useWrite } from "../../ui";
import { returnColumns } from "./ReturnsPage";

type ReturnSlip = Schemas["ReturnSlip"];

export function RefundsPage() {
  const slips = useQuery({
    queryKey: ["returns", "APPROVED", "NOT_REFUNDED"],
    queryFn: () =>
      unwrap(
        client.GET("/returns", {
          params: { query: { status: "APPROVED", refund_status: "NOT_REFUNDED" } },
        }),
      ),
  });
  const current = useCurrentShift();
  const refund = useWrite(
    (returnId: string) =>
      unwrap(client.POST("/returns/{return_id}/refunds", { params: { path: { return_id: returnId } } })),
    TXN_KEYS,
  );
  // Giao dịch hoàn thất bại trong ca: hiện để thu ngân biết phiếu cần thử lại
  const failed = new Map(
    (current.data?.failed ?? [])
      .filter((txn) => txn.type === "REFUND")
      .map((txn) => [txn.return_id, txn]),
  );

  return (
    <Card title="Hoàn tiền">
      <Table<ReturnSlip>
        rowKey="return_id"
        loading={slips.isPending}
        dataSource={slips.data}
        scroll={{ x: true }}
        columns={[
          ...returnColumns,
          {
            title: "Lần trước",
            render: (_, slip) => {
              const txn = failed.get(slip.return_id);
              if (!txn) return "";
              return txn.cash_refund_approved_by
                ? `Thất bại; ${txn.cash_refund_approved_by} đã duyệt hoàn tiền mặt`
                : "Thất bại";
            },
          },
          {
            title: "Thao tác",
            render: (_, slip) => (
              <Popconfirm
                title={`Khởi tạo hoàn tiền cho phiếu ${slip.return_id}?`}
                onConfirm={() => refund.mutate(slip.return_id)}
              >
                <Button size="small" type="primary">
                  {failed.has(slip.return_id) ? "Thử lại" : "Khởi tạo hoàn"}
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />

      <PendingTransactions type="REFUND" />
    </Card>
  );
}
