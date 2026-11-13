import { Card, Descriptions } from "antd";
import { useAuth } from "../../auth";
import { ROLE_LABEL } from "../../labels";

export function HomePage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <Card title="Phiên đăng nhập">
      <Descriptions
        column={1}
        items={[
          { key: "id", label: "Mã nhân viên", children: user.employee_id },
          { key: "name", label: "Họ tên", children: user.full_name },
          { key: "role", label: "Vai trò", children: ROLE_LABEL[user.role] },
          { key: "branch", label: "Chi nhánh", children: user.branch_id ?? "Trụ sở" },
        ]}
      />
    </Card>
  );
}
