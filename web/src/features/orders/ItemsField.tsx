// Ô chọn khách và các dòng sản phẩm của đơn (3.1). Tồn khả dụng lấy từ GET /stock (4.1 phục vụ 3.1).
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button, Form, Input, InputNumber, Select, Space, message } from "antd";
import { client, unwrap } from "../../api/client";
import { PRODUCT_STATUS_LABEL } from "../../labels";
import { stockText } from "./stockText";

/** Mã khách: gõ thẳng (KHLE cho khách lẻ) hoặc tra theo số điện thoại (2.3). */
export function CustomerField() {
  const form = Form.useFormInstance();
  const lookup = useMutation({
    mutationFn: (phone: string) => unwrap(client.GET("/customers", { params: { query: { phone } } })),
    onSuccess: (found) => {
      if (found.length === 0) return message.warning("Không tìm thấy");
      form.setFieldValue("customer_id", found[0].customer_id);
      message.success(`Khách: ${found[0].full_name}`);
    },
    onError: (error) => message.error(error.message, 6),
  });
  return (
    <>
      <Form.Item label="Tra khách theo số điện thoại">
        <Input.Search
          enterButton="Tra"
          loading={lookup.isPending}
          onSearch={(phone) => phone && lookup.mutate(phone)}
        />
      </Form.Item>
      <Form.Item
        label="Mã khách"
        name="customer_id"
        extra="Khách không cung cấp thông tin: KHLE"
        rules={[{ required: true }]}
      >
        <Input />
      </Form.Item>
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
          {fields.map((field) => (
            <Space key={field.key} align="baseline" wrap>
              <Form.Item name={[field.name, "product_id"]} rules={[{ required: true }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  placeholder="Sản phẩm"
                  style={{ width: 340 }}
                  options={options}
                />
              </Form.Item>
              <Form.Item name={[field.name, "quantity"]} rules={[{ required: true }]}>
                <InputNumber min={1} precision={0} placeholder="Số lượng" />
              </Form.Item>
              <Button onClick={() => remove(field.name)}>Bỏ</Button>
            </Space>
          ))}
          <Button onClick={() => add()}>Thêm dòng</Button>
          <Form.ErrorList errors={errors} />
        </>
      )}
    </Form.List>
  );
}
