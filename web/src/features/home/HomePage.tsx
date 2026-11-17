import { Card, Col, Descriptions, Row, Space, Typography } from "antd";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth";
import { ROLE_LABEL } from "../../labels";
// menu.tsx cũng import trang này; vòng import an toàn vì menuFor chỉ gọi lúc render
import { menuFor } from "../../menu";
import { BRAND } from "../../ui";

export function HomePage() {
  const { user } = useAuth();
  if (!user) return null;

  // Lối tắt tới các trang vai trò này được dùng (cùng danh sách với menu, trừ trang chủ)
  const shortcuts = menuFor(user.role).filter((item) => item.path !== "/");

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card>
        <Typography.Title level={3} style={{ marginTop: 0 }}>
          Xin chào, {user.full_name}
        </Typography.Title>
        <Descriptions
          column={{ xs: 1, sm: 2, lg: 4 }}
          items={[
            { key: "id", label: "Mã nhân viên", children: user.employee_id },
            { key: "role", label: "Vai trò", children: ROLE_LABEL[user.role] },
            { key: "branch", label: "Chi nhánh", children: user.branch_id ?? "Trụ sở" },
          ]}
        />
      </Card>
      <Card title="Chức năng của bạn">
        <Row gutter={[16, 16]}>
          {shortcuts.map((item) => (
            <Col key={item.path} xs={24} sm={12} lg={8} xl={6}>
              <Link to={item.path}>
                <Card hoverable size="small" style={{ borderLeft: `4px solid ${BRAND}` }}>
                  <Typography.Text strong>{item.label}</Typography.Text>
                </Card>
              </Link>
            </Col>
          ))}
        </Row>
      </Card>
    </Space>
  );
}
