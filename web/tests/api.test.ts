import { afterEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("calls /api/v1/health and returns the parsed body", async () => {
    const body = { status: "ok", version: "0.1.0", environment: "test" };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));

    await expect(api.health()).resolves.toEqual(body);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/v1\/health$/);
  });

  it("throws ApiError on non-2xx responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 503 }));
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("API_URL", () => {
  it("strips a trailing /api/v1 so paths are never doubled", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://example.test/api/v1/");
    const mod = await import("@/lib/api");
    expect(mod.API_URL).toBe("http://example.test");
    vi.unstubAllEnvs();
  });
});
