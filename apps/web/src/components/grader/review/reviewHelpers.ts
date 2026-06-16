import type { GradingSubmission } from "../../../types";

export function initials(name: string | null | undefined, fallback: string): string {
  const source = (name ?? "").trim();
  if (!source) return fallback;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function isBlocked(submission: GradingSubmission | undefined): boolean {
  return Boolean(submission?.error) || submission?.ai_attempt_status === "blocked";
}

export function isVisualSubmission(submission: GradingSubmission): boolean {
  const files = submission.files?.length ? submission.files : [{ mime_type: submission.mime_type }];
  return files.some((file) => file.mime_type?.startsWith("image/"));
}
