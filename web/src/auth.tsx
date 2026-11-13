// Phiên đăng nhập của giao diện. Quyền thật do API kiểm tra ở mỗi request (K-01);
// ở đây chỉ dùng vai trò để ẩn/hiện menu.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { client, token, unwrap, type CurrentUser } from "./api/client";

type Auth = {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<Auth | null>(null);
const ME_KEY = ["auth", "me"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({
    queryKey: ME_KEY,
    // Token hết hạn hoặc tài khoản bị khóa: coi như chưa đăng nhập
    queryFn: () => (token.get() ? unwrap(client.GET("/auth/me")).catch(() => null) : null),
  });

  const login = async (username: string, password: string) => {
    const result = await unwrap(client.POST("/auth/login", { body: { username, password } }));
    token.set(result.token);
    queryClient.setQueryData(ME_KEY, result.user);
  };

  const logout = () => {
    token.clear();
    // Bỏ dữ liệu đã tải của người vừa đăng xuất, để người đăng nhập sau không nhìn thấy
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
    queryClient.setQueryData(ME_KEY, null);
  };

  return (
    <AuthContext.Provider value={{ user: me.data ?? null, loading: me.isPending, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth phải dùng bên trong AuthProvider");
  return auth;
}
