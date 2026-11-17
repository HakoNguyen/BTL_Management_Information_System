// 2.2 cập nhật, 2.3 danh sách và tra cứu khách hàng; 2.4 lịch sử mua và trả (NVBH). Khách mới ghi nhận
// (2.1) ngay lúc lập đơn ở trang Đơn hàng. KH-01..KH-04 do API kiểm tra (chuẩn hóa số, trùng số, không
// tra KHLE, xác minh số khi xem lịch sử).
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Modal, Space, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime } from "../../format";
import { ORDER_STATUS_LABEL } from "../../labels";
import { FormModal, STATUS_COLOR, moneyColumn, useWrite } from "../../ui";
import { returnColumns } from "../returns/ReturnsPage";

type Customer = Schemas["Customer"];

const customerPath = (id: string) => ({ params: { path: { customer_id: id } } });

export function CustomersPage() {
  const customers = useQuery({
    queryKey: ["customers", "all"],
    queryFn: () => unwrap(client.GET("/customers")),
  });
  const [keyword, setKeyword] = useState("");
  const k = keyword.trim().toLowerCase();
  const shown = (customers.data ?? []).filter(
    (c) => !k || [c.customer_id, c.full_name, c.phone ?? ""].some((v) => v.toLowerCase().includes(k)),
  );
  const [dialog, setDialog] = useState<{ kind: "edit" | "verify"; customer: Customer } | null>(null);
  const [history, setHistory] = useState<{ customerId: string; phone: string } | null>(null);
  const close = () => setDialog(null);
  const id = dialog?.customer?.customer_id ?? "";

  const historyQuery = useQuery({
    queryKey: ["customers", history?.customerId, "history", history?.phone],
    queryFn: () =>
      unwrap(
        client.GET("/customers/{customer_id}/history", {
          params: { path: { customer_id: history!.customerId }, query: { phone: history!.phone } },
        }),
      ),
    enabled: history !== null,
    retry: false,
  });

  const update = useWrite(
    (body: Schemas["CustomerUpdate"]) =>
      unwrap(client.PATCH("/customers/{customer_id}", { ...customerPath(id), body })),
    ["customers"],
  );

  return (
    <Card title="Khách hàng">
      <Input.Search
        allowClear
        placeholder="Lọc theo tên, số điện thoại hoặc mã khách"
        style={{ marginBottom: 16, maxWidth: 420 }}
        value={keyword}
        onChange={(event) => setKeyword(event.target.value)}
      />
      {customers.error && (
        <Alert type="error" showIcon message={customers.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Customer>
        rowKey="customer_id"
        loading={customers.isPending}
        dataSource={shown}
        locale={{ emptyText: k ? "Không tìm thấy" : "Chưa có khách có hồ sơ" }}
        pagination={{ pageSize: 10, hideOnSinglePage: true, showSizeChanger: false }}
        scroll={{ x: true }}
        columns={[
          { title: "Mã khách", dataIndex: "customer_id" },
          { title: "Họ tên", dataIndex: "full_name" },
          { title: "Số điện thoại", dataIndex: "phone" },
          { title: "Địa chỉ", dataIndex: "address" },
          { title: "Ngày đăng ký", dataIndex: "registered_on" },
          {
            title: "Thao tác",
            render: (_, customer) => (
              <Space wrap>
                <Button size="small" onClick={() => setDialog({ kind: "edit", customer })}>
                  Sửa
                </Button>
                <Button size="small" onClick={() => setDialog({ kind: "verify", customer })}>
                  Lịch sử mua và trả
                </Button>
              </Space>
            ),
          },
        ]}
      />

      {dialog?.kind === "edit" && (
        <FormModal<Schemas["CustomerUpdate"]>
          title={`Sửa khách ${id} – ${dialog.customer.full_name}`}
          initialValues={{
            phone: dialog.customer.phone ?? undefined,
            address: dialog.customer.address,
          }}
          onClose={close}
          onSubmit={update.mutateAsync}
        >
          <Form.Item label="Số điện thoại" name="phone" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Địa chỉ" name="address">
            <Input />
          </Form.Item>
        </FormModal>
      )}

      {dialog?.kind === "verify" && (
        <FormModal<{ phone: string }>
          title={`Xác minh khách ${id} trước khi xem lịch sử`}
          onClose={close}
          onSubmit={async ({ phone }) => setHistory({ customerId: id, phone })}
        >
          <Form.Item label="Số điện thoại khách đọc" name="phone" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </FormModal>
      )}

      {history && (
        <Modal
          open
          width={960}
          title={`Lịch sử mua và trả của ${history.customerId}`}
          footer={null}
          onCancel={() => setHistory(null)}
        >
          {historyQuery.error && <Alert type="error" showIcon message={historyQuery.error.message} />}
          {historyQuery.data && (
            <>
              <Typography.Title level={5}>Đơn đã mua</Typography.Title>
              <Table<Schemas["Order"]>
                rowKey="order_id"
                size="small"
                dataSource={historyQuery.data.orders}
                scroll={{ x: true }}
                columns={[
                  { title: "Mã đơn", dataIndex: "order_id" },
                  { title: "Chi nhánh", dataIndex: "branch_id" },
                  { title: "Hoàn tất lúc", dataIndex: "completed_at", render: dateTime },
                  {
                    title: "Trạng thái",
                    dataIndex: "status",
                    render: (status: Schemas["OrderStatus"]) => <Tag color={STATUS_COLOR[status]}>{ORDER_STATUS_LABEL[status]}</Tag>,
                  },
                  moneyColumn("Tổng tiền", "total"),
                ]}
              />
              <Typography.Title level={5}>Phiếu trả</Typography.Title>
              <Table<Schemas["ReturnSlip"]>
                rowKey="return_id"
                size="small"
                dataSource={historyQuery.data.returns}
                scroll={{ x: true }}
                columns={returnColumns}
              />
            </>
          )}
        </Modal>
      )}
    </Card>
  );
}
