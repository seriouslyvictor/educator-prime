import type { CacheOptions } from "./types";
import { ApiError } from "./types";
import {
  responseCache,
  inFlight,
  markConnectivitySuccess,
  markConnectivityFailure,
  checkAppVersion,
  cacheKey,
} from "./cache";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function queryString(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

export async function request<T>(
  path: string,
  init?: RequestInit,
  options: CacheOptions = {},
): Promise<T> {
  const method = init?.method ?? "GET";
  const key = options.cacheKey ?? (method === "GET" ? cacheKey(path) : undefined);
  const now = Date.now();
  const cached = key ? responseCache.get(key) : undefined;
  if (!options.force && cached && now < cached.freshUntil) {
    return cached.value as T;
  }
  if (!options.force && cached && now < cached.staleUntil) {
    if (key && !inFlight.has(key)) {
      void request<T>(path, init, { ...options, force: true }).catch((error) => {
        if (error instanceof ApiError && error.code === "unreachable") {
          markConnectivityFailure();
        }
      });
    }
    return cached.value as T;
  }
  if (key && inFlight.has(key)) {
    return inFlight.get(key) as Promise<T>;
  }

  const fetchPromise = fetchJson<T>(path, init)
    .then((value) => {
      markConnectivitySuccess();
      if (key) {
        const ttlMs = options.ttlMs ?? 30_000;
        const staleMs = options.staleMs ?? ttlMs * 4;
        responseCache.set(key, {
          value,
          freshUntil: Date.now() + ttlMs,
          staleUntil: Date.now() + ttlMs + staleMs,
        });
      }
      return value;
    })
    .finally(() => {
      if (key) inFlight.delete(key);
    });
  if (key) inFlight.set(key, fetchPromise);
  return fetchPromise;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
      ...init,
    });
  } catch (error) {
    markConnectivityFailure();
    throw new ApiError(
      0,
      "unreachable",
      error instanceof Error ? error.message : "The API could not be reached.",
    );
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => undefined);
    const payload = detail?.detail;
    if (payload && typeof payload === "object") {
      throw new ApiError(
        response.status,
        typeof payload.code === "string" ? payload.code : undefined,
        typeof payload.message === "string" ? payload.message : `Request failed with ${response.status}`,
      );
    }
    throw new ApiError(
      response.status,
      undefined,
      typeof payload === "string" ? payload : `Request failed with ${response.status}`,
    );
  }

  checkAppVersion(response);

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
