import { Button, Layout, Menu, Spin, Typography } from "antd";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { LoginPage } from "./features/auth/LoginPage";
import { ROLE_LABEL } from "./labels";
import { menuFor } from "./menu";

export function App() {
  const { user, loading, logout } = useAuth();
  const location = useLocation();

  if (loading) return <Spin fullscreen />;
  if (!user) return <LoginPage />;

  const items = menuFor(user.role);
  const identity = [user.full_name, ROLE_LABEL[user.role], user.branch_id].filter(Boolean);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          items={items.map((item) => ({
            key: item.path,
            label: <Link to={item.path}>{item.label}</Link>,
          }))}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 16,
            background: "#fff",
          }}
        >
          <Typography.Text>{identity.join(" · ")}</Typography.Text>
          <Button onClick={logout}>Đăng xuất</Button>
        </Layout.Header>
        <Layout.Content style={{ padding: 24 }}>
          <Routes>
            {items.map((item) => (
              <Route key={item.path} path={item.path} element={item.element} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
