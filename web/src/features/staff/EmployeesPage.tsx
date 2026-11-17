// 6.1 Hồ sơ nhân viên, 6.2 phân công, 6.3 tài khoản (Trụ sở). Quy tắc NV-01..NV-04 do API kiểm tra.
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { client, unwrap, type Role, type Schemas } from "../../api/client";
import {
  ACCOUNT_STATUS_LABEL,
  EMPLOYEE_STATUS_LABEL,
  ROLE_LABEL,
  optionsOf,
} from "../../labels";
import { BranchFilter, FormModal, STATUS_COLOR, useWrite } from "../../ui";

type Employee = Schemas["Employee"];
type Path = { params: { path: { employee_id: string } } };
type Dialog = "create" | "edit" | "assign" | "account";

const ROLE_COLOR: Record<Role, string> = {
  HQ: "magenta",
  MANAGER: "gold",
  SALES: "blue",
  CASHIER: "cyan",
  WAREHOUSE: "orange",
};

const path = (id: string): Path => ({ params: { path: { employee_id: id } } });
const KEYS = ["employees"];

export function EmployeesPage() {
  const employees = useQuery({
    queryKey: ["employees"],
    queryFn: () => unwrap(client.GET("/employees")),
  });
  const branches = useQuery({
    queryKey: ["branches"],
    queryFn: () => unwrap(client.GET("/branches")),
  });
  const [role, setRole] = useState<Role | "ALL">("ALL");
  const [branchId, setBranchId] = useState<string>();
  const [dialog, setDialog] = useState<{ kind: Dialog; employee?: Employee } | null>(null);
  const close = () => setDialog(null);
  const id = dialog?.employee?.employee_id ?? "";

  const create = useWrite(
    (body: Schemas["EmployeeCreate"]) => unwrap(client.POST("/employees", { body })),
    KEYS,
  );
  const update = useWrite(
    (body: Schemas["EmployeeUpdate"]) =>
      unwrap(client.PATCH("/employees/{employee_id}", { ...path(id), body })),
    KEYS,
  );
  const assign = useWrite(
    (body: Schemas["AssignmentRequest"]) =>
      unwrap(client.PUT("/employees/{employee_id}/assignment", { ...path(id), body })),
    KEYS,
  );
  const issue = useWrite(
    (body: Schemas["AccountCreate"]) =>
      unwrap(client.POST("/employees/{employee_id}/account", { ...path(id), body })),
    KEYS,
  );
  const resetPassword = useWrite(
    (employeeId: string) =>
      unwrap(client.POST("/employees/{employee_id}/account/reset-password", path(employeeId))),
    [], // danh sách nhân viên không đổi
  );
  const lock = useWrite(
    (employeeId: string) =>
      unwrap(client.POST("/employees/{employee_id}/account/lock", path(employeeId))),
    KEYS,
  );
  const unlock = useWrite(
    (employeeId: string) =>
      unwrap(client.POST("/employees/{employee_id}/account/unlock", path(employeeId))),
    KEYS,
  );
  const leave = useWrite(
    (employeeId: string) => unwrap(client.POST("/employees/{employee_id}/leave", path(employeeId))),
    KEYS,
  );

  // Chỉ gợi ý chi nhánh đang hoạt động; API vẫn kiểm tra NV-04
  const branchOptions = (branches.data ?? [])
    .filter((branch) => branch.status === "ACTIVE")
    .map((branch) => ({ value: branch.branch_id, label: `${branch.branch_id} – ${branch.name}` }));

  const assignmentFields = (
    <>
      <Form.Item label="Vai trò" name="role" rules={[{ required: true }]}>
        <Select options={optionsOf(ROLE_LABEL)} />
      </Form.Item>
      <Form.Item label="Chi nhánh (để trống với Trụ sở)" name="branch_id">
        <Select allowClear options={branchOptions} />
      </Form.Item>
    </>
  );
  const profileFields = (
    <>
      <Form.Item label="Họ tên" name="full_name" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item label="Điện thoại" name="phone">
        <Input />
      </Form.Item>
      <Form.Item label="Ngày vào làm" name="hired_on" rules={[{ required: true }]}>
        <Input type="date" />
      </Form.Item>
    </>
  );

  // Mật khẩu tạm chỉ trả về một lần (6.3): hiện ngay để trụ sở bàn giao
  const showPassword = (title: string, issued: Schemas["AccountIssued"]) =>
    Modal.success({
      title,
      content: (
        <>
          <p>Tên đăng nhập: {issued.username}</p>
          <p>
            Mật khẩu tạm: <Typography.Text copyable>{issued.temporary_password}</Typography.Text>
          </p>
          <p>Mật khẩu này không hiển thị lại. Bàn giao cho nhân viên ngay.</p>
        </>
      ),
    });
  const issueAccount = async (body: Schemas["AccountCreate"]) =>
    showPassword("Đã cấp tài khoản", await issue.mutateAsync(body));
  const reissuePassword = (employeeId: string) =>
    resetPassword.mutate(employeeId, {
      onSuccess: (issued) => showPassword("Đã cấp lại mật khẩu tạm", issued),
    });

  return (
    <Card
      title="Nhân viên"
      extra={<Button onClick={() => setDialog({ kind: "create" })}>Thêm nhân viên</Button>}
    >
      <Space wrap style={{ marginBottom: 16 }}>
        <Segmented<Role | "ALL">
          value={role}
          onChange={setRole}
          options={[{ value: "ALL", label: "Tất cả" }, ...optionsOf(ROLE_LABEL)]}
        />
        <BranchFilter value={branchId} onChange={setBranchId} />
      </Space>
      <Table<Employee>
        key={`${role}-${branchId}`} // đổi bộ lọc thì quay về trang 1
        rowKey="employee_id"
        loading={employees.isPending}
        dataSource={employees.data?.filter(
          (e) => (role === "ALL" || e.role === role) && (!branchId || e.branch_id === branchId),
        )}
        pagination={{ pageSize: 5, simple: true, hideOnSinglePage: true }}
        scroll={{ x: true }}
        columns={[
          { title: "Mã", dataIndex: "employee_id" },
          { title: "Họ tên", dataIndex: "full_name" },
          { title: "Điện thoại", dataIndex: "phone" },
          {
            title: "Vai trò",
            dataIndex: "role",
            render: (role: Role) => <Tag color={ROLE_COLOR[role]}>{ROLE_LABEL[role]}</Tag>,
          },
          {
            title: "Chi nhánh",
            dataIndex: "branch_id",
            render: (branchId: string | null) => branchId ?? "Trụ sở",
          },
          { title: "Ngày vào làm", dataIndex: "hired_on" },
          {
            title: "Trạng thái",
            dataIndex: "status",
            render: (status: Employee["status"]) => (
              <Tag color={STATUS_COLOR[status]}>{EMPLOYEE_STATUS_LABEL[status]}</Tag>
            ),
          },
          {
            title: "Tài khoản",
            render: (_, employee) =>
              employee.username === null || employee.account_status === null ? (
                "Chưa cấp"
              ) : (
                <Space>
                  {employee.username}
                  <Tag color={STATUS_COLOR[employee.account_status]}>
                    {ACCOUNT_STATUS_LABEL[employee.account_status]}
                  </Tag>
                </Space>
              ),
          },
          {
            title: "Thao tác",
            render: (_, employee) => {
              const open = (kind: Dialog) => () => setDialog({ kind, employee });
              const target = employee.employee_id;
              if (employee.status === "LEFT")
                return (
                  <Button size="small" onClick={open("edit")}>
                    Sửa
                  </Button>
                );
              return (
                <Space wrap>
                  <Button size="small" onClick={open("edit")}>
                    Sửa
                  </Button>
                  <Button size="small" onClick={open("assign")}>
                    Phân công
                  </Button>
                  {employee.account_status === null && (
                    <Button size="small" onClick={open("account")}>
                      Cấp tài khoản
                    </Button>
                  )}
                  {employee.account_status === "ACTIVE" && (
                    <Popconfirm title="Khóa tài khoản?" onConfirm={() => lock.mutate(target)}>
                      <Button size="small">Khóa tài khoản</Button>
                    </Popconfirm>
                  )}
                  {employee.account_status === "LOCKED" && (
                    <Popconfirm title="Mở khóa tài khoản?" onConfirm={() => unlock.mutate(target)}>
                      <Button size="small">Mở khóa</Button>
                    </Popconfirm>
                  )}
                  {employee.account_status !== null && (
                    <Popconfirm
                      title="Cấp lại mật khẩu tạm?"
                      description="Mật khẩu cũ hết hiệu lực ngay."
                      onConfirm={() => reissuePassword(target)}
                    >
                      <Button size="small">Cấp lại mật khẩu</Button>
                    </Popconfirm>
                  )}
                  <Popconfirm
                    title={`Chuyển ${employee.full_name} sang Đã nghỉ?`}
                    onConfirm={() => leave.mutate(target)}
                  >
                    <Button size="small" danger>
                      Cho nghỉ
                    </Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />

      {dialog?.kind === "create" && (
        <FormModal<Schemas["EmployeeCreate"]>
          title="Thêm nhân viên"
          onClose={close}
          onSubmit={create.mutateAsync}
        >
          <Form.Item label="Mã nhân viên" name="employee_id" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          {profileFields}
          {assignmentFields}
        </FormModal>
      )}

      {dialog?.kind === "edit" && (
        <FormModal<Schemas["EmployeeUpdate"]>
          title={`Sửa hồ sơ ${id}`}
          initialValues={dialog.employee}
          onClose={close}
          onSubmit={update.mutateAsync}
        >
          {profileFields}
        </FormModal>
      )}

      {dialog?.kind === "assign" && (
        <FormModal<Schemas["AssignmentRequest"]>
          title={`Phân công ${id}`}
          initialValues={dialog.employee}
          onClose={close}
          onSubmit={assign.mutateAsync}
        >
          {assignmentFields}
        </FormModal>
      )}

      {dialog?.kind === "account" && (
        <FormModal<Schemas["AccountCreate"]>
          title={`Cấp tài khoản cho ${id}`}
          onClose={close}
          onSubmit={issueAccount}
        >
          <Form.Item label="Tên đăng nhập" name="username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </FormModal>
      )}
    </Card>
  );
}
