import { useEffect, useMemo, useState } from "react";
import { ConnectView } from "./components/ConnectView";
import { AdminView } from "./components/admin/AdminView";
import { DoneView } from "./components/DoneView";
import { DryRunDrawer } from "./components/DryRunDrawer";
import {
  GraderQueue,
  GraderReview,
  GraderSetup,
  GraderWrap,
} from "./components/grader";
import { HistoryView } from "./components/HistoryView";
import { ProgressView } from "./components/ProgressView";
import { Rail } from "./components/Rail";
import { TurmasView } from "./components/workspace";
import {
  ApiError,
  api,
  apiErrorFromUnknown,
} from "./lib/api";
import { resolveError } from "./lib/errorCatalog";
import appStyles from "./components/App.module.css";
void appStyles;
import { useLocalExportHistory } from "./lib/local-history";
import { useThemePreference } from "./lib/theme";
import { useConnection } from "./hooks/useConnection";
import { useExportWorkspace } from "./hooks/useExportWorkspace";
import { useGradingQueue } from "./hooks/useGradingQueue";
import { AppIcon } from "./components/icons";
import { InlineError } from "./components/ui";
import { Gate, OfflinePill } from "./components/errors";
import type {
  Activity,
  AppView,
  GradingHealth,
  GradingCriterionInput,
  GradingJob,
  GradingQueueItem,
  GradingSubmission,
  PrivacyAudit,
  QueueAction,
  RubricMode,
  TeacherLoopMode,
} from "./types";

// Remembering the active grading job lets a page reload drop the teacher back into
// the same job instead of an empty workspace — the job itself is already persisted
// server-side, this is just the pointer to it.
const ACTIVE_JOB_STORAGE_KEY = "cd.grading.activeJobId";

function appError(caught: unknown, fallback: string): ApiError {
  return apiErrorFromUnknown(caught, fallback);
}

function appErrorSummary(error: unknown): string {
  const entry = resolveError(error);
  return `${entry.title}: ${entry.body}`;
}

type GradingStreamPayload = {
  phase?: "audit" | "criteria" | "draft";
  processed?: number;
  total?: number;
  current?: string;
  done?: boolean;
  error?: string;
  summary?: PrivacyAudit;
  job?: GradingJob;
  submission?: GradingSubmission;
  queued?: GradingSubmission[];
  drafting_id?: string;
};

type GradingInlineProgress = {
  phase: "audit" | "criteria" | "draft";
  processed: number;
  total: number;
  current: string;
  done: boolean;
  error: string | null;
};

function readStoredJobId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredJobId(jobId: string | null): void {
  try {
    if (jobId) localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, jobId);
    else localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
  } catch {
    /* ignore storage failures (private mode, quota) */
  }
}

// Build the lightweight queue item the Setup screen needs from a full job — used
// when resuming a not-yet-drafted ("ready") job back into the Setup/prepare screen.
function gradingItemFromJob(job: GradingJob): GradingQueueItem {
  return {
    course_id: job.course_id,
    course_name: job.course_name,
    activity_id: job.activity_id,
    activity_title: job.activity_title,
    due_label: null,
    submission_count: job.total_submissions,
    status: job.status,
    latest_job_id: job.id,
    queue_state: job.queue_state,
    reviewed_submissions: job.reviewed_submissions,
    total_submissions: job.total_submissions,
  };
}

