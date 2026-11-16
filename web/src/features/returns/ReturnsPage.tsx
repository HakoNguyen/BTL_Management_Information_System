// 3.4 Lập phiếu trả (NVBH, QL) và theo dõi trạng thái duyệt, hoàn tiền; QL duyệt hoặc từ chối, HQ duyệt thay
// mọi chi nhánh kèm lý do (TH-03, K-02, K-03, quyết định 15).
// TH-01, TH-02 do API kiểm tra; giá trị phiếu, trạng thái hoàn lấy từ API (dẫn xuất), giao diện không tự tính.
import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Checkbox, Descriptions, Form, Input, InputNumber, Select, Space, Table, Tag, message } from "antd";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime, money } from "../../format";
import { REFUND_STATUS_LABEL, RETURN_STATUS_LABEL, optionsOf } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";
import { decisionNoteRequired } from "./decisionNote";

type ReturnSlip = Schemas["ReturnSlip"];

/** Cột phiếu trả dùng chung cho trang này và lịch sử khách (2.4). */
export const returnColumns = [
  { title: "Mã phiếu", dataIndex: "return_id" },
  { title: "Đơn gốc", dataIndex: "order_id" },
  { title: "Lập lúc", dataIndex: "created_at", render: dateTime },
  { title: "Lý do", dataIndex: "reason" },
  {
    title: "Trạng thái",
    dataIndex: "status",
    render: (status: ReturnSlip["status"]) => <Tag>{RETURN_STATUS_LABEL[status]}</Tag>,
  },
  moneyColumn("Giá trị", "value"),
  {
    title: "Hoàn tiền",
    dataIndex: "refund_status",
    render: (status: ReturnSlip["refund_status"]) => (status ? REFUND_STATUS_LABEL[status] : ""),
  },
];

const itemColumns = [
  { title: "Sản phẩm", dataIndex: "product_id" },
  { title: "Tốt", dataIndex: "good_qty", align: "right" as const },
  { title: "Lỗi", dataIndex: "defective_qty", align: "right" as const },
  moneyColumn("Đơn giá chốt", "unit_price"),
  moneyColumn("Thành tiền", "amount"),
];

// Chỉ đơn Hoàn tất hoặc Đã trả một phần mới được lập phiếu trả (TH-01)
const RETURNABLE: Schemas["OrderStatus"][] = ["COMPLETED", "PARTIALLY_RETURNED"];

