import { describe, expect, it } from "vitest";

import type { GradingSubmission } from "../types";
import {
  applyProgressExhausted,
  applyProgressPayload,
  applyProgressReconnecting,
  gradingItemFromJob,
  mergeDraftSubmission,
} from "./gradingProgress";
import type { GradingInlineProgress, GradingStreamPayload } from "./gradingProgress";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseSubmission: GradingSubmission = {
  id: "sub-1",
  student_email: null,
  student_name: "Ana",
  source_file_id: "file-1",
  source_name: "work.txt",
  mime_type: "text/plain",
  files: [],
  ai_score: 80,
  confidence: 0.9,
  final_score: 90,
  feedback: "Reviewed feedback",
  reviewed: true,
  flag: null,
  error: null,
  error_retryable: false,
  classroom_submission_id: null,
  privacy_status: null,
  extraction_status: null,
  ai_attempt_status: "succeeded",
  ai_engine: null,
  ai_model: null,
  ai_safe_error: null,
  ai_flags: [],
  privacy_flags: [],
  alternate_link: null,
  posted_to_classroom: false,
  posted_at: null,
};

const baseProgress: GradingInlineProgress = {
  phase: "draft",
  processed: 5,
  total: 10,
  current: "Avaliando...",
  done: false,
  error: null,
};

// ---------------------------------------------------------------------------
// mergeDraftSubmission
// ---------------------------------------------------------------------------

describe("mergeDraftSubmission", () => {
  it("does not overwrite an already-reviewed submission when a late draft arrives", () => {
    const lateDraft: GradingSubmission = {
      ...baseSubmission,
      ai_score: 70,
      final_score: 70,
      feedback: "Late draft feedback",
      reviewed: false,
    };

    const merged = mergeDraftSubmission([baseSubmission], lateDraft);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({
      id: "sub-1",
      reviewed: true,
      final_score: 90,
      feedback: "Reviewed feedback",
    });
  });

  it("replaces an unreviewed submission with a new draft", () => {
    const unreviewed: GradingSubmission = {
      ...baseSubmission,
      ai_score: 60,
      final_score: 60,
      feedback: "Draft feedback",
      reviewed: false,
    };
    const newDraft: GradingSubmission = {
      ...baseSubmission,
      ai_score: 75,
      final_score: 75,
      feedback: "Updated draft feedback",
      reviewed: false,
    };

    const merged = mergeDraftSubmission([unreviewed], newDraft);

    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ ai_score: 75, feedback: "Updated draft feedback" });
  });

  it("appends a submission not found in the current list", () => {
    const newSub: GradingSubmission = {
      ...baseSubmission,
      id: "sub-2",
      student_name: "Bruno",
      reviewed: false,
    };

    const merged = mergeDraftSubmission([baseSubmission], newSub);

    expect(merged).toHaveLength(2);
    expect(merged[1]).toMatchObject({ id: "sub-2", student_name: "Bruno" });
  });

  it("does not duplicate an existing submission", () => {
    const sameSub: GradingSubmission = { ...baseSubmission, reviewed: false };

    const merged = mergeDraftSubmission([baseSubmission], sameSub);

    expect(merged).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// gradingItemFromJob (type-shape check only — no server round-trip)
// ---------------------------------------------------------------------------

describe("gradingItemFromJob", () => {
  it("maps required job fields to the queue item shape", () => {
    const job = {
      id: "job-1",
      course_id: "course-1",
      course_name: "Matemática",
      activity_id: "act-1",
      activity_title: "Tarefa 1",
      total_submissions: 20,
      reviewed_submissions: 5,
      flagged_submissions: 0,
      graded_submissions: 5,
      status: "ready" as const,
      queue_state: "active" as const,
      rubric_mode: "manual" as const,
      teacher_loop: "off" as const,
      rubric_text: "",
      include_visual_submissions: false,
      grade_scope: "all" as const,
      submissions: [],
      created_at: "",
      updated_at: "",
    };

    // @ts-expect-error — GradingJob has more fields; we provide a structural subset
    const item = gradingItemFromJob(job);

    expect(item).toMatchObject({
      course_id: "course-1",
      activity_id: "act-1",
      total_submissions: 20,
      reviewed_submissions: 5,
      latest_job_id: "job-1",
      due_label: null,
      concluded: false,
      graded_submissions: 0,
      ungraded_submissions: 20,
    });
  });
});

// ---------------------------------------------------------------------------
// applyProgressPayload
// ---------------------------------------------------------------------------

describe("applyProgressPayload", () => {
  it("merges a normal progress tick into current state", () => {
    const payload: GradingStreamPayload = { processed: 7, total: 10, current: "Corrigindo..." };

    const next = applyProgressPayload(baseProgress, payload, "draft");

    expect(next).toMatchObject({ processed: 7, total: 10, current: "Corrigindo...", done: false, error: null });
  });

  it("marks done when payload.done is true", () => {
    const payload: GradingStreamPayload = { processed: 10, total: 10, done: true };

    const next = applyProgressPayload(baseProgress, payload, "draft");

    expect(next.done).toBe(true);
    expect(next.error).toBeNull();
  });

  it("sets done and error when payload carries an error", () => {
    const payload: GradingStreamPayload = { error: "Algo deu errado" };

    const next = applyProgressPayload(baseProgress, payload, "draft");

    expect(next.done).toBe(true);
    expect(next.error).toBe("Algo deu errado");
  });

  it("falls back to current state values when payload fields are absent", () => {
    const next = applyProgressPayload(baseProgress, {}, "audit");

    // phase falls back to current.phase, not the passed-in "audit"
    expect(next.phase).toBe("draft");
    expect(next.processed).toBe(5);
    expect(next.total).toBe(10);
    expect(next.current).toBe("Avaliando...");
  });

  it("falls back to safe defaults when current is null", () => {
    const next = applyProgressPayload(null, {}, "audit");

    expect(next.phase).toBe("audit");
    expect(next.processed).toBe(0);
    expect(next.total).toBe(0);
    expect(next.current).toBe("");
  });
});

// ---------------------------------------------------------------------------
// applyProgressReconnecting
// ---------------------------------------------------------------------------

describe("applyProgressReconnecting", () => {
  it("produces a reconnecting message with the attempt counter", () => {
    const next = applyProgressReconnecting(baseProgress, "draft", 2);

    expect(next).toMatchObject({
      phase: "draft",
      processed: 5,
      total: 10,
      current: "Reconectando... tentativa 2/3",
      done: false,
      error: null,
    });
  });

  it("falls back to zeros when current is null", () => {
    const next = applyProgressReconnecting(null, "audit", 1);

    expect(next.processed).toBe(0);
    expect(next.total).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// applyProgressExhausted
// ---------------------------------------------------------------------------

describe("applyProgressExhausted", () => {
  it("marks done with the exhausted error message", () => {
    const message = "O processamento foi interrompido, mas pode continuar de onde parou.";

    const next = applyProgressExhausted(baseProgress, "audit", message);

    expect(next).toMatchObject({
      phase: "audit",
      done: true,
      error: message,
      processed: 5,
      total: 10,
      current: "Avaliando...", // preserved from current
    });
  });

  it("falls back to empty string for current when current is null", () => {
    const next = applyProgressExhausted(null, "draft", "erro");

    expect(next.current).toBe("");
    expect(next.processed).toBe(0);
  });
});
