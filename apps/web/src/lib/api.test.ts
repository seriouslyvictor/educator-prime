import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let mod: typeof import("./api");

function jsonResponse(
  body: unknown,
  init: { status?: number; headers?: Record<string, string> } = {},
): Response {
  const status = init.status ?? 200;
  return {
    ok: status < 400,
    status,
    headers: { get: (key: string) => init.headers?.[key] ?? null },
    json: async () => body,
  } as unknown as Response;
}

beforeEach(async () => {
  vi.resetModules();
  mod = await import("./api");
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiErrorFromUnknown", () => {
  it("returns ApiError instances unchanged", () => {
    const error = new mod.ApiError(409, "conflict", "Already exists");

    expect(mod.apiErrorFromUnknown(error, "fallback")).toBe(error);
  });

  it("wraps Error instances with status 0", () => {
    const error = mod.apiErrorFromUnknown(new Error("Network down"), "fallback");

    expect(error).toBeInstanceOf(mod.ApiError);
    expect(error.status).toBe(0);
    expect(error.code).toBeUndefined();
    expect(error.message).toBe("Network down");
  });

  it("uses the fallback for non-Error values", () => {
    const error = mod.apiErrorFromUnknown("bad", "Fallback message");

    expect(error.status).toBe(0);
    expect(error.code).toBeUndefined();
    expect(error.message).toBe("Fallback message");
  });
});

describe("subscriptions", () => {
  it("notifies connectivity listeners immediately and on failure", async () => {
    const listener = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const unsubscribe = mod.subscribeConnectivity(listener);
    await expect(mod.api.courses()).rejects.toMatchObject({
      status: 0,
      code: "unreachable",
    });

    expect(listener).toHaveBeenNthCalledWith(1, false);
    expect(listener).toHaveBeenNthCalledWith(2, true);

    unsubscribe();
  });

  it("stops notifying connectivity listeners after unsubscribe", async () => {
    const listener = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const unsubscribe = mod.subscribeConnectivity(listener);
    unsubscribe();
    await expect(mod.api.courses()).rejects.toBeInstanceOf(mod.ApiError);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(false);
  });

  it("notifies version skew listeners immediately", () => {
    const listener = vi.fn();

    const unsubscribe = mod.subscribeVersionSkew(listener);

    expect(listener).toHaveBeenCalledOnce();
    expect(listener).toHaveBeenCalledWith(false);
    unsubscribe();
  });
});

describe("cache behavior", () => {
  it("serves fresh GET responses from cache", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse([{ id: "course-1" }]));
    vi.stubGlobal("fetch", fetch);

    const first = await mod.api.courses();
    const second = await mod.api.courses();

    expect(first).toEqual([{ id: "course-1" }]);
    expect(second).toBe(first);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("deduplicates concurrent GET requests", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse([{ id: "course-1" }]));
    vi.stubGlobal("fetch", fetch);

    const first = mod.api.courses();
    const second = mod.api.courses();

    await expect(Promise.all([first, second])).resolves.toEqual([
      [{ id: "course-1" }],
      [{ id: "course-1" }],
    ]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("returns stale cached data and starts background revalidation", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-13T00:00:00Z"));
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([{ id: "first" }]))
      .mockResolvedValueOnce(jsonResponse([{ id: "second" }]));
    vi.stubGlobal("fetch", fetch);

    const first = await mod.api.courses();
    vi.setSystemTime(new Date("2026-06-13T00:02:01Z"));
    const stale = await mod.api.courses();

    expect(stale).toBe(first);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe("Google auth start", () => {
  it("posts capability and reason instead of raw scopes", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse({
      authorization_url: "https://accounts.google.com",
      mock_connected: false,
      scopes: ["openid"],
    }));
    vi.stubGlobal("fetch", fetch);

    await mod.api.connectGoogle("identity", "Entrar no app.");

    expect(fetch).toHaveBeenCalledWith("/api/auth/google/start", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ capability: "identity", reason: "Entrar no app." }),
    }));
  });
});

describe("fetchJson error mapping", () => {
  it("maps thrown fetch errors to unreachable ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network failed")));

    await expect(mod.api.courses()).rejects.toMatchObject({
      status: 0,
      code: "unreachable",
      message: "network failed",
    });
  });

  it("maps object detail errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: { code: "x", message: "m" } }, { status: 404 })),
    );

    await expect(mod.api.courses()).rejects.toMatchObject({
      status: 404,
      code: "x",
      message: "m",
    });
  });

  it("maps string detail errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "plain string" }, { status: 500 })),
    );

    await expect(mod.api.courses()).rejects.toMatchObject({
      status: 500,
      code: undefined,
      message: "plain string",
    });
  });

  it("resolves 204 responses to undefined", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(undefined, { status: 204 })));

    await expect(mod.api.deleteGradingJob("job-1")).resolves.toBeUndefined();
  });
});