/** Chọn đơn gốc (tra theo SĐT khách 2.3 hoặc chọn mã đơn), rồi mỗi dòng là một sản phẩm tốt/lỗi (TH-02). */
function ReturnFields({
  orders,
  preselectedOrderId,
}: {
  orders: Schemas["Order"][];
  preselectedOrderId?: string;
}) {
  const form = Form.useFormInstance();
  const orderId = Form.useWatch("order_id");
  const items: { product_id: string; good_qty: number; defective_qty: number }[] =
    Form.useWatch("items") ?? [];
  const [matchedOrders, setMatchedOrders] = useState<Schemas["Order"][] | null>(null);

  const lookup = useMutation({
    mutationFn: async (phone: string) => {
      const customers = await unwrap(client.GET("/customers", { params: { query: { phone } } }));
      if (customers.length === 0) throw new Error("Không tìm thấy khách hàng");
      const customer = customers[0];
      const history = await unwrap(
        client.GET("/customers/{customer_id}/history", {
          params: { path: { customer_id: customer.customer_id }, query: { phone } },
        }),
      );
      return { customer, orders: (history.orders ?? []).filter((o) => RETURNABLE.includes(o.status)) };
    },
    onSuccess: ({ customer, orders: customerOrders }) => {
      if (customerOrders.length === 0) {
        message.warning(`Khách ${customer.full_name} không có đơn nào đủ điều kiện trả`);
        return;
      }
      setMatchedOrders(customerOrders);
      if (customerOrders.length === 1) {
        form.setFieldValue("order_id", customerOrders[0].order_id);
      }
      message.success(`Khách: ${customer.full_name} (${customerOrders.length} đơn có thể trả)`);
    },
    onError: (error) => message.error(error.message, 6),
  });

  const availableOrders = matchedOrders ?? orders;
  const order = availableOrders.find((candidate) => candidate.order_id === orderId);

  // Tính tổng tiền hoàn ước tính (preview, không lưu DB; API tính chính thức sau khi tạo phiếu)
  const previewTotal = items.reduce((sum, row) => {
    const orderItem = order?.items.find((it) => it.product_id === row.product_id);
    const qty = (row.good_qty ?? 0) + (row.defective_qty ?? 0);
    return sum + qty * (orderItem?.unit_price ?? 0);
  }, 0);

  useEffect(() => {
    if (preselectedOrderId) {
      form.setFieldValue("order_id", preselectedOrderId);
    }
  }, [preselectedOrderId, form]);

  return (
    <>
      {/* Bước 01: tra khách theo SĐT để lấy lịch sử đơn */}
      <Form.Item label="Tra đơn theo số điện thoại khách">
        <Input.Search
          enterButton="Tra"
          loading={lookup.isPending}
          placeholder="Nhập số điện thoại khách hàng"
          onSearch={(phone) => phone && lookup.mutate(phone.trim())}
        />
      </Form.Item>
      <Form.Item label="Đơn gốc" name="order_id" rules={[{ required: true }]}>
        <Select
          showSearch
          optionFilterProp="label"
          placeholder="Chọn đơn hàng"
          options={availableOrders.map((candidate) => ({
            value: candidate.order_id,
            label: `${candidate.order_id} · ${candidate.customer_id} · ${dateTime(candidate.completed_at)}`,
          }))}
        />
      </Form.Item>

      {/* Bước 03: hiển thị tóm tắt đơn gốc sau khi chọn */}
      {order && (
        <Descriptions
          size="small"
          bordered
          column={2}
          style={{ marginBottom: 16 }}
        >
          <Descriptions.Item label="Mã đơn">{order.order_id}</Descriptions.Item>
          <Descriptions.Item label="Chi nhánh">{order.branch_id}</Descriptions.Item>
          <Descriptions.Item label="Khách hàng">{order.customer_id}</Descriptions.Item>
          <Descriptions.Item label="Trạng thái">{order.status === "COMPLETED" ? "Hoàn tất" : "Đã trả một phần"}</Descriptions.Item>
          <Descriptions.Item label="Tổng tiền">{money(order.total)}</Descriptions.Item>
          <Descriptions.Item label="Hoàn tất lúc">{dateTime(order.completed_at)}</Descriptions.Item>
        </Descriptions>
      )}

      <Form.Item label="Lý do trả" name="reason" rules={[{ required: true, whitespace: true }]}>
        <Input.TextArea />
      </Form.Item>
      {/* TH-01: khách lẻ không có hóa đơn thì không nhận trả; API kiểm tra lại */}
      <Form.Item
        name="invoice_presented"
        valuePropName="checked"
        extra={order?.customer_id === "KHLE" ? "Bắt buộc với khách lẻ (KHLE)" : undefined}
      >
        <Checkbox>Khách xuất trình hóa đơn</Checkbox>
      </Form.Item>

      {/* Bước 04-05: chọn sản phẩm, số lượng tốt/lỗi */}
      <Form.List name="items">
        {(fields, { add, remove }) => (
          <>
            {fields.map((field) => {
              const selectedProductId = form.getFieldValue(["items", field.name, "product_id"]);
              const orderItem = order?.items.find((it) => it.product_id === selectedProductId);
              return (
                <Space key={field.key} align="start" wrap style={{ marginBottom: 4 }}>
                  <div>
                    <Form.Item name={[field.name, "product_id"]} rules={[{ required: true }]} style={{ marginBottom: 4 }}>
                      <Select
                        placeholder="Sản phẩm"
                        style={{ width: 200 }}
                        options={(order?.items ?? []).map((item) => ({
                          value: item.product_id,
                          label: item.product_id,
                        }))}
                      />
                    </Form.Item>
                    {/* Hiển thị thông tin đã mua và đơn giá chốt */}
                    {orderItem && (
                      <div style={{ fontSize: 12, color: "#595959", marginBottom: 4 }}>
                        Đã mua: {orderItem.quantity} · Đơn giá chốt: {money(orderItem.unit_price)}
                      </div>
                    )}
                  </div>
                  <Form.Item label="Tốt" name={[field.name, "good_qty"]} rules={[{ required: true }]}>
                    <InputNumber min={0} precision={0} />
                  </Form.Item>
                  <Form.Item label="Lỗi" name={[field.name, "defective_qty"]} rules={[{ required: true }]}>
                    <InputNumber min={0} precision={0} />
                  </Form.Item>
                  <Button onClick={() => remove(field.name)}>Bỏ</Button>
                </Space>
              );
            })}
            <Button onClick={() => add({ good_qty: 0, defective_qty: 0 })}>Thêm dòng</Button>
          </>
        )}
      </Form.List>

      {/* Preview tổng hoàn tiền (ước tính) */}
      {previewTotal > 0 && (
        <Form.Item label="Tổng giá trị hoàn (ước tính)">
          <strong>{money(previewTotal)}</strong>
        </Form.Item>
      )}

      {/* Ghi chú nghiệp vụ: khách vẫn giữ hàng đến khi phiếu được duyệt (Bước 05 → 07) */}
      <Alert
        type="info"
        showIcon
        message="Khách vẫn giữ hàng cho đến khi phiếu được Quản lý duyệt"
        style={{ marginTop: 8 }}
      />
    </>
  );
}

type Decision = "approve" | "reject";
const DECISION_TITLE: Record<Decision, string> = { approve: "Duyệt", reject: "Từ chối" };
// Duyệt đổi tồn (hàng tốt nhập lại), trạng thái đơn và báo cáo
const DECISION_KEYS = ["returns", "orders", "reports"];

