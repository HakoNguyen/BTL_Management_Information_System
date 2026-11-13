// 3.2 Thu tiền: đơn Chờ thanh toán của chi nhánh, chọn phương thức, rồi xác nhận/tra soát kết quả.
// TT-01..TT-03 do API kiểm tra; số tiền giao dịch = tổng đơn do API lấy, giao diện không tự tính.
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Select, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime } from "../../format";
import { TXN_METHOD_LABEL, optionsOf } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";
import { stockProblems } from "../orders/stockProblems";
import { useCurrentShift } from "../shifts/ShiftsPage";
import { PendingTransactions, TXN_KEYS } from "./PendingTransactions";

type Order = Schemas["Order"];

export function PaymentsPage() {
  const orders = useQuery({
    queryKey: ["orders", "AWAITING_PAYMENT"],
    queryFn: () =>
      unwrap(client.GET("/orders", { params: { query: { status: "AWAITING_PAYMENT" } } })),
  });
  const current = useCurrentShift();
  const [paying, setPaying] = useState<Order | null>(null);
  const [problem, setProblem] = useState<{ orderId: string; lines: string[] } | null>(null);
  const pay = useWrite(
    (body: Schemas["PaymentCreate"]) =>
      unwrap(
        client.POST("/orders/{order_id}/payments", {
          params: { path: { order_id: paying!.order_id } },
          body,
        }),
      ),
    TXN_KEYS,
  );
  // Đơn đang có giao dịch Chờ kết quả thì không khởi tạo thu lần nữa (TT-02)
  const pendingOrders = new Set((current.data?.pending ?? []).map((txn) => txn.order_id));

  const submit = (body: Schemas["PaymentCreate"]) => {
    const orderId = paying!.order_id;
    setProblem(null);
    return pay.mutateAsync(body).catch((error) => {
      setProblem({ orderId, lines: stockProblems(error, new Map()) });
      throw error;
    });
  };

  return (
    <Card title="Thu tiền">
      {problem && problem.lines.length > 0 && (
        <Alert
          type="error"
          showIcon
          closable
          onClose={() => setProblem(null)}
          style={{ marginBottom: 16 }}
          message={`Không giữ được hàng cho đơn ${problem.orderId}, chưa tạo giao dịch`}
          description={
            <ul style={{ margin: 0 }}>
              {problem.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          }
        />
      )}
      <Table<Order>
        rowKey="order_id"
        loading={orders.isPending}
        dataSource={orders.data}
        scroll={{ x: true }}
        expandable={{
          expandedRowRender: (order) => (
            <Table<Schemas["OrderItem"]>
              rowKey="product_id"
              size="small"
              pagination={false}
              dataSource={order.items}
              columns={[
                { title: "Sản phẩm", dataIndex: "product_id" },
                { title: "Số lượng", dataIndex: "quantity", align: "right" },
                moneyColumn("Đơn giá chốt", "unit_price"),
              ]}
            />
          ),
        }}
        columns={[
          { title: "Mã đơn", dataIndex: "order_id" },
          { title: "Khách", dataIndex: "customer_id" },
          { title: "Người lập", dataIndex: "created_by" },
          { title: "Chốt lúc", dataIndex: "confirmed_at", render: dateTime },
          moneyColumn("Tổng tiền", "total"),
          {
            title: "Thao tác",
            render: (_, order) =>
              pendingOrders.has(order.order_id) ? (
                "Đang chờ kết quả"
              ) : (
                <Button size="small" type="primary" onClick={() => setPaying(order)}>
                  Thu tiền
                </Button>
              ),
          },
        ]}
      />

      <PendingTransactions type="COLLECT" />

      {paying && (
        <FormModal<Schemas["PaymentCreate"]>
          title={`Thu tiền đơn ${paying.order_id}`}
          initialValues={{ method: "CASH" }}
          onClose={() => setPaying(null)}
          onSubmit={submit}
        >
          <Form.Item label="Phương thức" name="method" rules={[{ required: true }]}>
            <Select options={optionsOf(TXN_METHOD_LABEL)} />
          </Form.Item>
        </FormModal>
      )}
    </Card>
  );
}
