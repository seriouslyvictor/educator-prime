import { useEffect, useMemo, useState } from "react";
import { ConnectView, InlineError } from "./components/ConnectView";
import { DoneView } from "./components/DoneView";
import { DryRunDrawer } from "./components/DryRunDrawer";
import {
  GraderQueue,
  GraderReview,
  GraderSetup,
  GraderWrap,
} from "./components/grader";
import {
  GradingProgressModal,
  type GradingProgressState,
} from "./components/grader/GradingProgressModal";
import { HistoryView } from "./components/HistoryView";
import { ProgressView, type ProgressLogItem } from "./components/ProgressView";
import { Rail } from "./components/Rail";
import { ActivityList, ClassroomList } from "./components/workspace";
import { api } from "./lib/api";
import appStyles from "./components/App.module.css";
void appStyles;
import {
  exportJobToFolder,
  isFolderExportSupported,
  pickExportFolder,
} from "./lib/folder-export";
import { useLocalExportHistory } from "./lib/local-history";
import { buildPreviewTree } from "./lib/preview-tree";
import { useThemePreference } from "./lib/theme";
import { AppIcon } from "./components/icons";
import type {
  Activity,
  AppView,
  AuthState,
  Course,
  ExportJob,
  GradingHealth,
  GradingCriterionInput,
  GradingJob,
  GradingQueueItem,
  GradingSubmission,
  LocalExportHistoryItem,
  PrivacyAudit,
  RubricMode,
  TeacherLoopMode,
} from "./types";

const classroomScopes = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/classroom.courses.readonly",
  "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
  "https://www.googleapis.com/auth/classroom.rosters.readonly",
  "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
  "https://www.googleapis.com/auth/classroom.profile.emails",
  "https://www.googleapis.com/auth/classroom.profile.photos",
  "https://www.googleapis.com/auth/drive.readonly",
];

// Remembering the active grading job lets a page reload drop the teacher back into
// the same job instead of an empty workspace — the job itself is already persisted
// server-side, this is just the pointer to it.
const ACTIVE_JOB_STORAGE_KEY = "cd.grading.activeJobId";

type GradingStreamPayload = {
  phase?: "audit" | "draft";
  processed?: number;
  total?: number;
  current?: string;
  done?: boolean;
  error?: string;
  summary?: PrivacyAudit;
  job?: GradingJob;
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
    reviewed_submissions: job.reviewed_submissions,
    total_submissions: job.total_submissions,
  };
}

