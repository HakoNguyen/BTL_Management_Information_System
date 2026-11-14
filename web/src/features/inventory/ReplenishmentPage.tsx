// 4.4 Yêu cầu bổ sung gửi kho tổng hoặc NCC (TK-06). Yêu cầu không làm tăng tồn, không có trạng thái giao nhận.
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Form, Input, Select, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { useAuth } from "../../auth";
import { dateTime } from "../../format";
import { REPLENISH_TYPE_LABEL, optionsOf } from "../../labels";
import { FormModal, useWrite } from "../../ui";
import { ItemsField } from "../orders/ItemsField";

type Request = Schemas["ReplenishmentRequest"];

export function ReplenishmentPage() {
  const requests = useQuery({
    queryKey: ["replenishment-requests"],
    queryFn: () => unwrap(client.GET("/replenishment-requests")),
  });
  const [open, setOpen] = useState(false);
  const isWarehouse = useAuth().user?.role === "WAREHOUSE";
  const create = useWrite(
    (body: Schemas["ReplenishmentCreate"]) =>
      unwrap(client.POST("/replenishment-requests", { body })),
    ["replenishment-requests"],
  );

  return (
    <Card
      title="Yêu cầu bổ sung"
      // QL chỉ xem; lập yêu cầu là việc của NV kho (ma trận 2.2)
      extra={
        isWarehouse && (
          <Button onClick={() => setOpen(true)}>Lập yêu cầu</Button>
        )
      }
    >
      <Table<Request>
        rowKey="request_id"
        loading={requests.isPending}
        dataSource={requests.data}
        scroll={{ x: true }}
        expandable={{
          expandedRowRender: (request) => (
            <Table<Schemas["StockSlipItem"]>
              rowKey="product_id"
              size="small"
              pagination={false}
              dataSource={request.items}
              columns={[
                { title: "Sản phẩm", dataIndex: "product_id" },
                { title: "Số lượng", dataIndex: "quantity", align: "right" },
              ]}
            />
          ),
        }}
        columns={[
          { title: "Mã yêu cầu", dataIndex: "request_id" },
          {
            title: "Hình thức",
            dataIndex: "type",
            render: (type: Request["type"]) => REPLENISH_TYPE_LABEL[type],
          },
          { title: "Nơi nhận", dataIndex: "recipient" },
          { title: "Người lập", dataIndex: "created_by" },
          { title: "Lập lúc", dataIndex: "created_at", render: dateTime },
        ]}
      />

      {open && (
        <FormModal<Schemas["ReplenishmentCreate"]>
          title="Lập yêu cầu bổ sung"
          initialValues={{ items: [{} as Schemas["StockSlipItem"]] }}
          onClose={() => setOpen(false)}
          onSubmit={create.mutateAsync}
        >
          <Form.Item label="Hình thức" name="type" rules={[{ required: true }]}>
            <Select options={optionsOf(REPLENISH_TYPE_LABEL)} />
          </Form.Item>
          <Form.Item
            label="Nơi nhận"
            name="recipient"
            extra="Kho tổng hoặc tên nhà cung cấp"
            rules={[{ required: true, whitespace: true }]}
          >
            <Input />
          </Form.Item>
          <ItemsField withLevels />
        </FormModal>
      )}
    </Card>
  );
}
