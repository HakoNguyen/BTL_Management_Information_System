import { Avatar, Button, Layout, Menu, Space, Spin, Tag, Typography } from "antd";
import { useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { LoginPage } from "./features/auth/LoginPage";
import { ROLE_LABEL } from "./labels";
import { menuFor, type MenuItem } from "./menu";
import { BRAND } from "./ui";

const isReport = (item: MenuItem) => item.path.startsWith("/reports/");
const toMenu = (item: MenuItem) => ({
  key: item.path,
  label: <Link to={item.path}>{item.label}</Link>,
});

export function App() {
  const { user, loading, logout } = useAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  if (loading) return <Spin fullscreen />;
  if (!user) return <LoginPage />;

  const items = menuFor(user.role);
  const reports = items.filter(isReport);
  const current = items.find((item) => item.path === location.pathname);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {/* Ẩn, hiện bằng nút ☰ ở thanh trên; màn hình hẹp thì tự ẩn */}
      <Layout.Sider
        width={230}
        breakpoint="lg"
        collapsedWidth={0}
        collapsed={collapsed}
        onBreakpoint={setCollapsed}
        trigger={null}
      >
        <div style={{ padding: "20px 24px", color: "#fff" }}>
          <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: 1 }}>QLBH</div>
          <div style={{ fontSize: 12, opacity: 0.7 }}>Quản lý bán hàng chuỗi cửa hàng</div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={[
            ...items.filter((item) => !isReport(item)).map(toMenu),
            ...(reports.length
              ? [{ type: "group" as const, label: "Báo cáo", children: reports.map(toMenu) }]
              : []),
          ]}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            boxShadow: "0 1px 4px rgba(0, 21, 41, 0.08)",
          }}
        >
          <Space size="middle" align="center" style={{ minWidth: 0 }}>
            <Button
              type="text"
              aria-label={collapsed ? "Hiện menu" : "Ẩn menu"}
              title={collapsed ? "Hiện menu" : "Ẩn menu"}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 20 }}
            >
              ☰
            </Button>
            <Typography.Title level={4} style={{ margin: 0 }} ellipsis>
              {current?.label ?? "Trang chủ"}
            </Typography.Title>
          </Space>
          <Space size="middle" align="center">
            <Avatar style={{ background: BRAND }}>{user.full_name.charAt(0)}</Avatar>
            <Typography.Text strong>{user.full_name}</Typography.Text>
            <Tag color="blue" style={{ margin: 0 }}>
              {[ROLE_LABEL[user.role], user.branch_id].filter(Boolean).join(" · ")}
            </Tag>
            <Button onClick={logout}>Đăng xuất</Button>
          </Space>
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
