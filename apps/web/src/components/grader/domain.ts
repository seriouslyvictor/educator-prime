import type { GradingJob, GradingSubmission } from "../../types";

export function scoreOf(submission: GradingSubmission): number | null {
  return submission.final_score ?? submission.ai_score ?? null;
}

export function studentLabel(submission: GradingSubmission): string {
  return submission.student_name ?? submission.student_email ?? "Aluno desconhecido";
}

export function scoreColor(g: number | null): string {
  if (g == null) return "var(--muted-2)";
  return g >= 85 ? "var(--ink)" : g >= 65 ? "var(--warning)" : "var(--danger)";
}

// Classroom web URLs use base64-encoded IDs, not the raw numeric API IDs.
// Passing the raw numeric IDs (e.g. /c/794020742771/a/.../details) makes
// Classroom hang on an endless loading screen.
function encodeClassroomId(id: string): string {
  return btoa(id).replace(/=+$/, "");
}

export function classroomActivityUrl(job: GradingJob): string {
  const course = encodeClassroomId(job.course_id);
  const activity = encodeClassroomId(job.activity_id);
  // Land on the teacher's submissions grading view (where feedback is pasted),
  // not /details which is the read-only stream card.
  return `https://classroom.google.com/u/0/c/${course}/a/${activity}/submissions/by-status/and-sort-first-name/all/all`;
}
