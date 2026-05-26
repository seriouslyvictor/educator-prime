import { useCallback, useEffect, useMemo, useState } from "react";
import { ActionBar } from "./components/ActionBar";
import { ConnectView, InlineError } from "./components/ConnectView";
import { DoneView } from "./components/DoneView";
import { DryRunDrawer } from "./components/DryRunDrawer";
import { GraderAudit, GraderQueue, GraderReview, GraderSetup, GraderWrap } from "./components/Grader";
import { HistoryView } from "./components/HistoryView";
import { ProgressView, type ProgressLogItem } from "./components/ProgressView";
import { Rail } from "./components/Rail";
import { ActivityList, ClassroomList } from "./components/Workspace";
import { api } from "./lib/api";
import {
  exportJobToFolder,
  isFolderExportSupported,
  pickExportFolder,
} from "./lib/folder-export";
import { useLocalExportHistory } from "./lib/local-history";
import { buildPreviewTree } from "./lib/preview-tree";
import { useThemePreference } from "./lib/theme";
import type {
  Activity,
  AppView,
  AuthState,
  Course,
  ExportJob,
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

export function App() {
  const { mode: themeMode, setMode: setThemeMode } = useThemePreference();
  const { history, addHistoryItem } = useLocalExportHistory();
  const folderSupported = isFolderExportSupported();
  const deliveryMode: "folder" | "zip" = folderSupported ? "folder" : "zip";

  const [view, setView] = useState<AppView>("connect");
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [selectedActivityIds, setSelectedActivityIds] = useState<string[]>([]);
  const [classQuery, setClassQuery] = useState("");
  const [activityQuery, setActivityQuery] = useState("");
  const [cursorIndex, setCursorIndex] = useState(0);
  const [keyboardActive, setKeyboardActive] = useState(false);
  const [dryRunOpen, setDryRunOpen] = useState(false);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [lastResult, setLastResult] = useState<LocalExportHistoryItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ completed: 0, total: 0, currentPath: "" });
  const [progressLog, setProgressLog] = useState<ProgressLogItem[]>([]);
  const [gradingQueue, setGradingQueue] = useState<GradingQueueItem[]>([]);
  const [selectedGradingItem, setSelectedGradingItem] = useState<GradingQueueItem | null>(null);
  const [gradingJob, setGradingJob] = useState<GradingJob | null>(null);
  const [privacyAudit, setPrivacyAudit] = useState<PrivacyAudit | null>(null);
  const [activeGradingSubmissionId, setActiveGradingSubmissionId] = useState<string | null>(null);
  const [graderBusy, setGraderBusy] = useState(false);

  const connected = Boolean(auth?.signed_in && auth.classroom_scopes && auth.drive_scopes);
  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId),
    [courses, selectedCourseId],
  );
  const selectedActivities = useMemo(
    () => activities.filter((activity) => selectedActivityIds.includes(activity.id)),
    [activities, selectedActivityIds],
  );
  const filteredActivities = useMemo(
    () =>
      activities.filter((activity) =>
        `${activity.title} ${activity.work_type}`.toLowerCase().includes(activityQuery.toLowerCase()),
      ),
    [activities, activityQuery],
  );
  const previewTree = selectedCourse
    ? buildPreviewTree(selectedCourse, selectedActivities, job)
    : null;

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (connected && view === "connect") {
      setView("workspace");
    }
  }, [connected, view]);

  useEffect(() => {
    setCursorIndex(0);
  }, [selectedCourseId, activityQuery]);

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

      if (event.ctrlKey && event.key.toLowerCase() === "a") {
        event.preventDefault();
        toggleAllActivities(filteredActivities, true);
        return;
      }

      if (event.ctrlKey && event.key.toLowerCase() === "d") {
        event.preventDefault();
        if (selectedActivityIds.length > 0) setDryRunOpen(true);
        return;
      }

      if (event.ctrlKey && event.key === "Enter") {
        event.preventDefault();
        void startExport();
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        setKeyboardActive(true);
        setCursorIndex((index) => Math.min(filteredActivities.length - 1, index + 1));
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setKeyboardActive(true);
        setCursorIndex((index) => Math.max(0, index - 1));
      }

      if (event.key === " ") {
        const activity = filteredActivities[cursorIndex];
        if (activity) {
          event.preventDefault();
          toggleActivity(activity.id);
        }
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cursorIndex, dryRunOpen, filteredActivities, selectedActivityIds.length, view]);

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
      try {
        await loadCourses();
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Failed to load app state.");
        setView("connect");
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
      setSelectedActivityIds(activityList.map((activity) => activity.id));
    } catch (caught) {
      setActivities([]);
      setError(caught instanceof Error ? caught.message : "Failed to load activities.");
    } finally {
      setActivitiesLoading(false);
    }
  }

  async function loadGradingQueue() {
    setGraderBusy(true);
    setError(null);
    try {
      setGradingQueue(await api.gradingQueue());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load grading queue.");
    } finally {
      setGraderBusy(false);
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
      setError(caught instanceof Error ? caught.message : "Failed to connect Google.");
    } finally {
      setBusy(false);
    }
  }

  async function startExport() {
    if (!selectedCourse || selectedActivityIds.length === 0 || busy) return;
    if (deliveryMode === "zip") {
      setError("Zip delivery is only a placeholder in this build. Use Chrome or Edge for folder export.");
      return;
    }

    setBusy(true);
    setError(null);
    setDryRunOpen(false);
    setProgress({ completed: 0, total: 0, currentPath: "" });
    setProgressLog([]);

    try {
      const root = await pickExportFolder();
      const exportJob = await api.createExport(selectedCourse.id, selectedActivityIds);
      setJob(exportJob);
      setProgress({ completed: 0, total: exportJob.files.length, currentPath: "Preparing files..." });
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
        activityCount: selectedActivityIds.length,
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
      const message = caught instanceof Error ? caught.message : "Export failed.";
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

  function toggleActivity(activityId: string) {
    setSelectedActivityIds((current) =>
      current.includes(activityId)
        ? current.filter((id) => id !== activityId)
        : [...current, activityId],
    );
  }

  const toggleAllActivities = useCallback((rows: Activity[], selected: boolean) => {
    setSelectedActivityIds((current) => {
      const next = new Set(current);
      for (const row of rows) {
        if (selected) next.add(row.id);
        else next.delete(row.id);
      }
      return Array.from(next);
    });
  }, []);

  function pickCourse(courseId: string) {
    setSelectedCourseId(courseId);
    void loadActivities(courseId);
  }

  function navigate(nextView: AppView) {
    if (!connected && nextView !== "connect") return;
    if (nextView === "graderQueue") void loadGradingQueue();
    setView(nextView);
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
          audit = await api.runPrivacyAudit(nextJob.id);
        }
        setPrivacyAudit(audit);
        setView("graderAudit");
        return;
      }
      setView(nextJob.status === "completed" ? "graderWrap" : "graderReview");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to open grading job.");
    } finally {
      setGraderBusy(false);
    }
  }

  async function runGradingPrivacyAudit(payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
  }) {
    if (!selectedGradingItem) return;
    setGraderBusy(true);
    setError(null);
    try {
      const created = await api.createGradingJob({
        course_id: selectedGradingItem.course_id,
        activity_id: selectedGradingItem.activity_id,
        rubric_mode: payload.rubricMode,
        teacher_loop: payload.teacherLoop,
        rubric_text: payload.rubricText,
      });
      setGradingJob(created);
      const audit = await api.runPrivacyAudit(created.id);
      setPrivacyAudit(audit);
      setView("graderAudit");
      void loadGradingQueue();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to run privacy audit.");
    } finally {
      setGraderBusy(false);
    }
  }

  async function rerunGradingPrivacyAudit() {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      setPrivacyAudit(await api.runPrivacyAudit(gradingJob.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to run privacy audit.");
    } finally {
      setGraderBusy(false);
    }
  }

  async function continueToGradingDraft() {
    if (!gradingJob) return;
    setGraderBusy(true);
    setError(null);
    try {
      const drafted = await api.draftGradingJob(gradingJob.id);
      setGradingJob(drafted);
      setActiveGradingSubmissionId(drafted.submissions[0]?.id ?? null);
      setView("graderReview");
      void loadGradingQueue();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to draft grades.");
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
      if (updated.reviewed_submissions === updated.total_submissions && updated.total_submissions > 0) {
        setView("graderWrap");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save review.");
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
      setError(caught instanceof Error ? caught.message : "Failed to re-grade submission.");
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
      setError(caught instanceof Error ? caught.message : "Failed to delete cached files.");
    } finally {
      setGraderBusy(false);
    }
  }

  return (
    <div className="shell" data-screen-label={view}>
      <Rail
        view={view}
        auth={auth}
        history={history}
        onNavigate={navigate}
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
                selectedIds={selectedActivityIds}
                query={activityQuery}
                cursorIndex={cursorIndex}
                keyboardActive={keyboardActive}
                loading={activitiesLoading}
                onToggle={toggleActivity}
                onToggleAll={toggleAllActivities}
                onQuery={setActivityQuery}
              />
            </div>
            {error ? <InlineError message={error} /> : null}
            <ActionBar
              selectedCount={selectedActivityIds.length}
              fileEstimate={job?.files.length ?? 0}
              deliveryMode={deliveryMode}
              disabled={selectedActivityIds.length === 0 || deliveryMode === "zip"}
              busy={busy}
              onDryRun={() => setDryRunOpen(true)}
              onDownload={() => void startExport()}
            />
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
              loading={graderBusy}
              onRefresh={() => void loadGradingQueue()}
              onSetup={(item) => {
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
              onBack={() => setView("graderQueue")}
              onStart={(payload) => void runGradingPrivacyAudit(payload)}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}

        {view === "graderAudit" && privacyAudit ? (
          <>
            <GraderAudit
              audit={privacyAudit}
              busy={graderBusy}
              onBack={() => setView("graderSetup")}
              onRerun={() => void rerunGradingPrivacyAudit()}
              onContinue={() => void continueToGradingDraft()}
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
              onBack={() => {
                setView("graderQueue");
                void loadGradingQueue();
              }}
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
              onQueue={() => {
                setView("graderQueue");
                void loadGradingQueue();
              }}
              onDeleteCache={() => void deleteGradingCache()}
            />
            {error ? <InlineError message={error} /> : null}
          </>
        ) : null}
      </main>
    </div>
  );
}
