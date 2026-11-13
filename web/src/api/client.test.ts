import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ApiError, client, token, unwrap } from "./client";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  });
});

afterEach(() => vi.unstubAllGlobals());

function respondWith(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async (_request: Request) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("gọi /api, gắn token vào header Authorization và trả dữ liệu", async () => {
  token.set("abc");
  const fetchMock = respondWith(200, {
    employee_id: "NV1",
    full_name: "An",
    role: "HQ",
    branch_id: null,
  });

  const me = await unwrap(client.GET("/auth/me"));

  expect(me.employee_id).toBe("NV1");
  const request = fetchMock.mock.calls[0][0];
  expect(request.url).toBe("http://localhost/api/auth/me");
  expect(request.headers.get("Authorization")).toBe("Bearer abc");
});

test("lỗi API thành ApiError mang error_code; 401 thì xóa token", async () => {
  token.set("het-han");
  respondWith(401, { error_code: "UNAUTHORIZED", message: "Chưa đăng nhập", details: {} });

  const error = await unwrap(client.GET("/auth/me")).catch((caught: unknown) => caught);

  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ status: 401, code: "UNAUTHORIZED", message: "Chưa đăng nhập" });
  expect(token.get()).toBeNull();
});

test("lỗi nghiệp vụ giữ nguyên token và mang details.rule", async () => {
  token.set("abc");
  respondWith(403, { error_code: "FORBIDDEN", message: "Sai vai trò", details: { rule: "K-01" } });

  const error = await unwrap(client.GET("/auth/me")).catch((caught: unknown) => caught);

  expect(error).toMatchObject({ status: 403, details: { rule: "K-01" } });
  expect(token.get()).toBe("abc");
});
