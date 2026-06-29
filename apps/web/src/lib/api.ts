import type {
  Activity,
  AdminStats,
  AiAttemptItem,
  AiAttemptPayload,
  AppEventItem,
  AuthState,
  Course,
  ExportJob,
  GradingHealth,
  GradingJob,
  GradingCriterionInput,
  GradingCriterionScore,
  GradingScope,
  GradingQueueItem,
  QueueState,
  PrivacyAudit,
  RubricMode,
  TeacherLoopMode,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type CacheOptions = {
  cacheKey?: string;
  ttlMs?: number;
  staleMs?: number;
  force?: boolean;
};

type CacheEntry<T> = {
  value: T;
  freshUntil: number;
  staleUntil: number;
};

const responseCache = new Map<string, CacheEntry<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();
const connectivityListeners = new Set<(offline: boolean) => void>();
const versionSkewListeners = new Set<(skewed: boolean) => void>();
let revalidationFailures = 0;
let offline = false;
let versionSkewNotified = false;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiErrorFromUnknown(caught: unknown, fallback: string): ApiError {
  if (caught instanceof ApiError) return caught;
  if (caught instanceof Error) return new ApiError(0, undefined, caught.message || fallback);
  return new ApiError(0, undefined, fallback);
}

export function subscribeConnectivity(listener: (offline: boolean) => void): () => void {
  connectivityListeners.add(listener);
  listener(offline);
  return () => connectivityListeners.delete(listener);
}

export function subscribeVersionSkew(listener: (skewed: boolean) => void): () => void {
  versionSkewListeners.add(listener);
  listener(versionSkewNotified);
  return () => versionSkewListeners.delete(listener);
}

function setOffline(nextOffline: boolean) {
  if (offline === nextOffline) return;
  offline = nextOffline;
  for (const listener of connectivityListeners) listener(offline);
}

function markConnectivitySuccess() {
  revalidationFailures = 0;
  setOffline(false);
}

function markConnectivityFailure() {
  revalidationFailures += 1;
  if (revalidationFailures >= 1) setOffline(true);
}

function checkAppVersion(response: Response) {
  const serverVersion = response.headers.get("X-App-Version");
  if (!serverVersion || serverVersion === __APP_VERSION__ || versionSkewNotified) return;
  versionSkewNotified = true;
  for (const listener of versionSkewListeners) listener(true);
}

function cacheKey(path: string) {
  return `GET ${path}`;
}

function clearApiCache(prefix?: string) {
  for (const key of responseCache.keys()) {
    if (!prefix || key.startsWith(prefix)) responseCache.delete(key);
  }
  for (const key of inFlight.keys()) {
    if (!prefix || key.startsWith(prefix)) inFlight.delete(key);
  }
}

function queryString(params: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

async function request<T>(
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

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
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

export const api = {
  adminListEvents: (params: {
    level?: string;
    event_prefix?: string;
    user_email?: string;
    q?: string;
    before?: string;
    limit?: number;
  } = {}) =>
    request<AppEventItem[]>(`/api/admin/events${queryString(params)}`, undefined, {
      ttlMs: 5_000,
    }),
  adminListAttempts: (params: {
    job_id?: string;
    status?: string;
    stage?: string;
    retryable?: boolean;
    model?: string;
    before?: string;
    limit?: number;
  } = {}) =>
    request<AiAttemptItem[]>(`/api/admin/llm/attempts${queryString(params)}`, undefined, {
      ttlMs: 5_000,
    }),
  adminGetAttemptPayload: (id: string) =>
    request<AiAttemptPayload>(`/api/admin/llm/attempts/${encodeURIComponent(id)}/payload`, undefined, {
      ttlMs: 5_000,
    }),
  adminGetStats: () => request<AdminStats>("/api/admin/stats", undefined, { ttlMs: 5_000 }),
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
  gradingHealth: (probe = false) =>
    request<GradingHealth>(
      `/api/grading/health${probe ? "?probe=true" : ""}`,
      undefined,
      { ttlMs: 30_000 },
    ),
  courses: () => request<Course[]>("/api/courses", undefined, { ttlMs: 120_000 }),
  activities: (courseId: string) =>
    request<Activity[]>(`/api/courses/${courseId}/activities`, undefined, {
      ttlMs: 120_000,
    }),
  activityGradeSummaries: (courseId: string) =>
    request<{
      activity_id: string;
      total_submissions: number;
      graded_submissions: number;
      ungraded_submissions: number;
      concluded: boolean;
    }[]>(`/api/courses/${courseId}/activities/grade-summary`, undefined, { ttlMs: 30_000 }),
  createExport: async (courseId: string, activityIds: string[]) => {
    const response = await request<ExportJob>("/api/exports", {
      method: "POST",
      body: JSON.stringify({ course_id: courseId, activity_ids: activityIds }),
    });
    clearApiCache("GET /api/exports");
    return response;
  },
  fileUrl: (jobId: string, fileId: string) =>
    `${API_BASE}/api/exports/${jobId}/files/${fileId}/content`,
  gradingQueue: (courseId: string, activityId: string) =>
    request<GradingQueueItem[]>(
      `/api/grading/queue?course_id=${encodeURIComponent(courseId)}&activity_id=${encodeURIComponent(activityId)}`,
      undefined,
      { ttlMs: 30_000 },
    ),
  gradingJobs: (state: QueueState | "all" = "active") =>
    request<GradingQueueItem[]>(
      `/api/grading/jobs?state=${encodeURIComponent(state)}`,
      undefined,
      { ttlMs: 15_000 },
    ),
  createGradingJob: async (payload: {
    course_id: string;
    activity_id: string;
    rubric_mode: RubricMode;
    teacher_loop: TeacherLoopMode;
    scope?: GradingScope;
    rubric_text?: string;
    include_visual_submissions?: boolean;
    criteria?: GradingCriterionInput[];
  }) => {
    const response = await request<GradingJob>("/api/grading/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    clearApiCache("GET /api/grading");
    return response;
  },
  gradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}`, undefined, { ttlMs: 15_000 }),
  updateGradingCriteria: async (jobId: string, criteria: GradingCriterionInput[]) => {
    const response = await request<GradingJob>(`/api/grading/jobs/${jobId}/criteria`, {
      method: "PATCH",
      body: JSON.stringify({ criteria }),
    });
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    return response;
  },
  runPrivacyAudit: async (jobId: string) => {
    const response = await request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`, {
      method: "POST",
    });
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    return response;
  },
  privacyAudit: (jobId: string) =>
    request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`, undefined, {
      ttlMs: 15_000,
    }),
  privacyAuditCsvUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.csv`,
  privacyAuditJsonUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.json`,
  privacyAuditStreamUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/stream`,
  criteriaStreamUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/criteria/stream`,
  draftGradingJob: async (jobId: string) => {
    const response = await request<GradingJob>(`/api/grading/jobs/${jobId}/draft`, {
      method: "POST",
    });
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    clearApiCache("GET /api/grading/jobs");
    clearApiCache("GET /api/grading/queue");
    return response;
  },
  draftStreamUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/draft/stream`,
  clearGradingCache: (jobId?: string) => {
    if (jobId) clearApiCache(`GET /api/grading/jobs/${jobId}`);
    clearApiCache("GET /api/grading/jobs");
    clearApiCache("GET /api/grading/queue");
  },
  reviewGradingSubmission: (
    jobId: string,
    submissionId: string,
    payload: { final_score: number; feedback: string; reviewed: boolean; criterion_scores?: GradingCriterionScore[] },
  ) => request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      clearApiCache("GET /api/grading/queue");
      return response;
    }),
  prepareClassroomLinks: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/classroom-links`, {
      method: "POST",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      return response;
    }),
  markSubmissionPosted: (jobId: string, submissionId: string, posted: boolean) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/posted`, {
      method: "POST",
      body: JSON.stringify({ posted }),
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      return response;
    }),
  retryGradingSubmission: (jobId: string, submissionId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/retry`, {
      method: "POST",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      return response;
    }),
  deleteGradingCache: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/cache`, {
      method: "DELETE",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      return response;
    }),
  deleteGradingJob: async (jobId: string) => {
    await request<void>(`/api/grading/jobs/${jobId}`, {
      method: "DELETE",
    });
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    clearApiCache("GET /api/grading/jobs");
    clearApiCache("GET /api/grading/queue");
  },
  archiveGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/archive`, {
      method: "POST",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      clearApiCache("GET /api/grading/queue");
      return response;
    }),
  hideGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/hide`, {
      method: "POST",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      clearApiCache("GET /api/grading/queue");
      return response;
    }),
  restoreGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/restore`, {
      method: "POST",
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      clearApiCache("GET /api/grading/queue");
      return response;
    }),
  gradingCsvUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/export.csv`,
  submissionPreviewUrl: (jobId: string, submissionId: string, fileId?: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/submissions/${submissionId}/preview` +
    (fileId ? `?file_id=${encodeURIComponent(fileId)}` : ""),
};
