// 1.1 Sản phẩm, 1.2 đổi nhóm, 1.3 giá và lịch sử giá, 1.4 trạng thái (Trụ sở).
// Quy tắc SP-01..SP-04 do API kiểm tra; không có thao tác xóa sản phẩm (SP-04).
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { dateTime, money } from "../../format";
import { PRODUCT_STATUS_LABEL } from "../../labels";
import { FormModal, moneyColumn, useWrite } from "../../ui";

type Product = Schemas["Product"];
type Dialog = "create" | "edit" | "group" | "price" | "history";

const productPath = (id: string) => ({ params: { path: { product_id: id } } });
const KEYS = ["products"];

export function ProductsPage() {
  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => unwrap(client.GET("/products")),
  });
  const groups = useQuery({
    queryKey: ["product-groups"],
    queryFn: () => unwrap(client.GET("/product-groups")),
  });
  const [dialog, setDialog] = useState<{ kind: Dialog; product?: Product } | null>(null);
  const close = () => setDialog(null);
  const id = dialog?.product?.product_id ?? "";

  const history = useQuery({
    queryKey: ["products", id, "price-history"],
    queryFn: () => unwrap(client.GET("/products/{product_id}/price-history", productPath(id))),
    enabled: dialog?.kind === "history",
  });

  const create = useWrite(
    (body: Schemas["ProductCreate"]) => unwrap(client.POST("/products", { body })),
    KEYS,
  );
  const update = useWrite(
    (body: Schemas["ProductUpdate"]) =>
      unwrap(client.PATCH("/products/{product_id}", { ...productPath(id), body })),
    KEYS,
  );
  const changeGroup = useWrite(
    (body: Schemas["ProductGroupChange"]) =>
      unwrap(client.PUT("/products/{product_id}/group", { ...productPath(id), body })),
    KEYS,
  );
  const changePrice = useWrite(
    (body: Schemas["PriceChange"]) =>
      unwrap(client.PUT("/products/{product_id}/price", { ...productPath(id), body })),
    KEYS,
  );
  const changeStatus = useWrite(
    ({ productId, status }: { productId: string; status: Product["status"] }) =>
      unwrap(
        client.PUT("/products/{product_id}/status", { ...productPath(productId), body: { status } }),
      ),
    KEYS,
  );

  const groupName = new Map((groups.data ?? []).map((group) => [group.group_id, group.name]));
  const groupField = (
    <Form.Item label="Nhóm" name="group_id" rules={[{ required: true }]}>
      <Select
        options={(groups.data ?? []).map((group) => ({ value: group.group_id, label: group.name }))}
      />
    </Form.Item>
  );
  const priceField = (
    <Form.Item label="Giá (VND)" name="price" rules={[{ required: true }]}>
      <InputNumber min={1} precision={0} style={{ width: "100%" }} />
    </Form.Item>
  );
  const detailFields = (
    <>
      <Form.Item label="Tên" name="name" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Đơn vị tính" name="unit" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Mô tả" name="description">
        <Input.TextArea />
      </Form.Item>
    </>
  );

  return (
    <Card
      title="Sản phẩm"
      extra={<Button onClick={() => setDialog({ kind: "create" })}>Thêm sản phẩm</Button>}
    >
      <Table<Product>
        rowKey="product_id"
        loading={products.isPending}
        dataSource={products.data}
        scroll={{ x: true }}
        columns={[
          { title: "Mã", dataIndex: "product_id" },
          { title: "Tên", dataIndex: "name" },
          {
            title: "Nhóm",
            dataIndex: "group_id",
            render: (groupId: string) => groupName.get(groupId) ?? groupId,
          },
          { title: "Đơn vị", dataIndex: "unit" },
          moneyColumn("Giá hiện hành", "current_price"),
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (status: Product["status"]) => (
              <Tag color={status === "ON_SALE" ? "green" : "default"}>
                {PRODUCT_STATUS_LABEL[status]}
              </Tag>
            ),
          },
          {
            title: "Thao tác",
            render: (_, product) => {
              const open = (kind: Dialog) => () => setDialog({ kind, product });
              const next = product.status === "ON_SALE" ? "DISCONTINUED" : "ON_SALE";
              return (
                <Space wrap>
                  <Button size="small" onClick={open("edit")}>
                    Sửa
                  </Button>
                  <Button size="small" onClick={open("group")}>
                    Đổi nhóm
                  </Button>
                  <Button size="small" onClick={open("price")}>
                    Đổi giá
                  </Button>
                  <Button size="small" onClick={open("history")}>
                    Lịch sử giá
                  </Button>
                  <Popconfirm
                    title={`Chuyển ${product.name} sang ${PRODUCT_STATUS_LABEL[next]}?`}
                    onConfirm={() =>
                      changeStatus.mutate({ productId: product.product_id, status: next })
                    }
                  >
                    <Button size="small">{PRODUCT_STATUS_LABEL[next]}</Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />

      {dialog?.kind === "create" && (
        <FormModal<Schemas["ProductCreate"]>
          title="Thêm sản phẩm"
          onClose={close}
          onSubmit={create.mutateAsync}
        >
          <Form.Item label="Mã sản phẩm" name="product_id" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {detailFields}
          {groupField}
          {priceField}
        </FormModal>
      )}

      {dialog?.kind === "edit" && (
        <FormModal<Schemas["ProductUpdate"]>
          title={`Sửa sản phẩm ${id}`}
          initialValues={dialog.product}
          onClose={close}
          onSubmit={update.mutateAsync}
        >
          {detailFields}
        </FormModal>
      )}

      {dialog?.kind === "group" && (
        <FormModal<Schemas["ProductGroupChange"]>
          title={`Đổi nhóm ${id}`}
          initialValues={dialog.product}
          onClose={close}
          onSubmit={changeGroup.mutateAsync}
        >
          {groupField}
        </FormModal>
      )}

      {dialog?.kind === "price" && (
        <FormModal<Schemas["PriceChange"]>
          title={`Đổi giá ${id} (hiện hành ${money(dialog.product?.current_price ?? null)})`}
          onClose={close}
          onSubmit={changePrice.mutateAsync}
        >
          {priceField}
        </FormModal>
      )}

      {dialog?.kind === "history" && (
        <Modal open title={`Lịch sử giá ${id}`} footer={null} onCancel={close}>
          <Table<Schemas["PriceHistoryEntry"]>
            rowKey="effective_at"
            loading={history.isPending}
            dataSource={history.data}
            pagination={false}
            columns={[
              { title: "Áp dụng từ", dataIndex: "effective_at", render: dateTime },
              moneyColumn("Giá", "price"),
              { title: "Người đổi", dataIndex: "changed_by" },
            ]}
          />
        </Modal>
      )}
    </Card>
  );
}
