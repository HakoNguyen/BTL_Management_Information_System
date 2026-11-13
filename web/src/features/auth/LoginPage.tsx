import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Card, Form, Input } from "antd";
import { useAuth } from "../../auth";

type LoginForm = { username: string; password: string };

export function LoginPage() {
  const { login } = useAuth();
  const submit = useMutation({
    mutationFn: (values: LoginForm) => login(values.username, values.password),
  });

  return (
    <div style={{ display: "grid", placeItems: "center", minHeight: "100vh", background: "#f5f5f5" }}>
      <Card title="Quản lý bán hàng – Đăng nhập" style={{ width: 360 }}>
        {submit.error && (
          <Alert type="error" showIcon message={submit.error.message} style={{ marginBottom: 16 }} />
        )}
        <Form<LoginForm> layout="vertical" onFinish={(values) => submit.mutate(values)}>
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
      </Card>
    </div>
  );
}
