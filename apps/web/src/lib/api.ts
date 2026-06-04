import type {
  Activity,
  AuthState,
  Course,
  ExportJob,
  GradingJob,
  GradingQueueItem,
  PrivacyAudit,
  RubricMode,
  TeacherLoopMode,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  authMe: () => request<AuthState>("/api/auth/me"),
  logoutGoogle: () =>
    request<AuthState>("/api/auth/google/logout", {
      method: "POST",
    }),
  connectGoogle: (scopes: string[]) =>
    request<{
      authorization_url: string | null;
      mock_connected: boolean;
      scopes: string[];
    }>("/api/auth/google/start", {
      method: "POST",
      body: JSON.stringify(scopes),
    }),
  courses: () => request<Course[]>("/api/courses"),
  activities: (courseId: string) =>
    request<Activity[]>(`/api/courses/${courseId}/activities`),
  createExport: (courseId: string, activityIds: string[]) =>
    request<ExportJob>("/api/exports", {
      method: "POST",
      body: JSON.stringify({ course_id: courseId, activity_ids: activityIds }),
    }),
  fileUrl: (jobId: string, fileId: string) =>
    `${API_BASE}/api/exports/${jobId}/files/${fileId}/content`,
  gradingQueue: () => request<GradingQueueItem[]>("/api/grading/queue"),
  createGradingJob: (payload: {
    course_id: string;
    activity_id: string;
    rubric_mode: RubricMode;
    teacher_loop: TeacherLoopMode;
    rubric_text?: string;
  }) =>
    request<GradingJob>("/api/grading/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  gradingJob: (jobId: string) => request<GradingJob>(`/api/grading/jobs/${jobId}`),
  runPrivacyAudit: (jobId: string) =>
    request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`, {
      method: "POST",
    }),
  privacyAudit: (jobId: string) =>
    request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`),
  privacyAuditCsvUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.csv`,
  privacyAuditJsonUrl: (jobId: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/privacy-audit/export.json`,
  draftGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/draft`, {
      method: "POST",
    }),
  reviewGradingSubmission: (
    jobId: string,
    submissionId: string,
    payload: { final_score: number; feedback: string; reviewed: boolean },
  ) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  retryGradingSubmission: (jobId: string, submissionId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/submissions/${submissionId}/retry`, {
      method: "POST",
    }),
  deleteGradingCache: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/cache`, {
      method: "DELETE",
    }),
  gradingCsvUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/export.csv`,
};
