// Danh sách trang và vai trò được thấy (ma trận phân quyền, đặc tả mục 2.2).
// Mỗi vòng nghiệp vụ thêm trang của mình bằng MỘT dòng ở đây; trang nằm trong src/features/<module>/.
import type { ReactNode } from "react";
import type { Role } from "./api/client";
import { CustomersPage } from "./features/customers/CustomersPage";
import { HomePage } from "./features/home/HomePage";
import { OrdersPage } from "./features/orders/OrdersPage";
import { InvoicesPage } from "./features/payments/InvoicesPage";
import { PaymentsPage } from "./features/payments/PaymentsPage";
import { ProductGroupsPage } from "./features/products/ProductGroupsPage";
import { ProductsPage } from "./features/products/ProductsPage";
import { ProductSalesReportPage } from "./features/reports/ProductSalesReportPage";
import { RevenueReportPage } from "./features/reports/RevenueReportPage";
import { StaffSalesReportPage } from "./features/reports/StaffSalesReportPage";
import { StockReportPage } from "./features/reports/StockReportPage";
import { RefundsPage } from "./features/returns/RefundsPage";
import { ReturnsPage } from "./features/returns/ReturnsPage";
import { ShiftsPage } from "./features/shifts/ShiftsPage";
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
  { path: "/reports/staff-sales", label: "Doanh số nhân viên", roles: ["HQ", "SALES"], element: <StaffSalesReportPage /> },
  { path: "/customers", label: "Khách hàng", roles: ["SALES"], element: <CustomersPage /> },
  { path: "/orders", label: "Đơn hàng", roles: ["SALES"], element: <OrdersPage /> },
  { path: "/returns", label: "Phiếu trả", roles: ["SALES"], element: <ReturnsPage /> },
  { path: "/shifts", label: "Ca thu ngân", roles: ["CASHIER"], element: <ShiftsPage /> },
  { path: "/payments", label: "Thu tiền", roles: ["CASHIER"], element: <PaymentsPage /> },
  { path: "/invoices", label: "Hóa đơn", roles: ["CASHIER"], element: <InvoicesPage /> },
  { path: "/refunds", label: "Hoàn tiền", roles: ["CASHIER"], element: <RefundsPage /> },
];

export const menuFor = (role: Role) =>
  MENU.filter((item) => item.roles === "all" || item.roles.includes(role));
