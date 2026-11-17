import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useAuth } from "../../auth";
import { BRAND, NAVY } from "../../ui";

type LoginForm = { username: string; password: string };

export function LoginPage() {
  const { login } = useAuth();
  const submit = useMutation({
    mutationFn: (values: LoginForm) => login(values.username, values.password),
  });

  return (
    <div
      style={{
        display: "grid",
        placeItems: "center",
        minHeight: "100vh",
        padding: 16,
        boxSizing: "border-box",
        background: `linear-gradient(135deg, ${BRAND} 0%, ${NAVY} 100%)`,
      }}
    >
      <Card style={{ width: "100%", maxWidth: 380, boxShadow: "0 12px 32px rgba(0, 0, 0, 0.2)" }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Typography.Title level={2} style={{ margin: 0, color: BRAND, letterSpacing: 1 }}>
            QLBH
          </Typography.Title>
          <Typography.Text type="secondary">Quản lý bán hàng chuỗi cửa hàng</Typography.Text>
        </div>
        {submit.error && (
          <Alert type="error" showIcon message={submit.error.message} style={{ marginBottom: 16 }} />
        )}
        <Form<LoginForm> layout="vertical" size="large" onFinish={(values) => submit.mutate(values)}>
          <Form.Item
            label="Tên đăng nhập"
            name="username"
            rules={[{ required: true, message: "Nhập tên đăng nhập" }]}
          >
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item
            label="Mật khẩu"
            name="password"
            rules={[{ required: true, message: "Nhập mật khẩu" }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submit.isPending}>
            Đăng nhập
          </Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ margin: "16px 0 0", textAlign: "center" }}>
          Quên mật khẩu? Liên hệ Trụ sở để được cấp lại.
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
