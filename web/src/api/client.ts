// Cách DUY NHẤT để giao diện gọi API. Đường dẫn, tham số và kiểu trả về lấy từ schema.d.ts
// (sinh từ OpenAPI bằng `make gen-api`), nên gõ sai tên endpoint hay tên trường là lỗi biên dịch.
//
//   const user = await unwrap(client.GET("/auth/me"));
//   await unwrap(client.POST("/auth/login", { body: { username, password } }));
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type CurrentUser = Schemas["CurrentUser"];
export type Role = Schemas["Role"];

// Thân lỗi của API: docs/api.md mục 2
type ApiErrorBody = { error_code: string; message: string; details: Record<string, unknown> };

export class ApiError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(
    readonly status: number,
    body?: Partial<ApiErrorBody>,
  ) {
    super(body?.message ?? `Lỗi ${status}`);
    this.code = body?.error_code ?? "INTERNAL_ERROR";
    this.details = body?.details ?? {};
  }
}

const TOKEN_KEY = "qlbh_token";
export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (value: string) => localStorage.setItem(TOKEN_KEY, value),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

// nginx (container web) và vite dev đều chuyển /api/* sang api, nên không cần CORS
const origin = typeof location === "undefined" ? "http://localhost" : location.origin;

export const client = createClient<paths>({
  baseUrl: `${origin}/api`,
  fetch: (request) => globalThis.fetch(request),
});

client.use({
  onRequest({ request }) {
    const value = token.get();
    if (value) request.headers.set("Authorization", `Bearer ${value}`);
    return request;
  },
});

/** Trả dữ liệu khi thành công; ném ApiError khi API báo lỗi. 401 thì xóa token để về trang đăng nhập. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok) {
    if (response.status === 401) token.clear();
    throw new ApiError(response.status, error as Partial<ApiErrorBody> | undefined);
  }
  return data as T;
}
