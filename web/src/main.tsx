import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth";
import { BRAND, NAVY } from "./ui";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={viVN}
        // Mọi bảng: ô không xuống dòng (cột nút vẫn tự xếp hàng), đệm dọc gọn hơn mặc định
        table={{ style: { whiteSpace: "nowrap" } }}
        theme={{
          token: { colorPrimary: BRAND, borderRadius: 8, colorBgLayout: "#f0f5ff" },
          components: {
            Layout: { siderBg: NAVY, headerBg: "#fff", headerPadding: "0 24px" },
            Menu: { darkItemBg: NAVY, darkSubMenuItemBg: NAVY, darkItemSelectedBg: BRAND },
            Table: { cellPaddingBlock: 10, headerBg: "#e6f4ff" },
            Card: { headerFontSize: 18 },
          },
        }}
      >
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  </StrictMode>,
);
