// 4.2 Ghi nhập theo phiếu giao (TK-02, ghi nhận ngay); 4.2/4.3 phiếu điều chỉnh, xuất hủy, xuất trả kho tổng
// lập ở Chờ xử lý, chờ QL duyệt hoặc từ chối kèm lý do (TK-03, TK-04, K-02, K-03). Trụ sở không duyệt thay
// phiếu kho. Lỗi do API kiểm tra; giao diện không tự tính tồn khả dụng.
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Popconfirm, Select, Space, Table, Tag } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime } from "../../format";
import { SLIP_STATUS_LABEL, SLIP_TYPE_LABEL, optionsOf } from "../../labels";
import { FormModal, useWrite } from "../../ui";
import { ItemsField } from "../orders/ItemsField";
import { stockProblems } from "../orders/stockProblems";

type Slip = Schemas["StockSlip"];
type InboundCreate = Schemas["InboundSlipCreate"];
type SlipCreate = Schemas["StockSlipCreate"];

const typeOptions = <T extends Slip["type"]>(types: T[]) =>
  types.map((value) => ({ value, label: SLIP_TYPE_LABEL[value] }));
const INBOUND_TYPES = typeOptions<InboundCreate["type"]>(["IN_WAREHOUSE", "IN_SUPPLIER"]);
const SLIP_TYPES = typeOptions<SlipCreate["type"]>([
  "ADJUST_UP",
  "ADJUST_DOWN",
  "OUT_DISPOSAL",
  "OUT_TO_WAREHOUSE",
]);
const ADJUST_TYPES: Slip["type"][] = ["ADJUST_UP", "ADJUST_DOWN"];
// Chỉ phiếu điều chỉnh, xuất khác qua QL duyệt; phiếu nhập, xuất bán không (TK-03)
const APPROVABLE = SLIP_TYPES.map((option) => option.value as Slip["type"]);
const slipPath = (id: string) => ({ params: { path: { slip_id: id } } });
// Phiếu xuất giữ hàng nên làm đổi tồn khả dụng; phiếu nhập đổi tồn ngay
const KEYS = ["stock-slips", "stock", "reports"];
const STATUS_COLOR: Record<Slip["status"], string> = {
  PENDING: "gold",
  POSTED: "green",
  CANCELLED: "default",
};