export function ReturnsPage() {
  const { user } = useAuth();
  const role = user?.role;
  const canDecide = role === "MANAGER" || role === "HQ";
  const [status, setStatus] = useState<ReturnSlip["status"]>();
  // TH-05: phiếu Đã duyệt chưa hoàn xong = Đã duyệt + Chưa hoàn
  const [refundStatus, setRefundStatus] = useState<Schemas["RefundStatus"]>();
  const returns = useQuery({
    queryKey: ["returns", status, refundStatus],
    queryFn: () =>
      unwrap(client.GET("/returns", { params: { query: { status, refund_status: refundStatus } } })),
  });
  const [deciding, setDeciding] = useState<{ slip: ReturnSlip; decision: Decision } | null>(null);
  const decide = useWrite(
    (body: Schemas["ReturnDecision"]) =>
      unwrap(
        client.POST(`/returns/{return_id}/${deciding!.decision}`, {
          params: { path: { return_id: deciding!.slip.return_id } },
          body,
        }),
      ),
    DECISION_KEYS,
  );
  const [creating, setCreating] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const preselectedOrderId = searchParams.get("order_id") ?? undefined;

  useEffect(() => {
    if (preselectedOrderId) {
      setCreating(true);
    }
  }, [preselectedOrderId]);

  const orders = useQuery({
    queryKey: ["orders", undefined],
    queryFn: () => unwrap(client.GET("/orders", { params: { query: {} } })),
    enabled: creating,
  });
  const create = useWrite(
    (body: Schemas["ReturnCreate"]) => unwrap(client.POST("/returns", { body })),
    ["returns"],
  );

  return (
    <Card
      title="Phiếu trả"
      extra={
        <Space wrap>
          <Select
            allowClear
            placeholder="Mọi trạng thái"
            style={{ minWidth: 160 }}
            options={optionsOf(RETURN_STATUS_LABEL)}
            value={status}
            onChange={setStatus}
          />
          <Select
            allowClear
            placeholder="Mọi trạng thái hoàn"
            style={{ minWidth: 180 }}
            options={optionsOf(REFUND_STATUS_LABEL)}
            value={refundStatus}
            onChange={setRefundStatus}
          />
          {role !== "HQ" && <Button onClick={() => setCreating(true)}>Lập phiếu trả</Button>}
        </Space>
      }
    >
      <Table<ReturnSlip>
        rowKey="return_id"
        loading={returns.isPending}
        dataSource={returns.data}
        scroll={{ x: true }}
        expandable={{
          expandedRowRender: (slip) => (
            <>
              <Table<Schemas["ReturnItem"]>
                rowKey="product_id"
                size="small"
                pagination={false}
                dataSource={slip.items}
                columns={itemColumns}
              />
              {slip.decided_at && (
                <p>
                  Quyết định lúc {dateTime(slip.decided_at)} bởi {slip.decided_by ?? "Hệ thống"}
                  {slip.decision_note ? `: ${slip.decision_note}` : ""}
                </p>
              )}
            </>
          ),
        }}
        columns={[
          { title: "Chi nhánh", dataIndex: "branch_id" },
          ...returnColumns,
          { title: "Người lập", dataIndex: "created_by" },
          ...(canDecide
            ? [
                {
                  title: "Thao tác",
                  render: (_: unknown, slip: ReturnSlip) =>
                    // K-02: không quyết định phiếu do mình lập (ẩn nút cho tiện; API kiểm tra lại)
                    slip.status === "PENDING" &&
                    slip.created_by !== user?.employee_id && (
                      <Space wrap>
                        <Button
                          size="small"
                          type="primary"
                          onClick={() => setDeciding({ slip, decision: "approve" })}
                        >
                          Duyệt
                        </Button>
                        <Button
                          size="small"
                          danger
                          onClick={() => setDeciding({ slip, decision: "reject" })}
                        >
                          Từ chối
                        </Button>
                      </Space>
                    ),
                },
              ]
            : []),
        ]}
      />

      {deciding && role && (
        <FormModal<Schemas["ReturnDecision"]>
          title={`${DECISION_TITLE[deciding.decision]} phiếu trả ${deciding.slip.return_id}`}
          onClose={() => setDeciding(null)}
          onSubmit={decide.mutateAsync}
        >
          <p>
            Đơn {deciding.slip.order_id}, giá trị {money(deciding.slip.value)}, lý do trả:{" "}
            {deciding.slip.reason}
          </p>
          <Form.Item
            label={role === "HQ" ? "Lý do duyệt thay" : "Ghi chú, lý do"}
            name="decision_note"
            rules={[
              { required: decisionNoteRequired(role, deciding.decision), whitespace: true },
            ]}
          >
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}

      {creating && (
        <FormModal<Schemas["ReturnCreate"]>
          title="Lập phiếu trả"
          initialValues={{ items: [{ good_qty: 0, defective_qty: 0 } as Schemas["ReturnItemInput"]] }}
          onClose={() => {
            setCreating(false);
            setSearchParams({});
          }}
          onSubmit={create.mutateAsync}
        >
          <ReturnFields
            orders={(orders.data ?? []).filter((order) => RETURNABLE.includes(order.status))}
            preselectedOrderId={preselectedOrderId}
          />
        </FormModal>
      )}
    </Card>
  );
}
