import { useMemo, useState } from "react";

import { ApiError, api, apiErrorFromUnknown } from "../lib/api";
import type { Activity, AppView, Course, GradingQueueItem, QueueAction } from "../types";

type UseGradingQueueOptions = {
  selectedCourse: Course | undefined;
  getActiveJobId: () => string | null;
  setView: (view: AppView) => void;
  setError: (error: ApiError | string | null) => void;
  setGraderBusy: (busy: boolean) => void;
  clearActiveJob: () => void;
};

function appError(caught: unknown, fallback: string): ApiError {
  return apiErrorFromUnknown(caught, fallback);
}

export function useGradingQueue({
  selectedCourse,
  getActiveJobId,
  setView,
  setError,
  setGraderBusy,
  clearActiveJob,
}: UseGradingQueueOptions) {
  const [selectedGradingItem, setSelectedGradingItem] = useState<GradingQueueItem | null>(null);
  const [gradingQueue, setGradingQueue] = useState<GradingQueueItem[]>([]);
  const [archivedQueue, setArchivedQueue] = useState<GradingQueueItem[]>([]);
  const [pendingQueue, setPendingQueue] = useState<GradingQueueItem[]>([]);
  const [gradingQueueLoading, setGradingQueueLoading] = useState(false);

  const gradingByActivity = useMemo(() => {
    const rows = new Map<string, GradingQueueItem>();
    for (const item of gradingQueue) {
      if (!selectedCourse || item.course_id === selectedCourse.id) {
        rows.set(item.activity_id, item);
      }
    }
    return rows;
  }, [gradingQueue, selectedCourse]);

  const queueItems = useMemo(() => {
    const serverActivityIds = new Set(gradingQueue.map((item) => item.activity_id));
    const pending = pendingQueue.filter((item) => !serverActivityIds.has(item.activity_id));
    return [...pending, ...gradingQueue];
  }, [gradingQueue, pendingQueue]);

  function resetGradingQueue() {
    setSelectedGradingItem(null);
    setGradingQueue([]);
    setPendingQueue([]);
  }

  function sendActivitiesToQueue(activitiesToSend: Activity[]) {
    if (!selectedCourse || activitiesToSend.length === 0) return;
    setPendingQueue((current) => {
      const seen = new Set(current.map((row) => row.activity_id));
      const additions = activitiesToSend
        .filter((activity) => !seen.has(activity.id))
        .map<GradingQueueItem>((activity) => ({
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
        }));
      return [...additions, ...current];
    });
    setView("graderQueue");
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
      const [activeItems, archivedItems, hiddenItems] = await Promise.all([
        api.gradingJobs("active"),
        api.gradingJobs("archived"),
        api.gradingJobs("hidden"),
      ]);
      setGradingQueue(activeItems);
      setArchivedQueue([...archivedItems, ...hiddenItems]);
    } catch {
      setGradingQueue([]);
      setArchivedQueue([]);
    } finally {
      setGradingQueueLoading(false);
    }
  }

  async function runQueueAction(action: QueueAction, items: GradingQueueItem[]) {
    if (items.length === 0) return;
    setGraderBusy(true);
    setError(null);
    const shouldIgnoreMissing = (caught: unknown) =>
      caught instanceof Error && /not found|404/i.test(caught.message);
    const freshPending: GradingQueueItem[] = [];
    try {
      if (action === "remove") {
        const pendingActivityIds = new Set(
          items.filter((item) => !item.latest_job_id).map((item) => item.activity_id),
        );
        if (pendingActivityIds.size > 0) {
          setPendingQueue((current) =>
            current.filter((item) => !pendingActivityIds.has(item.activity_id)),
          );
        }
      }

      for (const item of items) {
        if (!item.latest_job_id) continue;
        try {
          if (action === "remove" || action === "restart") {
            await api.deleteGradingJob(item.latest_job_id);
            if (action === "restart") {
              freshPending.push({
                course_id: item.course_id,
                course_name: item.course_name,
                activity_id: item.activity_id,
                activity_title: item.activity_title,
                due_label: item.due_label,
                submission_count: item.submission_count,
                status: "ready",
                latest_job_id: null,
                queue_state: "active",
                reviewed_submissions: 0,
                total_submissions: 0,
              });
            }
          } else if (action === "archive") {
            await api.archiveGradingJob(item.latest_job_id);
          } else if (action === "hide") {
            await api.hideGradingJob(item.latest_job_id);
          } else if (action === "restore") {
            await api.restoreGradingJob(item.latest_job_id);
          }
        } catch (caught) {
          if (!shouldIgnoreMissing(caught)) throw caught;
        }
      }

      if (freshPending.length > 0) {
        setPendingQueue((current) => {
          const activityIds = new Set(freshPending.map((item) => item.activity_id));
          return [...freshPending, ...current.filter((item) => !activityIds.has(item.activity_id))];
        });
      }

      const activeJobId = getActiveJobId();
      if (
        activeJobId &&
        items.some((item) => item.latest_job_id === activeJobId) &&
        action !== "restore"
      ) {
        clearActiveJob();
      }

      await loadGradingQueue();
    } catch (caught) {
      setError(appError(caught, "Falha ao gerenciar a fila de correção."));
    } finally {
      setGraderBusy(false);
    }
  }

  return {
    selectedGradingItem,
    setSelectedGradingItem,
    gradingQueue,
    archivedQueue,
    pendingQueue,
    setPendingQueue,
    gradingQueueLoading,
    gradingByActivity,
    queueItems,
    resetGradingQueue,
    sendActivitiesToQueue,
    findExistingJob,
    loadGradingQueue,
    runQueueAction,
  };
}
