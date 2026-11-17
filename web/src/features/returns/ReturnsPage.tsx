// 3.4 Lập phiếu trả (NVBH, QL) và theo dõi trạng thái duyệt, hoàn tiền; QL duyệt hoặc từ chối, HQ duyệt thay
// mọi chi nhánh kèm lý do (TH-03, K-02, K-03, quyết định 15).
// TH-01, TH-02 do API kiểm tra; giá trị phiếu, trạng thái hoàn lấy từ API (dẫn xuất), giao diện không tự tính.
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Checkbox,
  Col,
  Form,
  Row as GridRow,
  Input,
  InputNumber,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime, money } from "../../format";
import { REFUND_STATUS_LABEL, RETURN_STATUS_LABEL, optionsOf } from "../../labels";
import { inDateRange, type DateRange } from "../../dateRange";
import {
  AddButton,
  BranchFilter,
  DateRangeFilter,
  FormModal,
  RemoveButton,
  STATUS_COLOR,
  moneyColumn,
  useWrite,
} from "../../ui";
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
    render: (status: ReturnSlip["status"]) => (
      <Tag color={STATUS_COLOR[status]}>{RETURN_STATUS_LABEL[status]}</Tag>
    ),
  },
  moneyColumn("Giá trị", "value"),
  {
    title: "Hoàn tiền",
    dataIndex: "refund_status",
    render: (status: ReturnSlip["refund_status"]) =>
      status && <Tag color={STATUS_COLOR[status]}>{REFUND_STATUS_LABEL[status]}</Tag>,
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

type FindBy = "ORDER" | "PHONE";

/** Đơn gốc tìm theo mã đơn (khách xuất trình hóa đơn/mã đơn), hoặc theo số điện thoại khách có hồ sơ
 * mất hóa đơn qua 2.4 (TH-01, KH-04: API xác minh số). Rồi mỗi dòng là một sản phẩm của đơn đó với số
 * lượng tốt và lỗi (TH-02). `orders`: đơn trả được của chi nhánh. */
function ReturnFields({ orders }: { orders: Schemas["Order"][] }) {
  const form = Form.useFormInstance();
  const { user } = useAuth();
  const [by, setBy] = useState<FindBy>("ORDER");
  const [found, setFound] = useState<Schemas["Order"][] | null>(null);
  const lookup = useMutation({
    mutationFn: async (phone: string) => {
      const [customer] = await unwrap(client.GET("/customers", { params: { query: { phone } } }));
      if (!customer) throw new Error("Không tìm thấy khách có số điện thoại này");
      const history = await unwrap(
        client.GET("/customers/{customer_id}/history", {
          params: { path: { customer_id: customer.customer_id }, query: { phone } },
        }),
      );
      return { customer, orders: history.orders };
    },
    onSuccess: ({ customer, orders: bought }) => {
      // Chỉ đơn trả được tại chi nhánh này (TH-01); API kiểm tra lại khi lưu
      const returnable = new Set(orders.map((o) => o.order_id));
      const here = bought.filter((o) => returnable.has(o.order_id));
      setFound(here);
      form.setFieldValue("order_id", here.length === 1 ? here[0].order_id : undefined);
      const text = `${customer.full_name}: ${bought.length} đơn đã mua, ${here.length} đơn trả được tại chi nhánh này`;
      if (here.length) message.success(text);
      else message.warning(text);
    },
    onError: (error) => message.error(error.message, 6),
  });
  const products = useQuery({ queryKey: ["products"], queryFn: () => unwrap(client.GET("/products")) });
  const names = new Map((products.data ?? []).map((p) => [p.product_id, p.name]));
  const candidates = by === "ORDER" ? orders : (found ?? []);
  const orderId = Form.useWatch("order_id");
  const order = candidates.find((candidate) => candidate.order_id === orderId);
  const switchTo = (next: FindBy) => {
    setBy(next);
    setFound(null);
    form.setFieldValue("order_id", undefined);
  };

  return (
    <>
      {/* 2.4 chỉ dành cho NVBH (ma trận 2.2): QL tìm theo mã đơn */}
      {user?.role === "SALES" && (
        <Form.Item label="Tìm đơn gốc">
          <Segmented<FindBy>
            value={by}
            onChange={switchTo}
            options={[
              { value: "ORDER", label: "Theo mã đơn" },
              { value: "PHONE", label: "Theo số điện thoại khách" },
            ]}
          />
        </Form.Item>
      )}
      {by === "PHONE" && (
        <Form.Item label="Số điện thoại khách" extra="Khách có hồ sơ mất hóa đơn; số phải khớp hồ sơ">
          <Input.Search
            enterButton="Tìm đơn"
            loading={lookup.isPending}
            onSearch={(phone) => phone.trim() && lookup.mutate(phone.trim())}
          />
        </Form.Item>
      )}
      <Form.Item label="Đơn gốc" name="order_id" rules={[{ required: true, message: "Chọn đơn gốc" }]}>
        <Select
          showSearch
          optionFilterProp="label"
          placeholder={by === "ORDER" ? "Gõ mã đơn, ví dụ DH000012" : "Tìm theo số điện thoại trước"}
          notFoundContent={by === "PHONE" && found ? "Không có đơn trả được" : undefined}
          options={candidates.map((candidate) => ({
            value: candidate.order_id,
            label: `${candidate.order_id} · ${candidate.customer_id} · ${dateTime(candidate.completed_at)} · ${money(candidate.total)}`,
          }))}
        />
      </Form.Item>
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
      <Form.List name="items">
        {(fields, { add, remove }) => (
          <>
            <GridRow gutter={8} style={{ fontWeight: 500, marginBottom: 6 }}>
              <Col flex="auto">Sản phẩm trả</Col>
              <Col flex="96px">Còn tốt</Col>
              <Col flex="96px">Bị lỗi</Col>
              <Col flex="32px" />
            </GridRow>
            {fields.map((field) => (
              <GridRow key={field.key} gutter={8} wrap={false}>
                <Col flex="auto" style={{ minWidth: 0 }}>
                  <Form.Item
                    name={[field.name, "product_id"]}
                    rules={[{ required: true, message: "Chọn sản phẩm" }]}
                  >
                    <Select
                      placeholder={order ? "Chọn sản phẩm trong đơn" : "Chọn đơn gốc trước"}
                      options={(order?.items ?? []).map((item) => ({
                        value: item.product_id,
                        label: `${item.product_id} – ${names.get(item.product_id) ?? ""} (mua ${item.quantity})`,
                      }))}
                    />
                  </Form.Item>
                </Col>
                <Col flex="96px">
                  <Form.Item name={[field.name, "good_qty"]} rules={[{ required: true, message: " " }]}>
                    <InputNumber min={0} precision={0} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col flex="96px">
                  <Form.Item name={[field.name, "defective_qty"]} rules={[{ required: true, message: " " }]}>
                    <InputNumber min={0} precision={0} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col flex="32px">
                  <RemoveButton onClick={() => remove(field.name)} />
                </Col>
              </GridRow>
            ))}
            <AddButton onClick={() => add({ good_qty: 0, defective_qty: 0 })}>+ Thêm sản phẩm</AddButton>
            <Typography.Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              Còn tốt: hàng nguyên vẹn, nhập lại kho khi phiếu được duyệt. Bị lỗi: hàng hỏng, không vào
              kho, QL xử lý riêng. Cả hai đều được hoàn tiền theo đơn giá đã chốt.
            </Typography.Paragraph>
          </>
        )}
      </Form.List>
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
  const [range, setRange] = useState<DateRange>(null);
  // HQ xem mọi chi nhánh: lọc theo chi nhánh ngay trên danh sách đã tải
  const [branchId, setBranchId] = useState<string>();
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
          {role === "HQ" && <BranchFilter value={branchId} onChange={setBranchId} />}
          <DateRangeFilter onChange={setRange} />
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
        dataSource={returns.data?.filter(
          (slip) => (!branchId || slip.branch_id === branchId) && inDateRange(slip.created_at, range),
        )}
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
          onClose={() => setCreating(false)}
          onSubmit={create.mutateAsync}
        >
          <ReturnFields
            orders={(orders.data ?? []).filter((order) => RETURNABLE.includes(order.status))}
          />
        </FormModal>
      )}
    </Card>
  );
}
