/**
 * Pure helpers for grading progress state and job data transformations.
 *
 * All exports here are side-effect-free functions and shared types — no React,
 * no API calls, no browser globals. This makes them directly testable with Vitest.
 */

import type { GradingJob, GradingQueueItem, GradingSubmission, PrivacyAudit } from "../types";

// ---------------------------------------------------------------------------
// Shared domain types
// ---------------------------------------------------------------------------

export type GradingStreamPayload = {
  phase?: "audit" | "criteria" | "draft" | "outlier_review";
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

export type GradingInlineProgress = {
  phase: "audit" | "criteria" | "draft" | "outlier_review";
  processed: number;
  total: number;
  current: string;
  done: boolean;
  error: string | null;
};

// ---------------------------------------------------------------------------
// Job / submission helpers
// ---------------------------------------------------------------------------

/**
 * Merge an incoming draft submission into the current list.
 * An already-reviewed submission is never overwritten by a later draft.
 * If the submission is not found it is appended.
 */
export function mergeDraftSubmission(
  currentSubmissions: GradingSubmission[],
  incoming: GradingSubmission,
): GradingSubmission[] {
  let found = false;
  const submissions = currentSubmissions.map((row) => {
    if (row.id !== incoming.id) return row;
    found = true;
    return row.reviewed ? row : incoming;
  });
  if (!found) submissions.push(incoming);
  return submissions;
}

/**
 * Build the lightweight queue item the Setup screen needs from a full job — used
 * when resuming a not-yet-drafted ("ready") job back into the Setup/prepare screen.
 */
export function gradingItemFromJob(job: GradingJob): GradingQueueItem {
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
    graded_submissions: 0,
    ungraded_submissions: job.total_submissions,
    concluded: false,
  };
}

// ---------------------------------------------------------------------------
// Pure progress reducers
// ---------------------------------------------------------------------------

/**
 * Apply a streaming payload to produce a new GradingInlineProgress snapshot.
 * Handles both normal ticks and terminal error payloads — if `payload.error` is
 * set the result will have `done: true` and `error` populated.
 */
export function applyProgressPayload(
  current: GradingInlineProgress | null,
  payload: GradingStreamPayload,
  phase: GradingInlineProgress["phase"],
): GradingInlineProgress {
  const errorMessage = payload.error ?? null;
  return {
    phase: payload.phase ?? current?.phase ?? phase,
    processed: payload.processed ?? current?.processed ?? 0,
    total: payload.total ?? current?.total ?? 0,
    current: payload.current ?? current?.current ?? "",
    done: errorMessage !== null ? true : Boolean(payload.done),
    error: errorMessage,
  };
}

/**
 * Produce a "reconnecting…" progress snapshot while the stream client is
 * waiting to retry the EventSource connection.
 */
export function applyProgressReconnecting(
  current: GradingInlineProgress | null,
  phase: GradingInlineProgress["phase"],
  attempt: number,
): GradingInlineProgress {
  return {
    phase,
    processed: current?.processed ?? 0,
    total: current?.total ?? 0,
    current: `Reconectando... tentativa ${attempt}/3`,
    done: false,
    error: null,
  };
}

/**
 * Produce a terminal "exhausted reconnects" progress snapshot.
 */
export function applyProgressExhausted(
  current: GradingInlineProgress | null,
  phase: GradingInlineProgress["phase"],
  message: string,
): GradingInlineProgress {
  return {
    phase,
    processed: current?.processed ?? 0,
    total: current?.total ?? 0,
    current: current?.current ?? "",
    done: true,
    error: message,
  };
}
