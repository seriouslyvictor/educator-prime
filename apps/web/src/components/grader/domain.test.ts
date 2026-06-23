import { describe, expect, it } from "vitest";
import { classroomActivityUrl, scoreColor, scoreOf, studentLabel, withAuthUser } from "./domain";
import type { GradingJob, GradingSubmission } from "../../types";

function submission(overrides: Partial<GradingSubmission>): GradingSubmission {
  return {
    id: "submission-1",
    student_email: null,
    student_name: null,
    source_file_id: "file-1",
    source_name: "file.pdf",
    mime_type: "application/pdf",
    files: [],
    ai_score: null,
    confidence: null,
    final_score: null,
    feedback: null,
    reviewed: false,
    flag: null,
    error: null,
    classroom_submission_id: null,
    alternate_link: null,
    posted_to_classroom: false,
    posted_at: null,
    privacy_status: null,
    extraction_status: null,
    ai_attempt_status: null,
    error_retryable: false,
    ai_engine: null,
    ai_model: null,
    ai_safe_error: null,
    ai_flags: [],
    privacy_flags: [],
    ...overrides,
  };
}

describe("grader domain helpers", () => {
  it("resolves score and student fallbacks", () => {
    expect(scoreOf(submission({ final_score: 91, ai_score: 70 }))).toBe(91);
    expect(scoreOf(submission({ ai_score: 70 }))).toBe(70);
    expect(scoreOf(submission({}))).toBeNull();
    expect(studentLabel(submission({ student_name: "Ana Silva" }))).toBe("Ana Silva");
    expect(studentLabel(submission({ student_email: "ana@example.edu" }))).toBe("ana@example.edu");
    expect(studentLabel(submission({}))).toBe("Aluno desconhecido");
  });

  it("keeps the existing score color thresholds", () => {
    expect(scoreColor(null)).toBe("var(--muted-2)");
    expect(scoreColor(90)).toBe("var(--ink)");
    expect(scoreColor(70)).toBe("var(--warning)");
    expect(scoreColor(50)).toBe("var(--danger)");
  });

  it("builds the Classroom grading URL with base64-encoded IDs", () => {
    const job = {
      course_id: "794020742771",
      activity_id: "796411880885",
    } as GradingJob;

    // Classroom web routes need base64-encoded IDs; raw numeric IDs hang on an
    // endless loading screen. Lands on the teacher submissions grading view.
    expect(classroomActivityUrl(job)).toBe(
      "https://classroom.google.com/c/Nzk0MDIwNzQyNzcx/a/Nzk2NDExODgwODg1/submissions/by-status/and-sort-first-name/all/all",
    );
  });

  it("pins the Classroom URL to the signed-in account via authuser", () => {
    const job = {
      course_id: "794020742771",
      activity_id: "796411880885",
    } as GradingJob;

    expect(classroomActivityUrl(job, "teacher@school.edu.br")).toBe(
      "https://classroom.google.com/c/Nzk0MDIwNzQyNzcx/a/Nzk2NDExODgwODg1/submissions/by-status/and-sort-first-name/all/all?authuser=teacher%40school.edu.br",
    );
  });

  it("appends authuser without clobbering existing query params", () => {
    expect(withAuthUser("https://classroom.google.com/c/abc/details", "a@b.com")).toBe(
      "https://classroom.google.com/c/abc/details?authuser=a%40b.com",
    );
    expect(withAuthUser("https://x.test/p?foo=1", "a@b.com")).toBe(
      "https://x.test/p?foo=1&authuser=a%40b.com",
    );
    expect(withAuthUser("https://x.test/p", null)).toBe("https://x.test/p");
  });
});
