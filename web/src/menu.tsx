// Danh sách trang và vai trò được thấy (ma trận phân quyền, đặc tả mục 2.2).
// Mỗi vòng nghiệp vụ thêm trang của mình bằng MỘT dòng ở đây; trang nằm trong src/features/<module>/.
import type { ReactNode } from "react";
import type { Role } from "./api/client";
import { HomePage } from "./features/home/HomePage";
import { ProductGroupsPage } from "./features/products/ProductGroupsPage";
import { ProductsPage } from "./features/products/ProductsPage";
import { ProductSalesReportPage } from "./features/reports/ProductSalesReportPage";
import { RevenueReportPage } from "./features/reports/RevenueReportPage";
import { StaffSalesReportPage } from "./features/reports/StaffSalesReportPage";
import { StockReportPage } from "./features/reports/StockReportPage";
import { BranchesPage } from "./features/staff/BranchesPage";
import { EmployeesPage } from "./features/staff/EmployeesPage";

export type MenuItem = {
  path: string;
  label: string;
  roles: Role[] | "all";
  element: ReactNode;
};

export const MENU: MenuItem[] = [
  { path: "/", label: "Trang chủ", roles: "all", element: <HomePage /> },
  { path: "/branches", label: "Chi nhánh", roles: ["HQ"], element: <BranchesPage /> },
  { path: "/employees", label: "Nhân viên", roles: ["HQ"], element: <EmployeesPage /> },
  { path: "/product-groups", label: "Nhóm sản phẩm", roles: ["HQ"], element: <ProductGroupsPage /> },
  { path: "/products", label: "Sản phẩm", roles: ["HQ"], element: <ProductsPage /> },
  { path: "/reports/revenue", label: "Doanh thu", roles: ["HQ"], element: <RevenueReportPage /> },
  { path: "/reports/products", label: "Sản phẩm bán", roles: ["HQ"], element: <ProductSalesReportPage /> },
  { path: "/reports/stock", label: "Tồn kho", roles: ["HQ"], element: <StockReportPage /> },
  { path: "/reports/staff-sales", label: "Doanh số nhân viên", roles: ["HQ"], element: <StaffSalesReportPage /> },
];

export const menuFor = (role: Role) =>
  MENU.filter((item) => item.roles === "all" || item.roles.includes(role));
