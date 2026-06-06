import type {
  Activity,
  AuthState,
  Course,
  ExportJob,
  GradingHealth,
  GradingJob,
  GradingCriterionInput,
  GradingQueueItem,
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
      void request<T>(path, init, { ...options, force: true }).catch(() => undefined);
    }
    return cached.value as T;
  }
  if (key && inFlight.has(key)) {
    return inFlight.get(key) as Promise<T>;
  }

  const fetchPromise = fetchJson<T>(path, init)
    .then((value) => {
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
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => undefined);
    throw new Error(detail?.detail ?? `Requisição falhou com ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
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
  gradingJobs: () =>
    request<GradingQueueItem[]>("/api/grading/jobs", undefined, { ttlMs: 15_000 }),
  createGradingJob: async (payload: {
    course_id: string;
    activity_id: string;
    rubric_mode: RubricMode;
    teacher_loop: TeacherLoopMode;
    rubric_text?: string;
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
  draftGradingJob: async (jobId: string) => {
    const response = await request<GradingJob>(`/api/grading/jobs/${jobId}/draft`, {
      method: "POST",
    });
    clearApiCache(`GET /api/grading/jobs/${jobId}`);
    clearApiCache("GET /api/grading/jobs");
    clearApiCache("GET /api/grading/queue");
    return response;
  },
  reviewGradingSubmission: (
    jobId: string,
    submissionId: string,
    payload: { final_score: number; feedback: string; reviewed: boolean },
  ) => request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }).then((response) => {
      clearApiCache(`GET /api/grading/jobs/${jobId}`);
      clearApiCache("GET /api/grading/jobs");
      clearApiCache("GET /api/grading/queue");
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
  gradingCsvUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/export.csv`,
  submissionPreviewUrl: (jobId: string, submissionId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/submissions/${submissionId}/preview`,
};
