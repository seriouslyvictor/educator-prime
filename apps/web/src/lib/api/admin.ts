import type {
  AdminStats,
  AiAttemptItem,
  AiAttemptPayload,
  AppEventItem,
} from "../../types";
import { request, queryString } from "./client";

export const admin = {
  adminListEvents: (
    params: {
      level?: string;
      event_prefix?: string;
      user_email?: string;
      q?: string;
      before?: string;
      limit?: number;
    } = {},
  ) =>
    request<AppEventItem[]>(`/api/admin/events${queryString(params)}`, undefined, {
      ttlMs: 5_000,
    }),
  adminListAttempts: (
    params: {
      job_id?: string;
      status?: string;
      stage?: string;
      retryable?: boolean;
      model?: string;
      before?: string;
      limit?: number;
    } = {},
  ) =>
    request<AiAttemptItem[]>(`/api/admin/llm/attempts${queryString(params)}`, undefined, {
      ttlMs: 5_000,
    }),
  adminGetAttemptPayload: (id: string) =>
    request<AiAttemptPayload>(
      `/api/admin/llm/attempts/${encodeURIComponent(id)}/payload`,
      undefined,
      { ttlMs: 5_000 },
    ),
  adminGetStats: () => request<AdminStats>("/api/admin/stats", undefined, { ttlMs: 5_000 }),
};
