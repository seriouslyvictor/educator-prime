import { expect, test } from "@playwright/test";

const job = {
  id: "job-live",
  course_id: "course-live",
  course_name: "Turma Live",
  activity_id: "activity-live",
  activity_title: "Atividade Live",
  rubric_mode: "brief",
  teacher_loop: "approve",
  grade_scope: "all",
  rubric_text: "Corrija com objetividade.",
  include_visual_submissions: false,
  queue_state: "active",
  status: "ready",
  total_submissions: 2,
  reviewed_submissions: 0,
  flagged_submissions: 0,
  criteria: [],
  submissions: [],
  cache_files: [],
};

const queued = [submission("sub-1", "Ana", null), submission("sub-2", "Bruno", null)];
const firstDraft = submission("sub-1", "Ana", 88);

function submission(id: string, studentName: string, score: number | null) {
  return {
    id,
    student_email: null,
    student_name: studentName,
    source_file_id: `${id}-file`,
    source_name: `${studentName}.txt`,
    mime_type: "text/plain",
    files: [{ source_file_id: `${id}-file`, source_name: `${studentName}.txt`, mime_type: "text/plain" }],
    ai_score: score,
    confidence: score == null ? null : 0.91,
    final_score: score,
    feedback: score == null ? null : `Feedback de ${studentName}`,
    reviewed: false,
    flag: null,
    error: null,
    classroom_submission_id: id,
    alternate_link: null,
    posted_to_classroom: false,
    posted_at: null,
    privacy_status: null,
    extraction_status: null,
    ai_attempt_status: score == null ? null : "succeeded",
    error_retryable: false,
    ai_engine: null,
    ai_model: null,
    ai_safe_error: null,
    ai_flags: [],
    privacy_flags: [],
  };
}

function sse(payload: unknown) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

test("allows accepting a ready draft while the draft stream is still running", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      signed_in: true,
      identity_scopes: true,
      classroom_scopes: true,
      drive_scopes: true,
      email: "teacher@example.edu",
      name: "Teacher",
      picture: null,
      provider: "mock",
      is_admin: false,
    }),
  }));
  await page.route("**/api/grading/health**", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ engine: "mock", ready: true, status: "mock", model: null, provider: "mock", missing_keys: [], detail: "ok", probed: false, probe_ok: null }),
  }));
  await page.route("**/api/courses", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify([{ id: "course-live", name: "Turma Live", section: null, course_state: "ACTIVE" }]),
  }));
  await page.route("**/api/courses/course-live/activities**", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify([{ id: "activity-live", course_id: "course-live", title: "Atividade Live", work_type: "ASSIGNMENT", state: "PUBLISHED", due_label: null, total_submissions: 2, graded_submissions: 0, ungraded_submissions: 2, concluded: false }]),
  }));
  await page.route("**/api/grading/jobs?state=active", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs?state=archived", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/queue**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(job) }));
  await page.route("**/api/grading/jobs/job-live/privacy-audit/stream", (route) => route.fulfill({
    contentType: "text/event-stream",
    body: sse({ phase: "audit", processed: 2, total: 2, current: "ok", done: true, summary: { id: "audit-1", job_id: "job-live", status: "completed", total_files: 2, passed_files: 2, redacted_files: 0, blocked_files: 0, high_risk_files: 0, created_at: "2026-06-24T00:00:00Z", updated_at: "2026-06-24T00:00:00Z", rows: [] } }),
  }));
  await page.route("**/api/grading/jobs/job-live/draft/stream", (route) => route.fulfill({
    contentType: "text/event-stream",
    body:
      sse({ phase: "draft", processed: 0, total: 2, current: "queued", done: false, queued }) +
      sse({ phase: "draft", processed: 1, total: 2, current: "Ana", done: false, submission: firstDraft }) +
      sse({ phase: "draft", processed: 1, total: 2, current: "Bruno", done: false, drafting_id: "sub-2" }),
  }));

  await page.goto("/");
  await expect(page.locator("[data-screen-label]").first()).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  await page.getByRole("button", { name: "Turmas" }).click();
  await page.getByText("Atividade Live").click();
  await page.getByRole("button", { name: "Corrigir com IA" }).last().click();
  await page.getByRole("tab", { name: /Orienta??o simples|Orienta/ }).click();
  await page.getByRole("button", { name: /Auditar e preparar/ }).click();
  await page.getByRole("button", { name: /Gerar 2 rascunhos e revisar/ }).click();

  await expect(page.getByText("Gerando rascunhos da IA")).toBeVisible();
  await expect(page.locator(".aside-summary", { hasText: "Feedback de Ana" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Aceitar/ })).toBeEnabled();
});
