// 6.4 Chi nhánh (Trụ sở). Điều kiện ngừng hoạt động (NV-04) do API kiểm tra và liệt kê.
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Form, Input, Popconfirm, Space, Table, Tag } from "antd";
import { useState } from "react";
import { client, unwrap, type Schemas } from "../../api/client";
import { BRANCH_STATUS_LABEL } from "../../labels";
import { FormModal, useWrite } from "../../ui";

type Branch = Schemas["Branch"];

export function BranchesPage() {
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => unwrap(client.GET("/branches")),
  });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);

  const create = useWrite(
    (body: Schemas["BranchCreate"]) => unwrap(client.POST("/branches", { body })),
    ["branches"],
  );
  const update = useWrite(
    (body: Schemas["BranchUpdate"]) =>
      unwrap(
        client.PATCH("/branches/{branch_id}", {
          params: { path: { branch_id: editing?.branch_id ?? "" } },
          body,
        }),
      ),
    ["branches"],
  );
  const deactivate = useWrite(
    (id: string) =>
      unwrap(
        client.POST("/branches/{branch_id}/deactivate", { params: { path: { branch_id: id } } }),
      ),
    ["branches"],
  );

  const fields = (
    <>
      <Form.Item label="Tên" name="name" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Địa chỉ" name="address">
        <Input />
      </Form.Item>
      <Form.Item label="Điện thoại" name="phone">
        <Input />
      </Form.Item>
      <Form.Item label="Giờ đóng cửa" name="closing_time" rules={[{ required: true }]}>
        <Input type="time" step={1} />
      </Form.Item>
    </>
  );

  return (
    <Card
      title="Chi nhánh"
      extra={<Button onClick={() => setCreating(true)}>Thêm chi nhánh</Button>}
    >
      <Table<Branch>
        rowKey="branch_id"
        loading={branches.isPending}
        dataSource={branches.data}
        columns={[
          { title: "Mã", dataIndex: "branch_id" },
          { title: "Tên", dataIndex: "name" },
          { title: "Địa chỉ", dataIndex: "address" },
          { title: "Điện thoại", dataIndex: "phone" },
          { title: "Giờ đóng cửa", dataIndex: "closing_time" },
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (status: Branch["status"]) => (
              <Tag color={status === "ACTIVE" ? "green" : "default"}>
                {BRANCH_STATUS_LABEL[status]}
              </Tag>
            ),
          },
          {
            title: "Thao tác",
            render: (_, branch) => (
              <Space>
                <Button size="small" onClick={() => setEditing(branch)}>
                  Sửa
                </Button>
                {branch.status === "ACTIVE" && (
                  <Popconfirm
                    title={`Ngừng hoạt động chi nhánh ${branch.name}?`}
                    onConfirm={() => deactivate.mutate(branch.branch_id)}
                  >
                    <Button size="small" danger>
                      Ngừng hoạt động
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            ),
          },
        ]}
      />

      {creating && (
        <FormModal<Schemas["BranchCreate"]>
          title="Thêm chi nhánh"
          onClose={() => setCreating(false)}
          onSubmit={create.mutateAsync}
        >
          <Form.Item label="Mã chi nhánh" name="branch_id" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {fields}
        </FormModal>
      )}

      {editing && (
        <FormModal<Schemas["BranchUpdate"]>
          title={`Sửa chi nhánh ${editing.branch_id}`}
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
