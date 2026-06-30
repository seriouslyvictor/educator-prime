import { useEffect, useState } from "react";

import { ApiError, api, apiErrorFromUnknown } from "../lib/api";
import type {
  Activity,
  AppView,
  Course,
  GradingCriterionInput,
  GradingCriterionScore,
  GradingJob,
  GradingQueueItem,
  GradingScope,
  GradingSubmission,
  PrivacyAudit,
  RubricMode,
  TeacherLoopMode,
} from "../types";
import { openGradingStream } from "../lib/gradingEventSource";
import {
  applyProgressExhausted,
  applyProgressPayload,
  applyProgressReconnecting,
  gradingItemFromJob,
  mergeDraftSubmission,
  type GradingInlineProgress,
  type GradingStreamPayload,
} from "./gradingProgress";
export type { GradingInlineProgress, GradingStreamPayload } from "./gradingProgress";

// Remembering the active grading job lets a page reload drop the teacher back
// into the same job instead of an empty workspace — the job itself is already
// persisted server-side, this is just the pointer to it.
const ACTIVE_JOB_STORAGE_KEY = "cd.grading.activeJobId";

export function readStoredJobId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function writeStoredJobId(jobId: string | null): void {
  try {
    if (jobId) localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, jobId);
    else localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    /* ignore storage failures (private mode, quota) */
  }
}

export { mergeDraftSubmission, gradingItemFromJob };

function appError(caught: unknown, fallback: string): ApiError {
  return apiErrorFromUnknown(caught, fallback);
}

type UseGradingJobOptions = {
  setView: (view: AppView) => void;
  setError: (error: ApiError | string | null) => void;
  setGraderBusy: (busy: boolean) => void;
  loadGradingQueue: () => Promise<void>;
  selectedGradingItem: GradingQueueItem | null;
  setSelectedGradingItem: (item: GradingQueueItem | null) => void;
  setPendingQueue: (updater: (current: GradingQueueItem[]) => GradingQueueItem[]) => void;
  findExistingJob: (courseId: string, activityId: string) => Promise<GradingQueueItem | null>;
  gradingQueue: GradingQueueItem[];
  selectedCourse: Course | undefined;
};

