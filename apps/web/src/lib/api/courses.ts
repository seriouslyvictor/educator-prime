import type { Activity, Course, ExportJob } from "../../types";
import { request, API_BASE } from "./client";
import { clearApiCache } from "./cache";

export const courses = {
  courses: () => request<Course[]>("/api/courses", undefined, { ttlMs: 120_000 }),
  activities: (courseId: string) =>
    request<Activity[]>(`/api/courses/${courseId}/activities`, undefined, {
      ttlMs: 120_000,
    }),
  activityGradeSummaries: (courseId: string) =>
    request<
      {
        activity_id: string;
        total_submissions: number;
        graded_submissions: number;
        ungraded_submissions: number;
        concluded: boolean;
      }[]
    >(`/api/courses/${courseId}/activities/grade-summary`, undefined, { ttlMs: 30_000 }),
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
};
