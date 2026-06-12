import { ApiError } from "./api";
import type { IconName } from "../components/icons";

export type ErrorEntry = {
  tier: "gate" | "banner";
  tone: "info" | "warning" | "danger";
  icon: IconName;
  title: string;
  body: string;
  action?: { label: string; kind: "retry" | "reconnect-google" | "reload" | "none" };
  adminHint?: boolean;
  technicalDetail?: string;
};

const entries: Record<string, Omit<ErrorEntry, "technicalDetail">> = {
  not_signed_in: {
    tier: "gate",
    tone: "info",
    icon: "lock",
    title: "Entre novamente",
    body: "Sua sessão não está ativa. Conecte sua conta Google escolar para continuar.",
    action: { label: "Conectar Google", kind: "reconnect-google" },
  },
  session_expired: {
    tier: "gate",
    tone: "info",
    icon: "lock",
    title: "Sessão expirada",
    body: "Sua sessão do app expirou. Entre novamente para continuar de onde parou.",
    action: { label: "Conectar Google", kind: "reconnect-google" },
  },
  google_session_missing: {
    tier: "gate",
    tone: "info",
    icon: "shield",
    title: "Reconecte o Google",
    body: "A autorização salva não foi encontrada. Reconecte sua conta Google escolar para continuar.",
    action: { label: "Reconectar Google", kind: "reconnect-google" },
  },
  google_session_expired: {
    tier: "gate",
    tone: "info",
    icon: "shield",
    title: "Sua conexão com o Google expirou",
    body: "Isso é normal e acontece toda semana no modo de teste. Reconecte para continuar.",
    action: { label: "Reconectar Google", kind: "reconnect-google" },
  },
  google_auth_denied: {
    tier: "gate",
    tone: "warning",
    icon: "shield",
    title: "O Google recusou a autorização",
    body: "Reconecte a conta e marque todas as permissões solicitadas na tela do Google.",
    action: { label: "Reconectar Google", kind: "reconnect-google" },
  },
  oauth_not_configured: {
    tier: "gate",
    tone: "danger",
    icon: "settings",
    title: "Login do Google não configurado",
    body: "O app precisa de configuração administrativa antes de conectar contas Google.",
    action: { label: "Tentar novamente", kind: "retry" },
    adminHint: true,
  },
  google_rate_limited: {
    tier: "banner",
    tone: "warning",
    icon: "triangleAlert",
    title: "O Google limitou as requisições",
    body: "Aguarde um minuto e tente de novo. Seus dados já carregados continuam disponíveis.",
    action: { label: "Tentar novamente", kind: "retry" },
  },
  google_unavailable: {
    tier: "banner",
    tone: "warning",
    icon: "triangleAlert",
    title: "Google Classroom instável",
    body: "O Google não respondeu agora. Aguarde um pouco e tente novamente.",
    action: { label: "Tentar novamente", kind: "retry" },
  },
  llm_not_configured: {
    tier: "banner",
    tone: "danger",
    icon: "settings",
    title: "Correção por IA indisponível",
    body: "A chave do provedor de IA não está configurada. Avise o administrador.",
    action: { label: "Tentar novamente", kind: "retry" },
    adminHint: true,
  },
  api_budget_exhausted: {
    tier: "banner",
    tone: "danger",
    icon: "settings",
    title: "Créditos da IA esgotados",
    body: "A correção por IA não pode continuar até o administrador ajustar os créditos.",
    adminHint: true,
  },
  busy_retry: {
    tier: "banner",
    tone: "warning",
    icon: "refresh",
    title: "Servidor ocupado",
    body: "O servidor está processando outra operação. Tente novamente em alguns segundos.",
    action: { label: "Tentar novamente", kind: "retry" },
  },
  unreachable: {
    tier: "gate",
    tone: "danger",
    icon: "alertCircle",
    title: "O servidor não respondeu",
    body: "Verifique sua internet ou tente novamente em alguns minutos.",
    action: { label: "Tentar novamente", kind: "retry" },
  },
  unsupported_browser: {
    tier: "banner",
    tone: "warning",
    icon: "download",
    title: "Use Chrome ou Edge para exportar",
    body: "Este navegador ainda não consegue salvar os arquivos direto em uma pasta.",
    action: { label: "Entendi", kind: "none" },
  },
  version_skew: {
    tier: "banner",
    tone: "info",
    icon: "refresh",
    title: "Nova versão disponível",
    body: "Recarregue a página para usar a versão mais recente do app.",
    action: { label: "Recarregar", kind: "reload" },
  },
};

export function resolveError(err: unknown): ErrorEntry {
  const apiError = err instanceof ApiError ? err : null;
  const code = apiError?.code;
  const entry =
    (code ? entries[code] : undefined) ??
    (apiError?.status === 401 ? entries.session_expired : undefined) ??
    (apiError?.status === 503 ? entries.busy_retry : undefined) ??
    genericEntry;
  return {
    ...entry,
    technicalDetail: apiError?.message,
  };
}

const genericEntry: Omit<ErrorEntry, "technicalDetail"> = {
  tier: "banner",
  tone: "danger",
  icon: "triangleAlert",
  title: "Algo deu errado",
  body: "Tente novamente; se continuar, avise o administrador.",
  action: { label: "Tentar novamente", kind: "retry" },
  adminHint: true,
};
