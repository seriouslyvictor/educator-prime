import { useMemo, useState } from "react";

import { ApiError, api, apiErrorFromUnknown } from "../lib/api";
import { resolveError } from "../lib/errorCatalog";
import {
  exportJobToFolder,
  isFolderExportSupported,
  pickExportFolder,
} from "../lib/folder-export";
import { buildPreviewTree } from "../lib/preview-tree";
import type { ProgressLogItem } from "../components/ProgressView";
import type {
  Activity,
  AppView,
  Course,
  ExportJob,
  LocalExportHistoryItem,
} from "../types";

type UseExportWorkspaceOptions = {
  view: AppView;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  setError: (error: ApiError | string | null) => void;
  setView: (view: AppView) => void;
  loadGradingQueue: () => Promise<void>;
  addHistoryItem: (item: Omit<LocalExportHistoryItem, "id" | "completedAt">) => void;
  requestDrivePermission: () => boolean;
};

function appError(caught: unknown, fallback: string): ApiError {
  return apiErrorFromUnknown(caught, fallback);
}

function appErrorSummary(error: unknown): string {
  const entry = resolveError(error);
  return `${entry.title}: ${entry.body}`;
}

export function useExportWorkspace({
  view,
  busy,
  setBusy,
  setError,
  setView,
  loadGradingQueue,
  addHistoryItem,
  requestDrivePermission,
}: UseExportWorkspaceOptions) {
  const folderSupported = isFolderExportSupported();
  const deliveryMode: "folder" | "zip" = folderSupported ? "folder" : "zip";

  const [courses, setCourses] = useState<Course[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [selectedActivityIds, setSelectedActivityIds] = useState<string[]>([]);
  const [classQuery, setClassQuery] = useState("");
  const [activityQuery, setActivityQuery] = useState("");
  const [dryRunOpen, setDryRunOpen] = useState(false);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [lastResult, setLastResult] = useState<LocalExportHistoryItem | null>(null);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [progress, setProgress] = useState({ completed: 0, total: 0, currentPath: "" });
  const [progressLog, setProgressLog] = useState<ProgressLogItem[]>([]);

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

  function resetExportWorkspace() {
    setCourses([]);
    setActivities([]);
    setSelectedCourseId("");
    setSelectedActivityIds([]);
    setJob(null);
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
      setError(appError(caught, "Falha ao carregar atividades."));
    } finally {
      setActivitiesLoading(false);
    }
  }

  async function startExport(activityIds = selectedActivityIds) {
    if (!selectedCourse || activityIds.length === 0 || busy) return;
    if (!requestDrivePermission()) return;
    if (deliveryMode === "zip") {
      setError(
        new ApiError(
          0,
          "unsupported_browser",
          "Folder export is not available in this browser.",
        ),
      );
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

      const exportSummary = await exportJobToFolder(exportJob, root, (completed, total, currentPath) => {
        setProgress({ completed, total, currentPath });
        setProgressLog((current) => [
          ...current.slice(-80),
          {
            id: `${completed}-${currentPath}`,
            kind: currentPath.startsWith("Falhou:") ? "err" : "ok",
            text: currentPath,
          },
        ]);
      });

      const historyItem = {
        courseName: selectedCourse.name,
        activityCount: activityIds.length,
        fileCount: exportSummary.completed,
        failedFiles: exportSummary.failed,
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
      if (caught instanceof ApiError && caught.code === "google_permission_required") {
        requestDrivePermission();
        return;
      }
      const exportError = appError(caught, "Falha na exportaÃ§Ã£o.");
      setError(exportError);
      setProgressLog((current) => [
        ...current,
        { id: `error-${Date.now()}`, kind: "err", text: appErrorSummary(exportError) },
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

  function previewActivity(activity: Activity) {
    setSelectedActivityIds([activity.id]);
    setJob(null);
    setDryRunOpen(true);
  }

  return {
    folderSupported,
    deliveryMode,
    courses,
    activities,
    selectedCourseId,
    selectedActivityIds,
    classQuery,
    activityQuery,
    dryRunOpen,
    job,
    lastResult,
    activitiesLoading,
    progress,
    progressLog,
    selectedCourse,
    selectedActivities,
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
  };
}