export function StockSlipsPage() {
  const isManager = useAuth().user?.role === "MANAGER";
  // QL mở trang để duyệt: mặc định lọc phiếu Chờ xử lý
  const [status, setStatus] = useState<Slip["status"] | undefined>(isManager ? "PENDING" : undefined);
  const slips = useQuery({
    queryKey: ["stock-slips", status],
    queryFn: () => unwrap(client.GET("/stock-slips", { params: { query: { status } } })),
  });
  // Danh sách đầy đủ để chọn phiếu bị sai khi lập phiếu điều chỉnh
  const allSlips = useQuery({
    queryKey: ["stock-slips", undefined],
    queryFn: () => unwrap(client.GET("/stock-slips")),
  });
  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => unwrap(client.GET("/products")),
  });
  const names = new Map((products.data ?? []).map((product) => [product.product_id, product.name]));
  const productLabel = (id: string) => (names.has(id) ? `${id} – ${names.get(id)}` : id);

  const [dialog, setDialog] = useState<"inbound" | "slip" | null>(null);
  const [rejecting, setRejecting] = useState<Slip | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const close = () => {
    setDialog(null);
    setProblems([]);
  };

  const inbound = useWrite(
    (body: InboundCreate) => unwrap(client.POST("/stock-slips/inbound", { body })),
    KEYS,
  );
  const create = useWrite(
    (body: SlipCreate) => unwrap(client.POST("/stock-slips", { body })),
    KEYS,
  );
  const approve = useWrite(
    (slipId: string) => unwrap(client.POST("/stock-slips/{slip_id}/approve", slipPath(slipId))),
    KEYS,
  );
  const reject = useWrite(
    (body: Schemas["StockSlipReject"]) =>
      unwrap(client.POST("/stock-slips/{slip_id}/reject", { ...slipPath(rejecting!.slip_id), body })),
    KEYS,
  );
  // TK-03: chỉ rõ dòng vượt tồn khả dụng; ném lại để hộp thoại giữ nguyên cho người dùng sửa
  const submitSlip = (body: SlipCreate) => {
    setProblems([]);
    return create.mutateAsync(body).catch((error) => {
      setProblems(stockProblems(error, names));
      throw error;
    });
  };

  return (
    <Card
      title="Phiếu kho"
      extra={
        <Space wrap>
          <Select
            allowClear
            placeholder="Mọi trạng thái"
            style={{ minWidth: 160 }}
            options={optionsOf(SLIP_STATUS_LABEL)}
            value={status}
            onChange={setStatus}
          />
          {!isManager && (
            <>
              <Button onClick={() => setDialog("inbound")}>Ghi nhập hàng</Button>
              <Button onClick={() => setDialog("slip")}>Lập phiếu điều chỉnh, xuất</Button>
            </>
          )}
        </Space>
      }
    >
      <Table<Slip>
        rowKey="slip_id"
        loading={slips.isPending}
        dataSource={slips.data}
        scroll={{ x: true }}
        expandable={{
          expandedRowRender: (slip) => (
            <>
              <Table<Schemas["StockSlipItem"]>
                rowKey="product_id"
                size="small"
                pagination={false}
                dataSource={slip.items}
                columns={[
                  { title: "Sản phẩm", dataIndex: "product_id", render: productLabel },
                  { title: "Số lượng", dataIndex: "quantity", align: "right" },
                ]}
              />
              {slip.approved_by && (
                <p>
                  {SLIP_STATUS_LABEL[slip.status]} lúc {dateTime(slip.finalized_at)} bởi{" "}
                  {slip.approved_by}
                  {slip.decision_reason && `: ${slip.decision_reason}`}
                </p>
              )}
            </>
          ),
        }}
        columns={[
          { title: "Mã phiếu", dataIndex: "slip_id" },
          {
            title: "Loại",
            dataIndex: "type",
            render: (type: Slip["type"]) => SLIP_TYPE_LABEL[type],
          },
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (value: Slip["status"]) => (
              <Tag color={STATUS_COLOR[value]}>{SLIP_STATUS_LABEL[value]}</Tag>
            ),
          },
          { title: "Lý do", dataIndex: "reason" },
          {
            title: "Phiếu giao",
            render: (_, slip) =>
              slip.delivery_no && `${slip.counterparty} – số ${slip.delivery_no}`,
          },
          { title: "Điều chỉnh phiếu", dataIndex: "adjusts_slip_id" },
          { title: "Người lập", dataIndex: "created_by" },
          { title: "Lập lúc", dataIndex: "created_at", render: dateTime },
          ...(isManager
            ? [
                {
                  title: "Thao tác",
                  render: (_: unknown, slip: Slip) =>
                    slip.status === "PENDING" &&
                    APPROVABLE.includes(slip.type) && (
                      <Space wrap>
                        <Popconfirm
                          title={`Duyệt phiếu ${slip.slip_id}? Tồn sẽ thay đổi ngay.`}
                          onConfirm={() => approve.mutate(slip.slip_id)}
                        >
                          <Button size="small" type="primary">
                            Duyệt
                          </Button>
                        </Popconfirm>
                        <Button size="small" danger onClick={() => setRejecting(slip)}>
                          Từ chối
                        </Button>
                      </Space>
                    ),
                },
              ]
            : []),
        ]}
      />

      {rejecting && (
        <FormModal<Schemas["StockSlipReject"]>
          title={`Từ chối phiếu ${rejecting.slip_id}`}
          onClose={() => setRejecting(null)}
          onSubmit={reject.mutateAsync}
        >
          <Form.Item label="Lý do từ chối" name="reason" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea />
          </Form.Item>
        </FormModal>
      )}

      {dialog === "inbound" && (
        <FormModal<InboundCreate>
          title="Ghi nhập hàng theo phiếu giao"
          initialValues={{ type: "IN_WAREHOUSE", items: [{} as Schemas["StockSlipItem"]] }}
          onClose={close}
          onSubmit={inbound.mutateAsync}
        >
          <Form.Item label="Nguồn hàng" name="type" rules={[{ required: true }]}>
            <Select options={INBOUND_TYPES} />
          </Form.Item>
          <Form.Item
            label="Bên giao"
            name="counterparty"
            extra="Kho tổng hoặc tên nhà cung cấp, như trên phiếu giao"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="Số phiếu giao"
            name="delivery_no"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="Sản phẩm và số lượng thực nhận" required>
            <ItemsField />
          </Form.Item>
        </FormModal>
      )}

      {dialog === "slip" && (
        <FormModal<SlipCreate>
          title="Lập phiếu điều chỉnh, xuất"
          initialValues={{ items: [{} as Schemas["StockSlipItem"]] }}
          onClose={close}
          onSubmit={submitSlip}
        >
          {problems.length > 0 && (
            <Alert
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
              message="Phiếu xuất vượt tồn khả dụng"
              description={
                <ul style={{ margin: 0 }}>
                  {problems.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              }
            />
          )}
          <Form.Item label="Loại phiếu" name="type" rules={[{ required: true }]}>
            <Select options={SLIP_TYPES} />
          </Form.Item>
          <Form.Item label="Lý do" name="reason" rules={[{ required: true, whitespace: true }]}>
            <Input.TextArea />
          </Form.Item>
          <Form.Item noStyle dependencies={["type"]}>
            {({ getFieldValue }) =>
              ADJUST_TYPES.includes(getFieldValue("type")) && (
                // preserve={false}: đổi sang phiếu xuất thì bỏ giá trị, tránh VALIDATION_ERROR TK-04
                <Form.Item label="Phiếu bị sai (nếu có)" name="adjusts_slip_id" preserve={false}>
                  <Select
                    allowClear
                    showSearch
                    optionFilterProp="label"
                    options={(allSlips.data ?? []).map((slip) => ({
                      value: slip.slip_id,
                      label: `${slip.slip_id} – ${SLIP_TYPE_LABEL[slip.type]} – ${dateTime(slip.created_at)}`,
                    }))}
                  />
                </Form.Item>
              )
            }
          </Form.Item>
          <ItemsField />
        </FormModal>
      )}
    </Card>
  );
}
