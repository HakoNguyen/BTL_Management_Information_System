import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // `npm run dev` gọi api đang chạy ở cổng 8000 (make up), cùng đường dẫn /api như nginx trong container
    proxy: {
      "/api": { target: "http://localhost:8000", rewrite: (path) => path.replace(/^\/api/, "") },
    },
  },
});
