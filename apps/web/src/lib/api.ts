import type { Activity, AuthState, Course, ExportJob } from "../types";

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
    throw new Error(detail?.detail ?? `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  authMe: () => request<AuthState>("/api/auth/me"),
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
};
