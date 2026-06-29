import type {
  GradingCriterionInput,
  GradingCriterionScore,
  GradingHealth,
  GradingJob,
  GradingQueueItem,
  GradingScope,
  PrivacyAudit,
  QueueState,
  RubricMode,
  TeacherLoopMode,
} from "../../types";
import { request, API_BASE } from "./client";
import { clearApiCache } from "./cache";

/** Invalidates cache entries for a specific grading job. */
function invalidateGradingJob(jobId: string) {
  clearApiCache(`GET /api/grading/jobs/${jobId}`);
}

/** Invalidates cache entries for the grading jobs list and queue. */
function invalidateGradingList() {
  clearApiCache("GET /api/grading/jobs");
  clearApiCache("GET /api/grading/queue");
}

export const grading = {
  gradingHealth: (probe = false) =>
    request<GradingHealth>(
      `/api/grading/health${probe ? "?probe=true" : ""}`,
      undefined,
      { ttlMs: 30_000 },
    ),
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
    invalidateGradingJob(jobId);
    return response;
  },
  runPrivacyAudit: async (jobId: string) => {
    const response = await request<PrivacyAudit>(`/api/grading/jobs/${jobId}/privacy-audit`, {
      method: "POST",
    });
    invalidateGradingJob(jobId);
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
    invalidateGradingJob(jobId);
    invalidateGradingList();
    return response;
  },
  draftStreamUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/draft/stream`,
  clearGradingCache: (jobId?: string) => {
    if (jobId) invalidateGradingJob(jobId);
    invalidateGradingList();
  },
  reviewGradingSubmission: (
    jobId: string,
    submissionId: string,
    payload: {
      final_score: number;
      feedback: string;
      reviewed: boolean;
      criterion_scores?: GradingCriterionScore[];
    },
  ) =>
    request<GradingJob>(
      `/api/grading/jobs/${jobId}/submissions/${submissionId}/review`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  prepareClassroomLinks: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/classroom-links`, {
      method: "POST",
    }).then((response) => {
      invalidateGradingJob(jobId);
      return response;
    }),
  markSubmissionPosted: (jobId: string, submissionId: string, posted: boolean) =>
    request<GradingJob>(
      `/api/grading/jobs/${jobId}/submissions/${submissionId}/posted`,
      {
        method: "POST",
        body: JSON.stringify({ posted }),
      },
    ).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  retryGradingSubmission: (jobId: string, submissionId: string) =>
    request<GradingJob>(
      `/api/grading/jobs/${jobId}/submissions/${submissionId}/retry`,
      {
        method: "POST",
      },
    ).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  deleteGradingCache: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/cache`, {
      method: "DELETE",
    }).then((response) => {
      invalidateGradingJob(jobId);
      return response;
    }),
  deleteGradingJob: async (jobId: string) => {
    await request<void>(`/api/grading/jobs/${jobId}`, {
      method: "DELETE",
    });
    invalidateGradingJob(jobId);
    invalidateGradingList();
  },
  archiveGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/archive`, {
      method: "POST",
    }).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  hideGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/hide`, {
      method: "POST",
    }).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  restoreGradingJob: (jobId: string) =>
    request<GradingJob>(`/api/grading/jobs/${jobId}/restore`, {
      method: "POST",
    }).then((response) => {
      invalidateGradingJob(jobId);
      invalidateGradingList();
      return response;
    }),
  gradingCsvUrl: (jobId: string) => `${API_BASE}/api/grading/jobs/${jobId}/export.csv`,
  submissionPreviewUrl: (jobId: string, submissionId: string, fileId?: string) =>
    `${API_BASE}/api/grading/jobs/${jobId}/submissions/${submissionId}/preview` +
    (fileId ? `?file_id=${encodeURIComponent(fileId)}` : ""),
};
