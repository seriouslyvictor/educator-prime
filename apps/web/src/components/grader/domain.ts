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

export function classroomActivityUrl(job: GradingJob): string {
  return `https://classroom.google.com/c/${job.course_id}/a/${job.activity_id}/details`;
}
