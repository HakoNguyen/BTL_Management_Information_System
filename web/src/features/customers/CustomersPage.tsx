// 2.1 Ghi nhận, 2.2 cập nhật, 2.3 tra cứu khách hàng; 2.4 lịch sử mua và trả (NVBH).
// KH-01..KH-04 do API kiểm tra (chuẩn hóa số, trùng số, không tra KHLE, xác minh số khi xem lịch sử).
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime } from "../../format";
import { ORDER_STATUS_LABEL } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";
import { returnColumns } from "../returns/ReturnsPage";

type Customer = Schemas["Customer"];
type Search = { by: "phone" | "customer_id"; value: string };

const customerPath = (id: string) => ({ params: { path: { customer_id: id } } });

export function CustomersPage() {
  const [by, setBy] = useState<Search["by"]>("phone");
  const [search, setSearch] = useState<Search | null>(null);
  const customers = useQuery({
    queryKey: ["customers", search],
    queryFn: () =>
      unwrap(client.GET("/customers", { params: { query: { [search!.by]: search!.value } } })),
    enabled: search !== null,
  });
  const [dialog, setDialog] = useState<{ kind: "create" | "edit" | "verify"; customer?: Customer } | null>(
    null,
  );
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

  const create = useWrite(
    (body: Schemas["CustomerCreate"]) => unwrap(client.POST("/customers", { body })),
    ["customers"],
  );
  const update = useWrite(
    (body: Schemas["CustomerUpdate"]) =>
      unwrap(client.PATCH("/customers/{customer_id}", { ...customerPath(id), body })),
    ["customers"],
  );
  // Số đã có hồ sơ thì API trả hồ sơ có sẵn (2.1): hiện luôn hồ sơ đó
  const createAndShow = async (body: Schemas["CustomerCreate"]) => {
    const customer = await create.mutateAsync(body);
    setSearch({ by: "customer_id", value: customer.customer_id });
  };

  const fields = (
    <>
      <Form.Item label="Họ tên" name="full_name" rules={[{ required: true, whitespace: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Số điện thoại" name="phone" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Địa chỉ" name="address">
        <Input />
      </Form.Item>
    </>
  );

  return (
    <Card
      title="Khách hàng"
      extra={<Button onClick={() => setDialog({ kind: "create" })}>Thêm khách</Button>}
    >
      <Space.Compact style={{ marginBottom: 16, maxWidth: 480, width: "100%" }}>
        <Select<Search["by"]>
          value={by}
          onChange={setBy}
          style={{ width: 150 }}
          options={[
            { value: "phone", label: "Số điện thoại" },
            { value: "customer_id", label: "Mã khách" },
          ]}
        />
        <Input.Search
          enterButton="Tìm"
          onSearch={(value) => value.trim() && setSearch({ by, value: value.trim() })}
        />
      </Space.Compact>
      {customers.error && (
        <Alert type="error" showIcon message={customers.error.message} style={{ marginBottom: 16 }} />
      )}
      <Table<Customer>
        rowKey="customer_id"
        loading={customers.isFetching}
        dataSource={customers.data}
        locale={{ emptyText: search ? "Không tìm thấy" : "Nhập số điện thoại hoặc mã khách để tìm" }}
        pagination={false}
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

      {dialog?.kind === "create" && (
        <FormModal<Schemas["CustomerCreate"]> title="Thêm khách" onClose={close} onSubmit={createAndShow}>
          {fields}
        </FormModal>
      )}

      {dialog?.kind === "edit" && (
        <FormModal<Schemas["CustomerUpdate"]>
          title={`Sửa khách ${id}`}
          initialValues={{ ...dialog.customer, phone: dialog.customer?.phone ?? undefined }}
          onClose={close}
          onSubmit={update.mutateAsync}
        >
          {fields}
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
                    render: (status: Schemas["OrderStatus"]) => <Tag>{ORDER_STATUS_LABEL[status]}</Tag>,
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