export function App() {
  const { mode: themeMode, setMode: setThemeMode } = useThemePreference();
  const { history, addHistoryItem } = useLocalExportHistory();

  const [view, setView] = useState<AppView>("connect");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | string | null>(null);
  const [gradingJob, setGradingJob] = useState<GradingJob | null>(null);
  const [privacyAudit, setPrivacyAudit] = useState<PrivacyAudit | null>(null);
  const [activeGradingSubmissionId, setActiveGradingSubmissionId] = useState<string | null>(null);
  const [draftingSubmissionId, setDraftingSubmissionId] = useState<string | null>(null);
  const [graderBusy, setGraderBusy] = useState(false);
  const [gradingProgress, setGradingProgress] = useState<GradingInlineProgress | null>(null);

  const {
    folderSupported,
    deliveryMode,
    courses,
    activities,
    selectedCourseId,
    classQuery,
    activityQuery,
    dryRunOpen,
    job,
    lastResult,
    activitiesLoading,
    progress,
    progressLog,
    selectedCourse,
    previewTree,
    setClassQuery,
    setActivityQuery,
    setDryRunOpen,
    loadCourses,
    loadActivities,
    startExport,
    pickCourse,
    previewActivity,
    resetExportWorkspace,
  } = useExportWorkspace({
    view,
    busy,
    setBusy,
    setError,
    setView,
    loadGradingQueue: () => loadGradingQueue(),
    addHistoryItem,
  });

  const {
    selectedGradingItem,
    setSelectedGradingItem,
    gradingQueue,
    archivedQueue,
    setPendingQueue,
    gradingQueueLoading,
    gradingByActivity,
    queueItems,
    resetGradingQueue,
    sendActivitiesToQueue,
    findExistingJob,
    loadGradingQueue,
    runQueueAction,
  } = useGradingQueue({
    selectedCourse,
    getActiveJobId: () => gradingJob?.id ?? null,
    setView,
    setError,
    setGraderBusy,
    clearActiveJob,
  });

  const {
    auth,
    loading,
    apiOffline,
    versionSkew,
    gradingHealth,
    connected,
    partialConsent,
    bootstrap,
    connectClassroom,
    logoutClassroom,
  } = useConnection({
    setView,
    setBusy,
    setError,
    loadCourses,
    loadGradingQueue,
    restoreGradingJob,
    readStoredJobId,
    resetWorkspace,
  });

  useEffect(() => {
    if (connected && view === "connect") {
      setView("workspace");
    }
  }, [connected, view]);

  // Keep the reload pointer in sync with whichever job is open.
  useEffect(() => {
    writeStoredJobId(gradingJob?.id ?? null);
  }, [gradingJob?.id]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName.toLowerCase();
      const inField = tag === "input" || tag === "textarea";

      if (event.key === "Escape" && dryRunOpen) {
        event.preventDefault();
        setDryRunOpen(false);
        return;
      }

      if (view === "progress" && event.key === "Escape") {
        event.preventDefault();
        setView("workspace");
        return;
      }

      if (view === "done" && event.key === "Enter") {
        event.preventDefault();
        setView("history");
        return;
      }

      if (view !== "workspace") return;
      if (inField && event.key !== "Escape") return;
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dryRunOpen, view]);

  const partialConsentError = partialConsent
    ? new ApiError(401, "google_auth_denied", "Missing required Google scopes.")
    : null;
  const gateError =
    partialConsentError ?? (error && resolveError(error).tier === "gate" ? error : null);
  const handleGateAction = () => {
    const action = resolveError(gateError).action?.kind;
    if (action === "reconnect-google") {
      void connectClassroom();
      return;
    }
    void bootstrap();
  };

  function clearActiveJob() {
    setGradingJob(null);
    setPrivacyAudit(null);
    setActiveGradingSubmissionId(null);
    setSelectedGradingItem(null);
    writeStoredJobId(null);
  }

  function resetWorkspace() {
    resetExportWorkspace();
    resetGradingQueue();
    setGradingJob(null);
    writeStoredJobId(null);
    setPrivacyAudit(null);
  }

  function navigate(nextView: AppView) {
    if (!connected && nextView !== "connect") return;
    if (nextView === "graderQueue") void loadGradingQueue();
    setView(nextView);
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
      total_submissions: 0,
    };
    await beginGradingSetup(item);
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
      total_submissions: existing?.total_submissions ?? 0,
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

    return new Promise((resolve, reject) => {
      let source: EventSource | null = null;
      let settled = false;
      let reconnectAttempt = 0;
      const reconnectDelays = [2_000, 5_000, 10_000];

      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        source?.close();
        callback();
      };

      const connect = () => {
        source?.close();
        source = new EventSource(url);

        source.onmessage = (event) => {
        let payload: GradingStreamPayload;
        try {
          payload = JSON.parse(event.data) as GradingStreamPayload;
        } catch {
          finish(() => reject(new Error(fallbackError)));
          return;
        }

        if (payload.error) {
          const errorMessage = payload.error;
          setGradingProgress((currentState) => ({
            phase: payload.phase ?? currentState?.phase ?? phase,
            processed: payload.processed ?? currentState?.processed ?? 0,
            total: payload.total ?? currentState?.total ?? 0,
            current: payload.current ?? currentState?.current ?? "",
            done: true,
            error: errorMessage,
          }));
          finish(() => reject(new Error(errorMessage)));
          return;
        }

        onPayload?.(payload);
        setGradingProgress((currentState) => ({
          phase: payload.phase ?? currentState?.phase ?? phase,
          processed: payload.processed ?? currentState?.processed ?? 0,
          total: payload.total ?? currentState?.total ?? 0,
          current: payload.current ?? currentState?.current ?? "",
          done: Boolean(payload.done),
          error: null,
        }));

        if (payload.done) {
          finish(() => resolve(payload));
        }
        };

        source.onerror = () => {
          source?.close();
          const delay = reconnectDelays[reconnectAttempt];
          if (delay !== undefined) {
            reconnectAttempt += 1;
            setGradingProgress((current) => ({
              phase,
              processed: current?.processed ?? 0,
              total: current?.total ?? 0,
              current: `Reconectando... tentativa ${reconnectAttempt}/3`,
              done: false,
              error: null,
            }));
            window.setTimeout(() => {
              if (!settled) connect();
            }, delay);
            return;
          }
          const resumeMessage =
            "O processamento foi interrompido, mas pode continuar de onde parou. Use Retomar na fila.";
          setGradingProgress((current) => ({
            phase,
            processed: current?.processed ?? 0,
            total: current?.total ?? 0,
            current: current?.current ?? "",
            done: true,
            error: resumeMessage,
          }));
          finish(() => reject(new Error(resumeMessage || fallbackError)));
        };
      };

      connect();
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
      const submissions = current.submissions.map((row) =>
        row.id === submission.id ? submission : row,
      );
      if (!submissions.some((row) => row.id === submission.id)) {
        submissions.push(submission);
      }
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
    payload: { rubricMode: RubricMode; teacherLoop: TeacherLoopMode; rubricText: string; includeVisualSubmissions: boolean },
  ): GradingJob | null {
    const reusable =
      gradingJob?.activity_id === item.activity_id &&
      gradingJob.status === "ready" &&
      gradingJob.rubric_mode === payload.rubricMode &&
      gradingJob.teacher_loop === payload.teacherLoop &&
      (gradingJob.rubric_text ?? "") === (payload.rubricText ?? "") &&
      gradingJob.include_visual_submissions === payload.includeVisualSubmissions;
    return reusable ? gradingJob : null;
  }

  // Step 1 of infer mode: produce the inferred rubric and pause on the setup
  // screen so the teacher can edit it before the audit runs.
  async function inferGradingCriteria(
    item: GradingQueueItem,
    payload: { rubricMode: RubricMode; teacherLoop: TeacherLoopMode; rubricText: string; includeVisualSubmissions: boolean },
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
    setGraderBusy(true);
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
      setGraderBusy(false);
    }
  }

  async function acceptGradingDraft(submission: GradingSubmission, score: number, feedback: string) {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      const updated = await api.reviewGradingSubmission(gradingJob.id, submission.id, {
        final_score: score,
        feedback,
        reviewed: true,
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
      setGraderBusy(false);
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

  return (
    <div className={appStyles.shell} data-screen-label={view}>
      <Rail
        view={view}
        auth={auth}
        history={history}
        onNavigate={navigate}
        onLogout={() => void logoutClassroom()}
        themeMode={themeMode}
        onThemeChange={setThemeMode}
      />

      <main className="main">
        {gateError ? (
          <Gate error={gateError} onAction={handleGateAction} />
        ) : (
          <>
            {versionSkew ? (
              <InlineError
                error={new ApiError(0, "version_skew", "Frontend and backend versions differ.")}
                onAction={() => window.location.reload()}
              />
            ) : null}
        {view === "connect" ? (
          <ConnectView
            connecting={busy}
            deliveryMode={deliveryMode}
            error={error}
            onConnect={connectClassroom}
          />
        ) : null}

        {view === "admin" ? <AdminView /> : null}

        {view === "workspace" ? (
          <>
            {gradingHealth && !gradingHealth.ready ? (
              <GradingHealthBanner health={gradingHealth} />
            ) : null}
            {!folderSupported ? (
              <InlineError
                error={
                  new ApiError(
                    0,
                    "unsupported_browser",
                    "Folder export is not available in this browser.",
                  )
                }
              />
            ) : null}
            <TurmasView
                courses={courses}
                activeCourseId={selectedCourseId}
                activities={activities}
                classQuery={classQuery}
                activityQuery={activityQuery}
                loadingCourses={loading}
                loadingActivities={activitiesLoading}
                busy={busy}
                deliveryMode={deliveryMode}
                gradingByActivity={gradingByActivity}
                onPickCourse={pickCourse}
                onClassQuery={setClassQuery}
                onActivityQuery={setActivityQuery}
                onGrade={gradeActivity}
                onRegrade={regradeActivity}
                onPreview={previewActivity}
                onDownload={(activity) => void startExport([activity.id])}
                onSendToQueue={sendActivitiesToQueue}
              />
            {error ? (
              <InlineError
                message={error}
                onAction={() =>
                  selectedCourseId ? void loadActivities(selectedCourseId) : void bootstrap()
                }
              />
            ) : null}
            {dryRunOpen && previewTree ? (
              <DryRunDrawer
                tree={previewTree}
                fileCount={job?.files.length ?? 0}
                deliveryMode={deliveryMode}
                onClose={() => setDryRunOpen(false)}
                onProceed={() => void startExport()}
              />
            ) : null}
          </>
        ) : null}

        {view === "progress" && selectedCourse ? (
          <ProgressView
            courseName={selectedCourse.name}
            total={progress.total}
            completed={progress.completed}
            failed={job?.errors.length ?? 0}
            currentPath={progress.currentPath}
            log={progressLog}
            error={error ? appErrorSummary(error) : null}
            deliveryMode={deliveryMode}
            onCancel={() => setView("workspace")}
          />
        ) : null}

        {view === "done" && lastResult ? (
          <DoneView
            result={lastResult}
            onDownloadAnother={() => setView("workspace")}
            onViewHistory={() => setView("history")}
          />
        ) : null}

        {view === "history" ? <HistoryView items={history} onBack={() => setView("workspace")} /> : null}

        {view === "graderQueue" ? (
          <>
            <GraderQueue
              items={queueItems}
              archivedItems={archivedQueue}
              loading={gradingQueueLoading}
              onRefresh={() => void loadGradingQueue()}
              onSetup={(item) => void beginGradingSetup(item)}
              onOpenJob={(jobId) => void openGradingJob(jobId)}
              onAction={(action, items) => void runQueueAction(action, items)}
              onDownloadInstead={() => setView("workspace")}
            />
            {error ? (
              <InlineError
                message={error}
                onAction={() => {
                  setError(null);
                  void loadGradingQueue();
                }}
              />
            ) : null}
          </>
        ) : null}

        {view === "graderSetup" && selectedGradingItem ? (
          <>
            <GraderSetup
              item={selectedGradingItem}
              job={gradingJob}
              busy={graderBusy}
              audit={privacyAudit}
              progress={gradingProgress}
              onBack={() => setView("workspace")}
              onInferCriteria={(payload) => void runInferGradingCriteria(payload)}
              onStart={(payload) => void runGradingPrivacyAudit(payload)}
              onContinue={() => void continueToGradingDraft()}
              onRerun={() => void rerunGradingPrivacyAudit()}
            />
            {error ? (
              <InlineError
                message={error}
                onAction={() =>
                  gradingJob
                    ? void openGradingJob(gradingJob.id)
                    : void beginGradingSetup(selectedGradingItem)
                }
              />
            ) : null}
          </>
        ) : null}

        {view === "graderReview" && gradingJob ? (
          <>
            <GraderReview
              job={gradingJob}
              busy={graderBusy}
              audit={privacyAudit}
              progress={gradingProgress}
              activeSubmissionId={activeGradingSubmissionId}
              draftingSubmissionId={draftingSubmissionId}
              onActiveSubmission={setActiveGradingSubmissionId}
              onBack={() => setView("workspace")}
              onWrap={() => setView("graderWrap")}
              onAccept={(submission, score, feedback) =>
                void acceptGradingDraft(submission, score, feedback)
              }
              onRetry={(submission) => void retryGradingDraft(submission)}
            />
            {error ? (
              <InlineError message={error} onAction={() => void openGradingJob(gradingJob.id)} />
            ) : null}
          </>
        ) : null}

        {view === "graderWrap" && gradingJob ? (
          <>
            <GraderWrap
              job={gradingJob}
              busy={graderBusy}
              onBack={() => setView("graderReview")}
              onQueue={() => navigate("graderQueue")}
              onDeleteCache={() => void deleteGradingCache()}
              onJobUpdate={setGradingJob}
            />
            {error ? (
              <InlineError message={error} onAction={() => void openGradingJob(gradingJob.id)} />
            ) : null}
          </>
        ) : null}
          </>
        )}
        {apiOffline && !gateError ? <OfflinePill /> : null}
      </main>
    </div>
  );
}

function GradingHealthBanner({ health }: { health: GradingHealth }) {
  const message =
    health.status === "provider_key_missing"
      ? `Falta a chave da API do provedor${
          health.missing_keys.length ? ` (${health.missing_keys.join(", ")})` : ""
        }. Configure em apps/api/.env e reinicie a API.`
      : health.status === "model_not_enabled"
        ? "O modelo selecionado não está habilitado no catálogo (config/llm-model-overrides.json)."
        : health.detail;
  return (
    <div className="notice notice-warning" role="alert">
      <div className="notice-icon">
        <AppIcon name="triangleAlert" />
      </div>
      <div className="notice-copy">
        <div className="notice-title">Correção por IA indisponível</div>
        <div className="notice-desc">{message}</div>
      </div>
    </div>
  );
}