export function App() {
  const { mode: themeMode, setMode: setThemeMode } = useThemePreference();
  const { history, addHistoryItem } = useLocalExportHistory();
  const folderSupported = isFolderExportSupported();
  const deliveryMode: "folder" | "zip" = folderSupported ? "folder" : "zip";

  const [view, setView] = useState<AppView>("connect");
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [gradingHealth, setGradingHealth] = useState<GradingHealth | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [selectedActivityIds, setSelectedActivityIds] = useState<string[]>([]);
  const [classQuery, setClassQuery] = useState("");
  const [activityQuery, setActivityQuery] = useState("");
  const [dryRunOpen, setDryRunOpen] = useState(false);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [lastResult, setLastResult] = useState<LocalExportHistoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ completed: 0, total: 0, currentPath: "" });
  const [progressLog, setProgressLog] = useState<ProgressLogItem[]>([]);
  const [selectedGradingItem, setSelectedGradingItem] = useState<GradingQueueItem | null>(null);
  const [gradingQueue, setGradingQueue] = useState<GradingQueueItem[]>([]);
  const [gradingQueueLoading, setGradingQueueLoading] = useState(false);
  const [gradingJob, setGradingJob] = useState<GradingJob | null>(null);
  const [privacyAudit, setPrivacyAudit] = useState<PrivacyAudit | null>(null);
  const [activeGradingSubmissionId, setActiveGradingSubmissionId] = useState<string | null>(null);
  const [graderBusy, setGraderBusy] = useState(false);
  const [gradingProgress, setGradingProgress] = useState<GradingProgressState | null>(null);

  const connected = Boolean(auth?.signed_in && auth.classroom_scopes && auth.drive_scopes);
  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId),
    [courses, selectedCourseId],
  );
  const selectedActivities = useMemo(
    () => activities.filter((activity) => selectedActivityIds.includes(activity.id)),
    [activities, selectedActivityIds],
  );
  const previewTree = selectedCourse
    ? buildPreviewTree(selectedCourse, selectedActivities, job)
    : null;
  const gradingByActivity = useMemo(() => {
    const rows = new Map<string, GradingQueueItem>();
    for (const item of gradingQueue) {
      if (!selectedCourse || item.course_id === selectedCourse.id) {
        rows.set(item.activity_id, item);
      }
    }
    return rows;
  }, [gradingQueue, selectedCourse]);

  useEffect(() => {
    void bootstrap();
  }, []);

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

  async function bootstrap() {
    setLoading(true);
    setError(null);
    try {
      const authState = await api.authMe();
      setAuth(authState);
      const hasConnection = authState.signed_in && authState.classroom_scopes && authState.drive_scopes;
      if (!hasConnection) {
        setView("connect");
        return;
      }
      // Checked right after login: AI grading depends on a configured provider key.
      void api.gradingHealth().then(setGradingHealth).catch(() => setGradingHealth(null));
      try {
        await loadCourses();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Falha ao carregar o estado do app.");
        setView("connect");
        return;
      }
      await loadGradingQueue();
      const restoredJobId = readStoredJobId();
      if (restoredJobId && (await restoreGradingJob(restoredJobId))) {
        return;
      }
      setView("workspace");
    } catch {
      setAuth(null);
      setView("connect");
    } finally {
      setLoading(false);
    }
  }

  async function loadCourses() {
    const courseList = await api.courses();
    setCourses(courseList);
    if (courseList[0]) {
      setSelectedCourseId(courseList[0].id);
      await loadActivities(courseList[0].id);
    }
  }

  async function loadActivities(courseId: string) {
    setActivitiesLoading(true);
    setError(null);
    setSelectedActivityIds([]);
    setJob(null);
    try {
      const activityList = await api.activities(courseId);
      setActivities(activityList);
      setSelectedActivityIds([]);
      await loadGradingQueue();
    } catch (caught) {
      setActivities([]);
      setError(caught instanceof Error ? caught.message : "Falha ao carregar atividades.");
    } finally {
      setActivitiesLoading(false);
    }
  }


  async function connectClassroom() {
    setBusy(true);
    setError(null);
    try {
      const authStart = await api.connectGoogle(classroomScopes);
      if (authStart.authorization_url) {
        window.location.href = authStart.authorization_url;
        return;
      }
      await bootstrap();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao conectar o Google.");
    } finally {
      setBusy(false);
    }
  }

  async function logoutClassroom() {
    setBusy(true);
    setError(null);
    try {
      const nextAuth = await api.logoutGoogle();
      setAuth(nextAuth);
      setCourses([]);
      setActivities([]);
      setSelectedCourseId("");
      setSelectedActivityIds([]);
      setSelectedGradingItem(null);
      setGradingJob(null);
      setGradingQueue([]);
      writeStoredJobId(null);
      setPrivacyAudit(null);
      setJob(null);
      setView("connect");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao sair da conta Google.");
    } finally {
      setBusy(false);
    }
  }

  async function startExport(activityIds = selectedActivityIds) {
    if (!selectedCourse || activityIds.length === 0 || busy) return;
    if (deliveryMode === "zip") {
      setError("A entrega por zip ainda é placeholder nesta versão. Use Chrome ou Edge para exportar para uma pasta.");
      return;
    }

    setBusy(true);
    setError(null);
    setDryRunOpen(false);
    setProgress({ completed: 0, total: 0, currentPath: "" });
    setProgressLog([]);

    try {
      const root = await pickExportFolder();
      const exportJob = await api.createExport(selectedCourse.id, activityIds);
      setJob(exportJob);
      setProgress({ completed: 0, total: exportJob.files.length, currentPath: "Preparando arquivos..." });
      setView("progress");

      await exportJobToFolder(exportJob, root, (completed, total, currentPath) => {
        setProgress({ completed, total, currentPath });
        setProgressLog((current) => [
          ...current.slice(-80),
          { id: `${completed}-${currentPath}`, kind: "ok", text: currentPath },
        ]);
      });

      const historyItem = {
        courseName: selectedCourse.name,
        activityCount: activityIds.length,
        fileCount: exportJob.files.length,
        outputLabel: `${root.name}/${selectedCourse.name}`,
      };
      addHistoryItem(historyItem);
      setLastResult({
        ...historyItem,
        id: crypto.randomUUID(),
        completedAt: new Date().toISOString(),
      });
      setView("done");
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Falha na exportação.";
      setError(message);
      setProgressLog((current) => [
        ...current,
        { id: `error-${Date.now()}`, kind: "err", text: message },
      ]);
      if (view !== "progress") setView("workspace");
    } finally {
      setBusy(false);
    }
  }

  function pickCourse(courseId: string) {
    setSelectedCourseId(courseId);
    void loadActivities(courseId);
  }

  function navigate(nextView: AppView) {
    if (!connected && nextView !== "connect") return;
    if (nextView === "graderQueue") void loadGradingQueue();
    setView(nextView);
  }

  function previewActivity(activity: Activity) {
    setSelectedActivityIds([activity.id]);
    setJob(null);
    setDryRunOpen(true);
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
      reviewed_submissions: 0,
      total_submissions: 0,
    };
    setSelectedGradingItem(item);
    setView("graderSetup");
    void startGradingAuditForItem(item, {
      rubricMode: "infer",
      teacherLoop: "approve",
      rubricText: "",
    });
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
      reviewed_submissions: existing?.reviewed_submissions ?? 0,
      total_submissions: existing?.total_submissions ?? 0,
    });
    setView("graderSetup");
  }

  async function findExistingJob(
    courseId: string,
    activityId: string,
  ): Promise<GradingQueueItem | null> {
    try {
      const items = await api.gradingQueue(courseId, activityId);
      return items.find((item) => item.latest_job_id) ?? null;
    } catch {
      return null;
    }
  }

  async function loadGradingQueue() {
    setGradingQueueLoading(true);
    try {
      setGradingQueue(await api.gradingJobs());
    } catch {
      setGradingQueue([]);
    } finally {
      setGradingQueueLoading(false);
    }
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
        let audit: PrivacyAudit;
        try {
          audit = await api.privacyAudit(nextJob.id);
        } catch {
          setGradingJob(nextJob);
          setSelectedGradingItem(gradingItemFromJob(nextJob));
          setView("graderSetup");
          const payload = await streamGradingProgress(
            api.privacyAuditStreamUrl(nextJob.id),
            "audit",
            "Falha ao executar a auditoria de privacidade.",
          );
          if (!payload.summary) throw new Error("A auditoria terminou sem resumo.");
          audit = payload.summary;
          setGradingProgress(null);
        }
        setPrivacyAudit(audit);
        setSelectedGradingItem(gradingItemFromJob(nextJob));
        setView("graderSetup");
        return;
      }
      setView(nextJob.status === "completed" ? "graderWrap" : "graderReview");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao abrir a correção.");
    } finally {
      setGraderBusy(false);
    }
  }

  function streamGradingProgress(
    url: string,
    phase: "audit" | "draft",
    fallbackError: string,
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
      const source = new EventSource(url);
      let settled = false;

      const finish = (callback: () => void) => {
        if (settled) return;
        settled = true;
        source.close();
        callback();
      };

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
            phase,
            processed: payload.processed ?? currentState?.processed ?? 0,
            total: payload.total ?? currentState?.total ?? 0,
            current: payload.current ?? currentState?.current ?? "",
            done: true,
            error: errorMessage,
          }));
          finish(() => reject(new Error(errorMessage)));
          return;
        }

        setGradingProgress((currentState) => ({
          phase,
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
        setGradingProgress((current) => ({
          phase,
          processed: current?.processed ?? 0,
          total: current?.total ?? 0,
          current: current?.current ?? "",
          done: true,
          error: fallbackError,
        }));
        finish(() => reject(new Error(fallbackError)));
      };
    });
  }

  async function startGradingAuditForItem(
    item: GradingQueueItem,
    payload: {
      rubricMode: RubricMode;
      teacherLoop: TeacherLoopMode;
      rubricText: string;
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
      const created = await api.createGradingJob({
        course_id: item.course_id,
        activity_id: item.activity_id,
        rubric_mode: payload.rubricMode,
        teacher_loop: payload.teacherLoop,
        rubric_text: payload.rubricText,
        criteria: payload.criteria,
      });
      setGradingJob(created);
      setSelectedGradingItem(gradingItemFromJob(created));
      const streamed = await streamGradingProgress(
        api.privacyAuditStreamUrl(created.id),
        "audit",
        "Falha ao executar a auditoria de privacidade.",
      );
      if (!streamed.summary) throw new Error("A auditoria terminou sem resumo.");
      setPrivacyAudit(streamed.summary);
      api.clearGradingCache(created.id);
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
    criteria?: GradingCriterionInput[];
  }) {
    if (!selectedGradingItem) return;
    await startGradingAuditForItem(selectedGradingItem, payload);
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
    try {
      const streamed = await streamGradingProgress(
        api.draftStreamUrl(gradingJob.id),
        "draft",
        "Falha ao gerar rascunhos de notas.",
      );
      if (!streamed.job) throw new Error("A avaliação terminou sem resultado.");
      const drafted = streamed.job;
      setGradingJob(drafted);
      setActiveGradingSubmissionId(drafted.submissions[0]?.id ?? null);
      setView("graderReview");
      api.clearGradingCache(drafted.id);
      setGradingProgress(null);
      void loadGradingQueue();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao gerar rascunhos de notas.");
    } finally {
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
      setError(caught instanceof Error ? caught.message : "Falha ao salvar a revisão.");
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
      setError(caught instanceof Error ? caught.message : "Falha ao corrigir a entrega novamente.");
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
      setError(caught instanceof Error ? caught.message : "Falha ao apagar arquivos em cache.");
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
        {view === "connect" ? (
          <ConnectView
            connecting={busy}
            deliveryMode={deliveryMode}
            error={error}
            onConnect={connectClassroom}
          />
        ) : null}

        {view === "workspace" ? (
          <>
            {gradingHealth && !gradingHealth.ready ? (
              <GradingHealthBanner health={gradingHealth} />
            ) : null}
            <div className="workspace">
              <ClassroomList
                courses={courses}
                activeId={selectedCourseId}
                query={classQuery}
                loading={loading}
                onPick={pickCourse}
                onQuery={setClassQuery}
              />
              <ActivityList
                course={selectedCourse}
                activities={activities}
                query={activityQuery}
                loading={activitiesLoading}
                onQuery={setActivityQuery}
                onGrade={gradeActivity}
                onRegrade={regradeActivity}
                onPreview={previewActivity}
                onDownload={(activity) => void startExport([activity.id])}
                busy={busy}
                deliveryMode={deliveryMode}
                gradingByActivity={gradingByActivity}
              />
            </div>
            {error ? <InlineError message={error} /> : null}
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
            error={error}
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
              items={gradingQueue}
              loading={gradingQueueLoading}
              onRefresh={() => void loadGradingQueue()}
              onSetup={(item) => {
                setPrivacyAudit(null);
                setGradingJob(null);
                setSelectedGradingItem(item);
                setView("graderSetup");
              }}
              onOpenJob={(jobId) => void openGradingJob(jobId)}
              onDownloadInstead={() => setView("workspace")}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}

        {view === "graderSetup" && selectedGradingItem ? (
          <>
            <GraderSetup
              item={selectedGradingItem}
              busy={graderBusy}
              audit={privacyAudit}
              onBack={() => setView("workspace")}
              onStart={(payload) => void runGradingPrivacyAudit(payload)}
              onContinue={() => void continueToGradingDraft()}
              onRerun={() => void rerunGradingPrivacyAudit()}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}

        {view === "graderReview" && gradingJob ? (
          <>
            <GraderReview
              job={gradingJob}
              busy={graderBusy}
              activeSubmissionId={activeGradingSubmissionId}
              onActiveSubmission={setActiveGradingSubmissionId}
              onBack={() => setView("workspace")}
              onWrap={() => setView("graderWrap")}
              onAccept={(submission, score, feedback) =>
                void acceptGradingDraft(submission, score, feedback)
              }
              onRetry={(submission) => void retryGradingDraft(submission)}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}

        {view === "graderWrap" && gradingJob ? (
          <>
            <GraderWrap
              job={gradingJob}
              busy={graderBusy}
              onBack={() => setView("graderReview")}
              onQueue={() => setView("workspace")}
              onDeleteCache={() => void deleteGradingCache()}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}
      </main>
      {gradingProgress ? (
        <GradingProgressModal state={gradingProgress} onClose={() => setGradingProgress(null)} />
      ) : null}
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

