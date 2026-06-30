import type { AuthState } from "../../types";
import { request } from "./client";
import { clearApiCache } from "./cache";

export const auth = {
  authMe: () => request<AuthState>("/api/auth/me", undefined, { ttlMs: 15_000 }),
  logoutGoogle: async () => {
    const response = await request<AuthState>("/api/auth/google/logout", {
      method: "POST",
    });
    clearApiCache();
    return response;
  },
  connectGoogle: (scopes: string[]) =>
    request<{
      authorization_url: string | null;
      mock_connected: boolean;
      scopes: string[];
    }>("/api/auth/google/start", {
      method: "POST",
      body: JSON.stringify(scopes),
    }),
};
