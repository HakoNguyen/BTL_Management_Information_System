// 1.2 Nhóm sản phẩm (Trụ sở). Xóa nhóm còn sản phẩm bị API chặn (SP-01).
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Form, Input, Popconfirm, Space, Table } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { FormModal, useWrite } from "../../ui";

type ProductGroup = Schemas["ProductGroup"];

export function ProductGroupsPage() {
  const groups = useQuery({
    queryKey: ["product-groups"],
    queryFn: () => unwrap(client.GET("/product-groups")),
  });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ProductGroup | null>(null);
  const groupPath = (id: string) => ({ params: { path: { group_id: id } } });

  const create = useWrite(
    (body: Schemas["ProductGroupCreate"]) => unwrap(client.POST("/product-groups", { body })),
    ["product-groups"],
  );
  const update = useWrite(
    (body: Schemas["ProductGroupUpdate"]) =>
      unwrap(
        client.PATCH("/product-groups/{group_id}", { ...groupPath(editing?.group_id ?? ""), body }),
      ),
    ["product-groups"],
  );
  const remove = useWrite(
    (id: string) => unwrap(client.DELETE("/product-groups/{group_id}", groupPath(id))),
    ["product-groups"],
  );

  const fields = (
    <>
      <Form.Item label="Tên nhóm" name="name" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Mô tả" name="description">
        <Input.TextArea />
      </Form.Item>
    </>
  );

  return (
    <Card
      title="Nhóm sản phẩm"
      extra={<Button onClick={() => setCreating(true)}>Thêm nhóm</Button>}
    >
      <Table<ProductGroup>
        rowKey="group_id"
        loading={groups.isPending}
        dataSource={groups.data}
        columns={[
          { title: "Mã nhóm", dataIndex: "group_id" },
          { title: "Tên nhóm", dataIndex: "name" },
          { title: "Mô tả", dataIndex: "description" },
          {
            title: "Thao tác",
            render: (_, group) => (
              <Space>
                <Button size="small" onClick={() => setEditing(group)}>
                  Sửa
                </Button>
                <Popconfirm
                  title={`Xóa nhóm ${group.name}?`}
                  onConfirm={() => remove.mutate(group.group_id)}
                >
                  <Button size="small" danger>
                    Xóa
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      {creating && (
        <FormModal<Schemas["ProductGroupCreate"]>
          title="Thêm nhóm sản phẩm"
          onClose={() => setCreating(false)}
          onSubmit={create.mutateAsync}
        >
          <Form.Item label="Mã nhóm" name="group_id" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {fields}
        </FormModal>
      )}

      {editing && (
        <FormModal<Schemas["ProductGroupUpdate"]>
          title={`Sửa nhóm ${editing.group_id}`}
          initialValues={editing}
          onClose={() => setEditing(null)}
          onSubmit={update.mutateAsync}
        >
          {fields}
        </FormModal>
      )}
    </Card>
  );
}
