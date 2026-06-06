import type { GradingSubmission } from "../../types";

export function privacyLabel(status?: string | null) {
  if (!status) return "Não verificado";
  const labels: Record<string, string> = {
    clean: "limpo",
    redacted: "redigido",
    partial_redaction: "redação parcial",
    high_reidentification_risk: "alto risco de reidentificação",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function extractionLabel(status?: string | null) {
  if (!status) return "Pendente";
  const labels: Record<string, string> = {
    supported: "suportado",
    degraded: "degradado",
    unsupported: "não suportado",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function attemptLabel(status?: string | null) {
  if (!status) return "Pendente";
  const labels: Record<string, string> = {
    pending: "pendente",
    completed: "concluído",
    blocked: "bloqueado",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function safeStatusLabel(value?: string | null) {
  if (!value) return "";
  const labels: Record<string, string> = {
    privacy_blocked: "bloqueado por privacidade",
    unsupported_file_type: "tipo de arquivo não suportado",
    high_reidentification_risk: "alto risco de reidentificação",
    partial_redaction: "redação parcial",
    low_confidence: "baixa confiança",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

export function privacyTone(submission?: GradingSubmission) {
  if (!submission?.privacy_status) return "neutral";
  if (submission.privacy_status === "clean") return "ok";
  if (submission.privacy_status === "redacted") return "warn";
  return "danger";
}

export function extractionTone(submission?: GradingSubmission) {
  if (!submission?.extraction_status) return "neutral";
  if (submission.extraction_status === "supported") return "ok";
  if (submission.extraction_status === "degraded") return "warn";
  return "danger";
}

export function attemptTone(submission?: GradingSubmission) {
  if (!submission?.ai_attempt_status) return "neutral";
  if (submission.ai_attempt_status === "completed") return "ok";
  if (submission.ai_attempt_status === "blocked") return "danger";
  return "warn";
}

export function statusTone(submission: GradingSubmission) {
  if (submission.error || submission.ai_attempt_status === "blocked") return "danger";
  if (submission.flag || submission.privacy_status === "redacted" || submission.extraction_status === "degraded") {
    return "warn";
  }
  return "ok";
}
