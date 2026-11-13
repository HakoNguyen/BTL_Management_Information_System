// 3.1 Lập, sửa, chốt, mở lại đơn; 3.4 hủy đơn chưa thanh toán (NVBH: đơn mình lập).
// BH-01..BH-04 do API kiểm tra; tổng tiền, đơn giá chốt lấy từ API, giao diện không tự tính.
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime, money } from "../../format";
import { ORDER_STATUS_LABEL, optionsOf } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";
import { CustomerField, ItemsField } from "./ItemsField";
import { stockProblems } from "./stockProblems";

type Order = Schemas["Order"];
type Dialog = "create" | "items" | "cancel";

const orderPath = (id: string) => ({ params: { path: { order_id: id } } });
const KEYS = ["orders"];
const WALK_IN = "KHLE";

export function OrdersPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<Order["status"]>();
  const orders = useQuery({
    queryKey: ["orders", status],
    queryFn: () => unwrap(client.GET("/orders", { params: { query: { status } } })),
  });
  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => unwrap(client.GET("/products")),
  });
  const names = new Map((products.data ?? []).map((product) => [product.product_id, product.name]));
  const [dialog, setDialog] = useState<{ kind: Dialog; order?: Order } | null>(null);
  const [problem, setProblem] = useState<{ orderId: string; lines: string[] } | null>(null);
  const close = () => setDialog(null);
  const id = dialog?.order?.order_id ?? "";

  const create = useWrite(
    (body: Schemas["OrderCreate"]) => unwrap(client.POST("/orders", { body })),
    KEYS,
  );
  const changeItems = useWrite(
    (body: Schemas["OrderItemsChange"]) =>
      unwrap(client.PUT("/orders/{order_id}/items", { ...orderPath(id), body })),
    KEYS,
  );
  const confirm = useWrite(
    (orderId: string) => unwrap(client.POST("/orders/{order_id}/confirm", orderPath(orderId))),
    KEYS,
  );
  const reopen = useWrite(
    (orderId: string) => unwrap(client.POST("/orders/{order_id}/reopen", orderPath(orderId))),
    KEYS,
  );
  const cancel = useWrite(
    (body: Schemas["OrderCancel"]) =>
      unwrap(client.POST("/orders/{order_id}/cancel", { ...orderPath(id), body })),
    KEYS,
  );

  const runConfirm = (orderId: string) => {
    setProblem(null);
    confirm
      .mutateAsync(orderId)
      .catch((error) => setProblem({ orderId, lines: stockProblems(error, names) }));
  };
  const productLabel = (productId: string) =>
    names.has(productId) ? `${productId} – ${names.get(productId)}` : productId;
  // Ẩn nút với đơn người khác lập chỉ để tiện dùng; quyền thật do API kiểm tra (BH-03, BH-04)
  const mine = (order: Order) => user?.role !== "SALES" || order.created_by === user.employee_id;

  return (
    <Card
      title="Đơn hàng"
      extra={
        <Space wrap>
          <Select
            allowClear
            placeholder="Mọi trạng thái"
            style={{ minWidth: 180 }}
            options={optionsOf(ORDER_STATUS_LABEL)}
            value={status}
            onChange={setStatus}
          />
          <Button onClick={() => setDialog({ kind: "create" })}>Lập đơn</Button>
        </Space>
      }
    >
      {problem && problem.lines.length > 0 && (
        <Alert
          type="error"
          showIcon
          closable
          onClose={() => setProblem(null)}
          style={{ marginBottom: 16 }}
          message={`Không chốt được đơn ${problem.orderId}, đơn vẫn Đang lập`}
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
            <>
              <Table<Schemas["OrderItem"]>
                rowKey="product_id"
                size="small"
                pagination={false}
                dataSource={order.items}
                columns={[
                  { title: "Sản phẩm", dataIndex: "product_id", render: productLabel },
                  { title: "Số lượng", dataIndex: "quantity", align: "right" },
                  {
                    ...moneyColumn("Đơn giá chốt", "unit_price"),
                    render: (price: number | null) => (price === null ? "Chưa chốt" : money(price)),
                  },
                ]}
              />
              {order.status === "CANCELLED" && (
                <p>
                  Hủy lúc {dateTime(order.cancelled_at)} bởi {order.cancelled_by ?? "Hệ thống"}: {" "}
                  {order.cancel_reason}
                </p>
              )}
            </>
          ),
        }}
        columns={[
          { title: "Mã đơn", dataIndex: "order_id" },
          { title: "Khách", dataIndex: "customer_id" },
          { title: "Người lập", dataIndex: "created_by" },
          { title: "Lập lúc", dataIndex: "created_at", render: dateTime },
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (value: Order["status"]) => <Tag>{ORDER_STATUS_LABEL[value]}</Tag>,
          },
          {
            ...moneyColumn("Tổng tiền", "total"),
            render: (total: number | null) => (total === null ? "Chưa chốt" : money(total)),
          },
          {
            title: "Thao tác",
            render: (_, order) => {
              if (!mine(order)) return null;
              const open = (kind: Dialog) => () => setDialog({ kind, order });
              const cancelButton = (
                <Button size="small" danger onClick={open("cancel")}>
                  Hủy đơn
                </Button>
              );
              if (order.status === "DRAFT")
                return (
                  <Space wrap>
                    <Button size="small" onClick={open("items")}>
                      Sửa dòng
                    </Button>
                    <Button
                      size="small"
                      type="primary"
                      loading={confirm.isPending && confirm.variables === order.order_id}
                      onClick={() => runConfirm(order.order_id)}
                    >
                      Chốt
                    </Button>
                    {cancelButton}
                  </Space>
                );
              if (order.status === "AWAITING_PAYMENT")
                return (
                  <Space wrap>
                    <Popconfirm
                      title={`Mở lại đơn ${order.order_id} về Đang lập?`}
                      onConfirm={() => reopen.mutate(order.order_id)}
                    >
                      <Button size="small">Mở lại</Button>
                    </Popconfirm>
                    {cancelButton}
                  </Space>
                );
              return null;
            },
          },
        ]}
      />

      {dialog?.kind === "create" && (
        <FormModal<Schemas["OrderCreate"]>
          title="Lập đơn"
          initialValues={{ customer_id: WALK_IN, items: [{} as Schemas["OrderItemInput"]] }}
          onClose={close}
          onSubmit={create.mutateAsync}
        >
          <CustomerField />
          <ItemsField />
        </FormModal>
      )}

      {dialog?.kind === "items" && (
        <FormModal<Schemas["OrderItemsChange"]>
          title={`Sửa dòng đơn ${id}`}
          initialValues={{
            items: dialog.order!.items.map(({ product_id, quantity }) => ({ product_id, quantity })),
          }}
          onClose={close}
          onSubmit={changeItems.mutateAsync}
        >
          <ItemsField />
        </FormModal>
      )}

      {dialog?.kind === "cancel" && (
        <FormModal<Schemas["OrderCancel"]> title={`Hủy đơn ${id}`} onClose={close} onSubmit={cancel.mutateAsync}>
          <Form.Item label="Lý do hủy" name="reason" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}
    </Card>
  );
}
