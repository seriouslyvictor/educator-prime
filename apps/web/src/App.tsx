import { useEffect, useRef, useState } from "react";
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
} from "./lib/api";
import { resolveError } from "./lib/errorCatalog";
import appStyles from "./components/App.module.css";
void appStyles;
import { useLocalExportHistory } from "./lib/local-history";
import { useThemePreference } from "./lib/theme";
import { useConnection } from "./hooks/useConnection";
import { useExportWorkspace } from "./hooks/useExportWorkspace";
import { useGradingQueue } from "./hooks/useGradingQueue";
import { useGradingJob, readStoredJobId } from "./hooks/useGradingJob";
import { AppIcon } from "./components/icons";
import { InlineError } from "./components/ui";
import { Gate, OfflinePill } from "./components/errors";
import type {
  AppView,
  GradingHealth,
} from "./types";

function appErrorSummary(error: unknown): string {
  const entry = resolveError(error);
  return `${entry.title}: ${entry.body}`;
}

export function App() {
  const { mode: themeMode, setMode: setThemeMode } = useThemePreference();
  const { history, addHistoryItem } = useLocalExportHistory();

  const [view, setView] = useState<AppView>("connect");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | string | null>(null);
  // graderBusy is shared between useGradingJob and useGradingQueue; keeping it
  // in App avoids a circular dependency (queue needs it as a setter, job owns it).
  const [graderBusy, setGraderBusy] = useState(false);

  // clearActiveJob and getActiveJobId are defined by useGradingJob but needed by
  // useGradingQueue (which is called first). Stable refs break the circular dep;
  // the refs are populated every render before any callback fires.
  const clearActiveJobRef = useRef<() => void>(() => {});
  const getActiveJobIdRef = useRef<() => string | null>(() => null);

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
    getActiveJobId: () => getActiveJobIdRef.current(),
    setView,
    setError,
    setGraderBusy,
    clearActiveJob: () => clearActiveJobRef.current(),
  });

  const {
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
  } = useGradingJob({
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
  });

  // Keep the refs current every render so queue callbacks always get the latest
  // functions from the job hook.
  clearActiveJobRef.current = clearActiveJob;
  getActiveJobIdRef.current = getActiveJobId;

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

  function resetWorkspace() {
    resetExportWorkspace();
    resetGradingQueue();
    clearActiveJob();
  }

  function navigate(nextView: AppView) {
    if (!connected && nextView !== "connect") return;
    if (nextView === "graderQueue") void loadGradingQueue();
    setView(nextView);
  }

  // Logged-out / connecting state: full-bleed login screen — no Rail, no shell chrome.
  if (view === "connect") {
    return (
      <div data-screen-label="connect">
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
            <ConnectView
              connecting={busy}
              deliveryMode={deliveryMode}
              error={error}
              onConnect={connectClassroom}
            />
          </>
        )}
        {apiOffline && !gateError ? <OfflinePill /> : null}
      </div>
    );
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
              acceptingSubmissionId={acceptingSubmissionId}
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
              accountEmail={auth?.email ?? null}
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
