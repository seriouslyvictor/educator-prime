import { expect, test } from "@playwright/test";

function submission(id: string, studentName: string) {
  return {
    id,
    student_email: null,
    student_name: studentName,
    source_file_id: `${id}-file`,
    source_name: `${studentName}.txt`,
    mime_type: "text/plain",
    files: [{ source_file_id: `${id}-file`, source_name: `${studentName}.txt`, mime_type: "text/plain" }],
    ai_score: 88,
    confidence: 0.91,
    final_score: 88,
    feedback: `Feedback de ${studentName}`,
    reviewed: false,
    flag: null,
    error: null,
    classroom_submission_id: id,
    alternate_link: null,
    posted_to_classroom: false,
    posted_at: null,
    privacy_status: null,
    extraction_status: null,
    ai_attempt_status: "succeeded",
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

test("retries a failed text submission preview", async ({ page }) => {
  const readySubmission = submission("sub-1", "Ana");
  const job = {
    id: "job-preview",
    course_id: "course-preview",
    course_name: "Turma Preview",
    activity_id: "activity-preview",
    activity_title: "Atividade Preview",
    rubric_mode: "brief",
    teacher_loop: "approve",
    grade_scope: "all",
    rubric_text: "Corrija com objetividade.",
    include_visual_submissions: false,
    queue_state: "active",
    status: "ready",
    total_submissions: 1,
    reviewed_submissions: 0,
    flagged_submissions: 0,
    criteria: [],
    submissions: [],
    cache_files: [],
  };
  const reviewingJob = { ...job, status: "reviewing", submissions: [readySubmission] };
  let previewRequests = 0;
  let allowPreviewRecovery = false;

  await page.route("**/api/auth/me", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ signed_in: true, identity_scopes: true, classroom_scopes: true, drive_scopes: true, email: "teacher@example.edu", name: "Teacher", picture: null, provider: "mock", is_admin: false }) }));
  await page.route("**/api/grading/health**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ engine: "mock", ready: true, status: "mock", model: null, provider: "mock", missing_keys: [], detail: "ok", probed: false, probe_ok: null }) }));
  await page.route("**/api/courses", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "course-preview", name: "Turma Preview", section: null, course_state: "ACTIVE" }]) }));
  await page.route("**/api/courses/course-preview/activities**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "activity-preview", course_id: "course-preview", title: "Atividade Preview", work_type: "ASSIGNMENT", state: "PUBLISHED", due_label: null, total_submissions: 1, graded_submissions: 0, ungraded_submissions: 1, concluded: false }]) }));
  await page.route("**/api/grading/jobs?state=active", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs?state=archived", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/queue**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(job) }));
  await page.route("**/api/grading/jobs/job-preview/privacy-audit/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "audit", processed: 1, total: 1, current: "ok", done: true, summary: { id: "audit-1", job_id: "job-preview", status: "completed", total_files: 1, passed_files: 1, redacted_files: 0, blocked_files: 0, high_risk_files: 0, created_at: "2026-06-24T00:00:00Z", updated_at: "2026-06-24T00:00:00Z", rows: [] } }) }));
  await page.route("**/api/grading/jobs/job-preview/draft/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "draft", processed: 0, total: 1, current: "queued", done: false, queued: [submission("sub-1", "Ana")] }) + sse({ phase: "draft", processed: 1, total: 1, current: "Ana", done: false, submission: readySubmission }) + sse({ phase: "draft", processed: 1, total: 1, current: "done", done: true, job: reviewingJob }) }));
  await page.route("**/api/grading/jobs/job-preview/submissions/sub-1/preview**", (route) => {
    previewRequests += 1;
    if (!allowPreviewRecovery) {
      return route.fulfill({ status: 500, contentType: "text/plain", body: "preview failed" });
    }
    return route.fulfill({ contentType: "text/plain", body: "Recovered preview content" });
  });

  await page.goto("/");
  await expect(page.locator("[data-screen-label]").first()).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  await page.getByRole("button", { name: "Turmas" }).click();
  await page.getByText("Atividade Preview").click();
  await page.getByRole("button", { name: "Corrigir com IA" }).last().click();
  await page.getByRole("tab", { name: /Orienta??o simples|Orienta/ }).click();
  await page.getByRole("button", { name: /Auditar e preparar/ }).click();
  await page.getByRole("button", { name: /rascunhos? e revisar/ }).click();

  await expect(page.getByRole("button", { name: /Tentar novamente/ })).toBeVisible();
  allowPreviewRecovery = true;
  await page.getByRole("button", { name: /Tentar novamente/ }).click();
  await expect(page.getByText("Recovered preview content")).toBeVisible();
  expect(previewRequests).toBeGreaterThanOrEqual(2);
});

test("retries a failed image submission preview", async ({ page }) => {
  const readySubmission = {
    ...submission("sub-1", "Ana"),
    source_name: "Ana.png",
    mime_type: "image/png",
    files: [{ source_file_id: "sub-1-file", source_name: "Ana.png", mime_type: "image/png" }],
  };
  const job = {
    id: "job-preview",
    course_id: "course-preview",
    course_name: "Turma Preview",
    activity_id: "activity-preview",
    activity_title: "Atividade Preview",
    rubric_mode: "brief",
    teacher_loop: "approve",
    grade_scope: "all",
    rubric_text: "Corrija com objetividade.",
    include_visual_submissions: false,
    queue_state: "active",
    status: "ready",
    total_submissions: 1,
    reviewed_submissions: 0,
    flagged_submissions: 0,
    criteria: [],
    submissions: [],
    cache_files: [],
  };
  const reviewingJob = { ...job, status: "reviewing", submissions: [readySubmission] };
  let previewRequests = 0;
  let allowPreviewRecovery = false;

  await page.route("**/api/auth/me", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ signed_in: true, identity_scopes: true, classroom_scopes: true, drive_scopes: true, email: "teacher@example.edu", name: "Teacher", picture: null, provider: "mock", is_admin: false }) }));
  await page.route("**/api/grading/health**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ engine: "mock", ready: true, status: "mock", model: null, provider: "mock", missing_keys: [], detail: "ok", probed: false, probe_ok: null }) }));
  await page.route("**/api/courses", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "course-preview", name: "Turma Preview", section: null, course_state: "ACTIVE" }]) }));
  await page.route("**/api/courses/course-preview/activities**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "activity-preview", course_id: "course-preview", title: "Atividade Preview", work_type: "ASSIGNMENT", state: "PUBLISHED", due_label: null, total_submissions: 1, graded_submissions: 0, ungraded_submissions: 1, concluded: false }]) }));
  await page.route("**/api/grading/jobs?state=active", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs?state=archived", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/queue**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(job) }));
  await page.route("**/api/grading/jobs/job-preview/privacy-audit/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "audit", processed: 1, total: 1, current: "ok", done: true, summary: { id: "audit-1", job_id: "job-preview", status: "completed", total_files: 1, passed_files: 1, redacted_files: 0, blocked_files: 0, high_risk_files: 0, created_at: "2026-06-24T00:00:00Z", updated_at: "2026-06-24T00:00:00Z", rows: [] } }) }));
  await page.route("**/api/grading/jobs/job-preview/draft/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "draft", processed: 0, total: 1, current: "queued", done: false, queued: [{ ...submission("sub-1", "Ana"), source_name: "Ana.png", mime_type: "image/png", files: [{ source_file_id: "sub-1-file", source_name: "Ana.png", mime_type: "image/png" }] }] }) + sse({ phase: "draft", processed: 1, total: 1, current: "Ana", done: false, submission: readySubmission }) + sse({ phase: "draft", processed: 1, total: 1, current: "done", done: true, job: reviewingJob }) }));
  await page.route("**/api/grading/jobs/job-preview/submissions/sub-1/preview**", (route) => {
    previewRequests += 1;
    if (!allowPreviewRecovery) {
      return route.fulfill({ status: 500, contentType: "text/plain", body: "preview failed" });
    }
    // Return a minimal 1x1 PNG for recovery
    const pngBytes = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");
    return route.fulfill({ status: 200, contentType: "image/png", body: pngBytes });
  });

  await page.goto("/");
  await expect(page.locator("[data-screen-label]").first()).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  await page.getByRole("button", { name: "Turmas" }).click();
  await page.getByText("Atividade Preview").click();
  await page.getByRole("button", { name: "Corrigir com IA" }).last().click();
  await page.getByRole("tab", { name: /Orienta??o simples|Orienta/ }).click();
  await page.getByRole("button", { name: /Auditar e preparar/ }).click();
  await page.getByRole("button", { name: /rascunhos? e revisar/ }).click();

  await expect(page.getByRole("button", { name: /Tentar novamente/ })).toBeVisible();
  allowPreviewRecovery = true;
  await page.getByRole("button", { name: /Tentar novamente/ }).click();
  await expect(page.locator("img.preview-image")).toBeVisible();
  expect(previewRequests).toBeGreaterThanOrEqual(2);
});

test("keeps a loaded PDF preview visible past the load timeout", async ({ page }) => {
  const readySubmission = {
    ...submission("sub-1", "Ana"),
    source_name: "Ana.pdf",
    mime_type: "application/pdf",
    files: [{ source_file_id: "sub-1-file", source_name: "Ana.pdf", mime_type: "application/pdf" }],
  };
  const job = {
    id: "job-preview",
    course_id: "course-preview",
    course_name: "Turma Preview",
    activity_id: "activity-preview",
    activity_title: "Atividade Preview",
    rubric_mode: "brief",
    teacher_loop: "approve",
    grade_scope: "all",
    rubric_text: "Corrija com objetividade.",
    include_visual_submissions: false,
    queue_state: "active",
    status: "ready",
    total_submissions: 1,
    reviewed_submissions: 0,
    flagged_submissions: 0,
    criteria: [],
    submissions: [],
    cache_files: [],
  };
  const reviewingJob = { ...job, status: "reviewing", submissions: [readySubmission] };

  // Minimal valid single-page PDF (base64-encoded, correct xref byte offsets) so the iframe fires onLoad
  const minimalPdf = Buffer.from(
    "JVBERi0xLjQKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5kb2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPJ4KZW5kb2JqCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCA2MTIgNzkyXQo+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDQKL1Jvb3QgMSAwIFIKPj4Kc3RhcnR4cmVmCjE5MAolJUVPRg==",
    "base64"
  );

  await page.route("**/api/auth/me", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ signed_in: true, identity_scopes: true, classroom_scopes: true, drive_scopes: true, email: "teacher@example.edu", name: "Teacher", picture: null, provider: "mock", is_admin: false }) }));
  await page.route("**/api/grading/health**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ engine: "mock", ready: true, status: "mock", model: null, provider: "mock", missing_keys: [], detail: "ok", probed: false, probe_ok: null }) }));
  await page.route("**/api/courses", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "course-preview", name: "Turma Preview", section: null, course_state: "ACTIVE" }]) }));
  await page.route("**/api/courses/course-preview/activities**", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: "activity-preview", course_id: "course-preview", title: "Atividade Preview", work_type: "ASSIGNMENT", state: "PUBLISHED", due_label: null, total_submissions: 1, graded_submissions: 0, ungraded_submissions: 1, concluded: false }]) }));
  await page.route("**/api/grading/jobs?state=active", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs?state=archived", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/queue**", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/api/grading/jobs", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(job) }));
  await page.route("**/api/grading/jobs/job-preview/privacy-audit/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "audit", processed: 1, total: 1, current: "ok", done: true, summary: { id: "audit-1", job_id: "job-preview", status: "completed", total_files: 1, passed_files: 1, redacted_files: 0, blocked_files: 0, high_risk_files: 0, created_at: "2026-06-24T00:00:00Z", updated_at: "2026-06-24T00:00:00Z", rows: [] } }) }));
  await page.route("**/api/grading/jobs/job-preview/draft/stream", (route) => route.fulfill({ contentType: "text/event-stream", body: sse({ phase: "draft", processed: 0, total: 1, current: "queued", done: false, queued: [{ ...submission("sub-1", "Ana"), source_name: "Ana.pdf", mime_type: "application/pdf", files: [{ source_file_id: "sub-1-file", source_name: "Ana.pdf", mime_type: "application/pdf" }] }] }) + sse({ phase: "draft", processed: 1, total: 1, current: "Ana", done: false, submission: readySubmission }) + sse({ phase: "draft", processed: 1, total: 1, current: "done", done: true, job: reviewingJob }) }));
  await page.route("**/api/grading/jobs/job-preview/submissions/sub-1/preview**", (route) => {
    return route.fulfill({ status: 200, contentType: "application/pdf", body: minimalPdf });
  });

  await page.goto("/");
  await expect(page.locator("[data-screen-label]").first()).toHaveAttribute("data-screen-label", "workspace", { timeout: 15_000 });
  await page.getByRole("button", { name: "Turmas" }).click();
  await page.getByText("Atividade Preview").click();
  await page.getByRole("button", { name: "Corrigir com IA" }).last().click();
  await page.getByRole("tab", { name: /Orienta??o simples|Orienta/ }).click();
  await page.getByRole("button", { name: /Auditar e preparar/ }).click();
  await page.getByRole("button", { name: /rascunhos? e revisar/ }).click();

  // The iframe should be visible after the PDF mounts
  const iframe = page.locator("iframe.preview-frame");
  await expect(iframe).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Não foi possível carregar a previsualização.")).not.toBeVisible();

  // Headless Chromium's PDF plugin does not fire the iframe load event, so we
  // deliver the load signal directly to exercise the component's `loaded` guard.
  await page.evaluate(() => {
    const f = document.querySelector("iframe.preview-frame");
    if (f) f.dispatchEvent(new Event("load"));
  });

  // Wait past the 8-second guard — before the loaded-flag fix the error state would appear here
  await page.waitForTimeout(9000);

  // Regression check: the iframe should still be visible and no error shown
  await expect(iframe).toBeVisible();
  await expect(page.getByText("Não foi possível carregar a previsualização.")).not.toBeVisible();
});
