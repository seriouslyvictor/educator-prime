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
    pending_vision: "aguardando extracao visual",
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

export function redactionLabel(category: string) {
  const labels: Record<string, string> = {
    name_visible: "Nome (na imagem)",
    face: "Rosto",
    id_document: "Documento",
    contact_info: "Contato (na imagem)",
    other_pii: "Outros dados pessoais",
    name: "Nome",
    cpf: "CPF",
    rg: "RG",
    email: "E-mail",
    phone: "Telefone",
    social: "Rede social",
  };
  return labels[category] ?? category.replaceAll("_", " ");
}

export function redactionSummary(counts?: Record<string, number> | null) {
  const entries = Object.entries(counts ?? {}).filter(([, count]) => count > 0);
  if (!entries.length) return "Nenhum";
  return entries
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, count]) => `${redactionLabel(category)} ×${count}`)
    .join(" · ");
}

export function safeStatusLabel(value?: string | null) {
  if (!value) return "";
  const labels: Record<string, string> = {
    api_unavailable: "IA indisponivel - tente novamente",
    api_rate_limited: "limite de requisicoes - tente novamente em instantes",
    api_timeout: "tempo esgotado na IA - tente novamente",
    api_connection: "falha de conexao com a IA - tente novamente",
    api_auth_failed: "autenticacao da IA falhou",
    context_window_exceeded: "entrega grande demais para a IA",
    content_blocked: "conteudo bloqueado pelo provedor",
    api_bad_request: "requisicao recusada pela IA",
    malformed_llm_response: "resposta invalida do modelo - tente novamente",
    llm_call_failed: "falha ao chamar a IA",
    vision_api_unavailable: "IA indisponivel na extracao - tente novamente",
    vision_api_rate_limited: "limite de requisicoes na extracao - tente novamente em instantes",
    vision_api_timeout: "tempo esgotado na extracao visual - tente novamente",
    vision_api_connection: "falha de conexao na extracao visual - tente novamente",
    vision_api_auth_failed: "autenticacao da IA falhou na extracao visual",
    vision_context_window_exceeded: "imagem/texto grande demais para a IA",
    vision_content_blocked: "imagem bloqueada pelo provedor",
    vision_api_bad_request: "requisicao de extracao recusada pela IA",
    vision_malformed_response: "resposta invalida da extracao visual - tente novamente",
    vision_llm_call_failed: "falha ao chamar a IA na extracao visual",
    vision_unreadable: "a IA nao conseguiu ler a imagem",
    local_preprocessing_failed: "falha ao preparar a imagem (nao foi enviada)",
    local_unsupported_image_format: "formato de imagem nao suportado (nao foi enviada)",
    local_image_too_large: "imagem grande demais (nao foi enviada)",
    cached_file_missing: "arquivo em cache nao encontrado (nao foi enviado)",
    privacy_blocked: "bloqueado por privacidade",
    unsupported_file_type: "tipo de arquivo não suportado",
    high_reidentification_risk: "alto risco de reidentificação",
    partial_redaction: "redação parcial",
    low_confidence: "baixa confiança",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

export function errorLayerLabel(value?: string | null) {
  if (!value) return "";
  if (value === "cached_file_missing" || value.startsWith("local_")) {
    return "Imagem nao saiu do computador";
  }
  if (
    value.startsWith("api_") ||
    value.startsWith("vision_api_") ||
    value === "malformed_llm_response" ||
    value === "vision_malformed_response"
  ) {
    return "Falha temporaria do provedor";
  }
  if (value.startsWith("vision_") || value === "content_blocked") {
    return "A IA recebeu e nao conseguiu concluir";
  }
  return "Requer revisao manual";
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
