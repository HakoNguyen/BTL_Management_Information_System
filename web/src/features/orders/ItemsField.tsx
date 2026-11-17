// Ô chọn khách và các dòng sản phẩm của đơn (3.1). Tồn khả dụng lấy từ GET /stock (4.1 phục vụ 3.1).
import { useQuery } from "@tanstack/react-query";
import { Col, Form, Input, InputNumber, Row, Segmented, Select, Space } from "antd";
import { client, unwrap, type Schemas } from "../../api/client";
import { PRODUCT_STATUS_LABEL } from "../../labels";
import { AddButton, RemoveButton } from "../../ui";
import { stockText } from "./stockText";

export type CustomerMode = "WALK_IN" | "SAVED" | "NEW";
/** Form lập đơn: `customer_id` chỉ dùng khi chọn khách đã lưu; khách mới ghi nhận qua 2.1 trước. */
export type OrderForm = Schemas["OrderCreate"] & {
  mode: CustomerMode;
  new_customer?: Schemas["CustomerCreate"];
};

/** Khách lẻ (KHLE, KH-02), khách đã lưu (chọn từ danh sách 2.3) hoặc khách mới (2.1, KH-01). */
export function CustomerField() {
  const mode = Form.useWatch("mode", Form.useFormInstance()) as CustomerMode | undefined;
  const customers = useQuery({
    queryKey: ["customers", "all"],
    queryFn: () => unwrap(client.GET("/customers")),
    enabled: mode === "SAVED",
  });
  return (
    <>
      <Form.Item label="Khách hàng" name="mode">
        <Segmented<CustomerMode>
          options={[
            { value: "WALK_IN", label: "Khách lẻ" },
            { value: "SAVED", label: "Khách đã lưu" },
            { value: "NEW", label: "Khách mới" },
          ]}
        />
      </Form.Item>
      {mode === "SAVED" && (
        <Form.Item name="customer_id" rules={[{ required: true, message: "Chọn khách" }]}>
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Tìm theo tên, số điện thoại hoặc mã khách"
            loading={customers.isPending}
            options={(customers.data ?? []).map((c) => ({
              value: c.customer_id,
              label: `${c.full_name} · ${c.phone} · ${c.customer_id}`,
            }))}
          />
        </Form.Item>
      )}
      {mode === "NEW" && (
        <Space wrap align="start">
          <Form.Item
            label="Họ tên"
            name={["new_customer", "full_name"]}
            rules={[{ required: true, whitespace: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="Số điện thoại" name={["new_customer", "phone"]} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Địa chỉ" name={["new_customer", "address"]}>
            <Input />
          </Form.Item>
        </Space>
      )}
    </>
  );
}

/** Các dòng `items`: mỗi sản phẩm một dòng, số lượng nguyên > 0 (BH-01).
 * `withLevels`: hiện tồn và ngưỡng thay cho tồn khả dụng (yêu cầu bổ sung 4.4). */
export function ItemsField({ withLevels = false }: { withLevels?: boolean }) {
  const products = useQuery({
    queryKey: ["products"],
    queryFn: () => unwrap(client.GET("/products")),
  });
  const stock = useQuery({ queryKey: ["stock"], queryFn: () => unwrap(client.GET("/stock")) });
  const levels = new Map((stock.data ?? []).map((line) => [line.product_id, line]));
  const options = (products.data ?? []).map((product) => ({
    value: product.product_id,
    label: [
      `${product.product_id} – ${product.name}`,
      stockText(levels.get(product.product_id), withLevels),
      product.status === "DISCONTINUED" ? PRODUCT_STATUS_LABEL.DISCONTINUED : "",
    ]
      .filter(Boolean)
      .join(" · "),
  }));

  return (
    <Form.List
      name="items"
      rules={[
        {
          validator: async (_, items) => {
            if (!items?.length) throw new Error("Cần ít nhất một dòng");
          },
        },
      ]}
    >
      {(fields, { add, remove }, { errors }) => (
        <>
          <Row gutter={8} style={{ fontWeight: 500, marginBottom: 6 }}>
            <Col flex="auto">Sản phẩm</Col>
            <Col flex="96px">Số lượng</Col>
            <Col flex="32px" />
          </Row>
          {fields.map((field) => (
            <Row key={field.key} gutter={8} wrap={false}>
              <Col flex="auto" style={{ minWidth: 0 }}>
                <Form.Item name={[field.name, "product_id"]} rules={[{ required: true, message: "Chọn sản phẩm" }]}>
                  <Select showSearch optionFilterProp="label" placeholder="Gõ mã hoặc tên sản phẩm" options={options} />
                </Form.Item>
              </Col>
              <Col flex="96px">
                <Form.Item name={[field.name, "quantity"]} rules={[{ required: true, message: "Nhập số lượng" }]}>
                  <InputNumber min={1} precision={0} style={{ width: "100%" }} />
                </Form.Item>
              </Col>
              <Col flex="32px">
                <RemoveButton onClick={() => remove(field.name)} />
              </Col>
            </Row>
          ))}
          <AddButton onClick={() => add()}>+ Thêm sản phẩm</AddButton>
          <Form.ErrorList errors={errors} />
        </>
      )}
    </Form.List>
  );
}