export function useGradingJob({
  setView,
  setError,
  setGraderBusy,
  loadGradingQueue,
  selectedGradingItem,
  setSelectedGradingItem,
  setPendingQueue,
  findExistingJob,
  gradingQueue,
  selectedCourse,
}: UseGradingJobOptions) {
  const [gradingJob, setGradingJob] = useState<GradingJob | null>(null);
  const [privacyAudit, setPrivacyAudit] = useState<PrivacyAudit | null>(null);
  const [activeGradingSubmissionId, setActiveGradingSubmissionId] = useState<string | null>(null);
  const [draftingSubmissionId, setDraftingSubmissionId] = useState<string | null>(null);
  const [acceptingSubmissionId, setAcceptingSubmissionId] = useState<string | null>(null);
  const [gradingProgress, setGradingProgress] = useState<GradingInlineProgress | null>(null);

  // Keep the reload pointer in sync with whichever job is open.
  useEffect(() => {
    writeStoredJobId(gradingJob?.id ?? null);
  }, [gradingJob?.id]);

  function clearActiveJob() {
    setGradingJob(null);
    setPrivacyAudit(null);
    setActiveGradingSubmissionId(null);
    setSelectedGradingItem(null);
    writeStoredJobId(null);
  }

  function getActiveJobId(): string | null {
    return gradingJob?.id ?? null;
  }

  function streamGradingProgress(
    url: string,
    phase: "audit" | "criteria" | "draft",
    fallbackError: string,
    onPayload?: (payload: GradingStreamPayload) => void,
  ): Promise<GradingStreamPayload> {
    setGradingProgress({
      phase,
      processed: 0,
      total: 0,
      current: phase === "audit" ? "Preparando auditoria..." : "Preparando avaliação...",
      done: false,
      error: null,
    });

    return openGradingStream(url, fallbackError, {
      onPayload: (payload) => {
        onPayload?.(payload);
        setGradingProgress((current) => applyProgressPayload(current, payload, phase));
      },
      onReconnecting: (attempt) => {
        setGradingProgress((current) => applyProgressReconnecting(current, phase, attempt));
      },
      onExhausted: (message) => {
        setGradingProgress((current) => applyProgressExhausted(current, phase, message));
      },
    });
  }

  // Seed the review list with every submission (alphabetical, all pending) before
  // drafting starts, so the queue is fully visible instead of filling in one by one.
  function seedDraftQueue(submissions: GradingSubmission[]) {
    setGradingJob((current) =>
      current ? { ...current, submissions, total_submissions: submissions.length } : current,
    );
  }

  function applyDraftSubmission(submission: GradingSubmission) {
    setGradingJob((current) => {
      if (!current) return current;
      const submissions = mergeDraftSubmission(current.submissions, submission);
      return {
        ...current,
        submissions,
        reviewed_submissions: submissions.filter((row) => row.reviewed).length,
        flagged_submissions: submissions.filter((row) => row.flag || row.error || row.ai_attempt_status === "blocked").length,
      };
    });
  }

  async function runCriteriaStream(job: GradingJob) {
    if (job.rubric_mode !== "infer") return job;
    const streamed = await streamGradingProgress(
      api.criteriaStreamUrl(job.id),
      "criteria",
      "Falha ao inferir critérios da rubrica.",
      (payload) => {
        if (payload.job) setGradingJob(payload.job);
      },
    );
    if (!streamed.job) throw new Error("A inferência terminou sem resultado.");
    setGradingJob(streamed.job);
    setSelectedGradingItem(gradingItemFromJob(streamed.job));
    return streamed.job;
  }

  // Reuse a not-yet-prepared job only when it matches the current selection;
  // otherwise the teacher's mode/rubric change would be silently dropped.
  function matchingReadyJob(
    item: GradingQueueItem,
    payload: { rubricMode: RubricMode; teacherLoop: TeacherLoopMode; rubricText: string; includeVisualSubmissions: boolean; scope?: GradingScope },
  ): GradingJob | null {
    const reusable =
      gradingJob?.activity_id === item.activity_id &&
      gradingJob.status === "ready" &&
      gradingJob.rubric_mode === payload.rubricMode &&
      gradingJob.teacher_loop === payload.teacherLoop &&
      (gradingJob.rubric_text ?? "") === (payload.rubricText ?? "") &&
      gradingJob.include_visual_submissions === payload.includeVisualSubmissions &&
      gradingJob.grade_scope === (payload.scope ?? "all");
    return reusable ? gradingJob : null;
  }

  // Open the Setup screen for a ready item: create the job, then auto-infer the rubric
  // (streamed) before any audit. Shared by Turmas and the grader queue.
  async function beginGradingSetup(item: GradingQueueItem) {
    setGraderBusy(true);
    setError(null);
    setPrivacyAudit(null);
    setSelectedGradingItem(item);
    setView("graderSetup");
    try {
      setGradingJob(null);
    } catch (caught) {
      setError(appError(caught, "Falha ao preparar a correção."));
    } finally {
      setGraderBusy(false);
    }
  }

  async function gradeActivity(activity: Activity) {
    if (!selectedCourse) return;
    // Resume an existing job for this activity rather than always creating a new one.
    const known = gradingQueue.find(
      (item) => item.activity_id === activity.id && item.latest_job_id,
    );
    const existing = known ?? (await findExistingJob(selectedCourse.id, activity.id));
    if (existing?.latest_job_id) {
      void openGradingJob(existing.latest_job_id);
      return;
    }
    const item: GradingQueueItem = {
      course_id: selectedCourse.id,
      course_name: selectedCourse.name,
      activity_id: activity.id,
      activity_title: activity.title,
      due_label: activity.due_label,
      submission_count: 0,
      status: "ready",
      latest_job_id: null,
      queue_state: "active",
      reviewed_submissions: 0,
      total_submissions: activity.total_submissions,
      graded_submissions: activity.graded_submissions,
      ungraded_submissions: activity.ungraded_submissions,
      concluded: activity.concluded,
    };
    await beginGradingSetup(item);
  }

  async function regradeActivity(activity: Activity) {
    if (!selectedCourse) return;
    const known = gradingQueue.find(
      (item) => item.activity_id === activity.id && item.latest_job_id,
    );
    const existing = known ?? (await findExistingJob(selectedCourse.id, activity.id));
    setPrivacyAudit(null);
    setGradingJob(null);
    setSelectedGradingItem({
      course_id: selectedCourse.id,
      course_name: selectedCourse.name,
      activity_id: activity.id,
      activity_title: activity.title,
      due_label: activity.due_label,
      submission_count: existing?.submission_count ?? 0,
      status: existing?.status ?? "ready",
      latest_job_id: existing?.latest_job_id ?? null,
      queue_state: existing?.queue_state ?? "active",
      reviewed_submissions: existing?.reviewed_submissions ?? 0,
      total_submissions: existing?.total_submissions ?? activity.total_submissions,
      graded_submissions: activity.graded_submissions,
      ungraded_submissions: activity.ungraded_submissions,
      concluded: activity.concluded,
    });
    setView("graderSetup");
  }

  // Quietly restore a job on reload. Unlike openGradingJob this never re-runs a
  // privacy audit and never surfaces an error banner — a stale/deleted pointer just
  // falls back to the workspace.
  async function restoreGradingJob(jobId: string): Promise<boolean> {
    try {
      const nextJob = await api.gradingJob(jobId);
      setGradingJob(nextJob);
      setActiveGradingSubmissionId(nextJob.submissions[0]?.id ?? null);
      if (nextJob.status === "ready") {
        writeStoredJobId(null);
        return false;
      }
      setView(nextJob.status === "completed" ? "graderWrap" : "graderReview");
      return true;
    } catch {
      writeStoredJobId(null);
      return false;
    }
  }

  async function openGradingJob(jobId: string) {
    setGraderBusy(true);
    setError(null);
    try {
      const nextJob = await api.gradingJob(jobId);
      setGradingJob(nextJob);
      setActiveGradingSubmissionId(nextJob.submissions[0]?.id ?? null);
      if (nextJob.status === "ready") {
        try {
          const audit = await api.privacyAudit(nextJob.id);
          setPrivacyAudit(audit);
        } catch {
          setPrivacyAudit(null);
          await runCriteriaStream(nextJob);
        }
        setSelectedGradingItem(gradingItemFromJob(nextJob));
        setView("graderSetup");
        return;
      }
      setView(nextJob.status === "completed" ? "graderWrap" : "graderReview");
    } catch (caught) {
      setError(appError(caught, "Falha ao abrir a correção."));
    } finally {
      setGraderBusy(false);
    }
  }

  // Step 1 of infer mode: produce the inferred rubric and pause on the setup
  // screen so the teacher can edit it before the audit runs.
  async function inferGradingCriteria(
    item: GradingQueueItem,
    payload: { rubricMode: RubricMode; teacherLoop: TeacherLoopMode; rubricText: string; includeVisualSubmissions: boolean; scope?: GradingScope },
  ) {
    setGraderBusy(true);
    setError(null);
    setPrivacyAudit(null);
    setSelectedGradingItem(item);
    setView("graderSetup");
    setGradingProgress({
      phase: "criteria",
      processed: 0,
      total: item.submission_count,
      current: "Criando rodada de correção...",
      done: false,
      error: null,
    });
    try {
      let target = matchingReadyJob(item, payload);
      if (!target) {
        target = await api.createGradingJob({
          course_id: item.course_id,
          activity_id: item.activity_id,
          rubric_mode: payload.rubricMode,
          teacher_loop: payload.teacherLoop,
          scope: payload.scope ?? "all",
          rubric_text: payload.rubricText,
          include_visual_submissions: payload.includeVisualSubmissions,
        });
        setGradingJob(target);
        setSelectedGradingItem(gradingItemFromJob(target));
        setPendingQueue((current) => current.filter((row) => row.activity_id !== item.activity_id));
      }
      await runCriteriaStream(target);
      setGradingProgress(null);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Falha ao inferir critérios da rubrica.";
      setError(message);
      setGradingProgress((current) => ({
        phase: "criteria",
        processed: current?.processed ?? 0,
        total: current?.total ?? item.submission_count,
        current: current?.current ?? "",
        done: true,
        error: message,
      }));
    } finally {
      setGraderBusy(false);
    }
  }

  async function startGradingAuditForItem(
    item: GradingQueueItem,
    payload: {
      rubricMode: RubricMode;
      teacherLoop: TeacherLoopMode;
      rubricText: string;
      includeVisualSubmissions: boolean;
      scope?: GradingScope;
      criteria?: GradingCriterionInput[];
    },
  ) {
    setGraderBusy(true);
    setError(null);
    setPrivacyAudit(null);
    setSelectedGradingItem(item);
    setView("graderSetup");
    setGradingProgress({
      phase: "audit",
      processed: 0,
      total: item.submission_count,
      current: "Criando rodada de correção...",
      done: false,
      error: null,
    });
    try {
      let target = matchingReadyJob(item, payload);
      if (!target) {
        target = await api.createGradingJob({
          course_id: item.course_id,
          activity_id: item.activity_id,
          rubric_mode: payload.rubricMode,
          teacher_loop: payload.teacherLoop,
          scope: payload.scope ?? "all",
          rubric_text: payload.rubricText,
          include_visual_submissions: payload.includeVisualSubmissions,
          criteria: payload.criteria,
        });
        setGradingJob(target);
        setSelectedGradingItem(gradingItemFromJob(target));
        setPendingQueue((current) => current.filter((row) => row.activity_id !== item.activity_id));
      }
      if (target.rubric_mode === "infer") {
        if (payload.criteria && payload.criteria.length > 0) {
          // Teacher already reviewed/edited the inferred rubric — persist it and
          // skip re-inference (which would overwrite their edits).
          target = await api.updateGradingCriteria(target.id, payload.criteria);
          setGradingJob(target);
          setSelectedGradingItem(gradingItemFromJob(target));
        } else {
          target = await runCriteriaStream(target);
        }
      }
      const streamed = await streamGradingProgress(
        api.privacyAuditStreamUrl(target.id),
        "audit",
        "Falha ao executar a auditoria de privacidade.",
      );
      if (!streamed.summary) throw new Error("A auditoria terminou sem resumo.");
      setPrivacyAudit(streamed.summary);
      api.clearGradingCache(target.id);
      void loadGradingQueue();
      setGradingProgress(null);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Falha ao executar a auditoria de privacidade.";
      setError(message);
      setGradingProgress((current) => ({
        phase: "audit",
        processed: current?.processed ?? 0,
        total: current?.total ?? item.submission_count,
        current: current?.current ?? "",
        done: true,
        error: message,
      }));
    } finally {
      setGraderBusy(false);
    }
  }

  async function runGradingPrivacyAudit(payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
    includeVisualSubmissions: boolean;
    criteria?: GradingCriterionInput[];
  }) {
    if (!selectedGradingItem) return;
    await startGradingAuditForItem(selectedGradingItem, payload);
  }

  async function runInferGradingCriteria(payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
    includeVisualSubmissions: boolean;
  }) {
    if (!selectedGradingItem) return;
    await inferGradingCriteria(selectedGradingItem, payload);
  }

  async function rerunGradingPrivacyAudit() {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      const streamed = await streamGradingProgress(
        api.privacyAuditStreamUrl(gradingJob.id),
        "audit",
        "Falha ao executar a auditoria de privacidade.",
      );
      if (!streamed.summary) throw new Error("A auditoria terminou sem resumo.");
      setPrivacyAudit(streamed.summary);
      api.clearGradingCache(gradingJob.id);
      setGradingProgress(null);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Falha ao executar a auditoria de privacidade.";
      setError(message);
    } finally {
      setGraderBusy(false);
    }
  }

  async function continueToGradingDraft() {
    if (!gradingJob) return;
    setError(null);
    setDraftingSubmissionId(null);
    try {
      setView("graderReview");
      const streamed = await streamGradingProgress(
        api.draftStreamUrl(gradingJob.id),
        "draft",
        "Falha ao gerar rascunhos de notas.",
        (payload) => {
          // Seed the whole queue up front so every student shows as "na fila".
          if (payload.queued) {
            seedDraftQueue(payload.queued);
            setActiveGradingSubmissionId((current) => current ?? payload.queued?.[0]?.id ?? null);
          }
          if (payload.drafting_id) {
            setDraftingSubmissionId(payload.drafting_id);
          }
          if (payload.submission) {
            applyDraftSubmission(payload.submission);
            setActiveGradingSubmissionId((current) => current ?? payload.submission?.id ?? null);
          }
          if (payload.job) setGradingJob(payload.job);
        },
      );
      if (!streamed.job) throw new Error("A avaliação terminou sem resultado.");
      const drafted = streamed.job;
      setGradingJob(drafted);
      setActiveGradingSubmissionId((current) => current ?? drafted.submissions[0]?.id ?? null);
      api.clearGradingCache(drafted.id);
      setGradingProgress(null);
      setDraftingSubmissionId(null);
      void loadGradingQueue();
    } catch (caught) {
      setError(appError(caught, "Falha ao gerar rascunhos de notas."));
    } finally {
      setDraftingSubmissionId(null);
    }
  }

  async function acceptGradingDraft(
    submission: GradingSubmission,
    score: number,
    feedback: string,
    criterionScores?: GradingCriterionScore[],
  ) {
    if (!gradingJob) return;
    setAcceptingSubmissionId(submission.id);
    setError(null);
    try {
      const updated = await api.reviewGradingSubmission(gradingJob.id, submission.id, {
        final_score: score,
        feedback,
        reviewed: true,
        ...(criterionScores && criterionScores.length > 0 ? { criterion_scores: criterionScores } : {}),
      });
      setGradingJob(updated);
      const index = updated.submissions.findIndex((row) => row.id === submission.id);
      const next =
        updated.submissions.slice(index + 1).find((row) => !row.reviewed) ??
        updated.submissions.find((row) => !row.reviewed) ??
        updated.submissions[index] ??
        updated.submissions[0];
      setActiveGradingSubmissionId(next?.id ?? null);
      void loadGradingQueue();
      if (updated.reviewed_submissions === updated.total_submissions && updated.total_submissions > 0) {
        setView("graderWrap");
      }
    } catch (caught) {
      setError(appError(caught, "Falha ao salvar a revisão."));
    } finally {
      setAcceptingSubmissionId(null);
    }
  }

  async function retryGradingDraft(submission: GradingSubmission) {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      const updated = await api.retryGradingSubmission(gradingJob.id, submission.id);
      setGradingJob(updated);
      setActiveGradingSubmissionId(submission.id);
    } catch (caught) {
      setError(appError(caught, "Falha ao corrigir a entrega novamente."));
    } finally {
      setGraderBusy(false);
    }
  }

  async function deleteGradingCache() {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      setGradingJob(await api.deleteGradingCache(gradingJob.id));
    } catch (caught) {
      setError(appError(caught, "Falha ao apagar arquivos em cache."));
    } finally {
      setGraderBusy(false);
    }
  }

  return {
    gradingJob,
    setGradingJob,
    privacyAudit,
    activeGradingSubmissionId,
    setActiveGradingSubmissionId,
    draftingSubmissionId,
    acceptingSubmissionId,
    gradingProgress,
    clearActiveJob,
    getActiveJobId,
    restoreGradingJob,
    gradeActivity,
    regradeActivity,
    beginGradingSetup,
    openGradingJob,
    runGradingPrivacyAudit,
    runInferGradingCriteria,
    rerunGradingPrivacyAudit,
    continueToGradingDraft,
    acceptGradingDraft,
    retryGradingDraft,
    deleteGradingCache,
  };
}
