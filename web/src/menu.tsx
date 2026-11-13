// Danh sách trang và vai trò được thấy (ma trận phân quyền, đặc tả mục 2.2).
// Mỗi vòng nghiệp vụ thêm trang của mình bằng MỘT dòng ở đây; trang nằm trong src/features/<module>/.
import type { ReactNode } from "react";
import type { Role } from "./api/client";
import { HomePage } from "./features/home/HomePage";

export type MenuItem = {
  path: string;
  label: string;
  roles: Role[] | "all";
  element: ReactNode;
};

export const MENU: MenuItem[] = [
  { path: "/", label: "Trang chủ", roles: "all", element: <HomePage /> },
];

export const menuFor = (role: Role) =>
  MENU.filter((item) => item.roles === "all" || item.roles.includes(role));
