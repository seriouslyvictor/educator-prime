import type { GradingQueueItem, QueueAction } from "../../../types";

export type QueueActionConfig = {
  id: QueueAction;
  label: string;
  bulkLabel: string;
  confirmLabel: string;
  sub: string;
  icon: "refresh" | "trash" | "archive" | "eyeOff";
};

export const bulkActions: QueueActionConfig[] = [
  {
    id: "restart",
    label: "Reiniciar do zero",
    bulkLabel: "Reiniciar",
    confirmLabel: "Confirmar reinício",
    sub: "descarta rascunhos, notas, critérios e auditoria",
    icon: "refresh",
  },
  {
    id: "remove",
    label: "Remover da fila",
    bulkLabel: "Remover",
    confirmLabel: "Confirmar remoção",
    sub: "continua disponível em Atividades",
    icon: "trash",
  },
  {
    id: "archive",
    label: "Arquivar",
    bulkLabel: "Arquivar",
    confirmLabel: "Arquivar",
    sub: "sai da fila e fica nesta seção",
    icon: "archive",
  },
  {
    id: "hide",
    label: "Ocultar da visualização",
    bulkLabel: "Ocultar",
    confirmLabel: "Ocultar",
    sub: "acessível pela seção de arquivadas e ocultas",
    icon: "eyeOff",
  },
];

export function queueItemKey(item: GradingQueueItem) {
  return `${item.course_id}-${item.activity_id}-${item.latest_job_id ?? "new"}`;
}

export function isDestructiveAction(action: QueueAction) {
  return action === "restart" || action === "remove";
}

export function isQueueActionValid(action: QueueAction, item: GradingQueueItem) {
  if (action === "remove") return true;
  if (action === "restore") return Boolean(item.latest_job_id);
  return Boolean(item.latest_job_id);
}

export function actionsForItem(item: GradingQueueItem) {
  if (!item.latest_job_id) return bulkActions.filter((action) => action.id === "remove");
  return bulkActions;
}

export function referenceQueueStatus(item: GradingQueueItem): {
  label: string;
  cls: string;
  icon: "sparkle" | "eye" | "settings" | "checkCircle";
  cta: string;
} {
  if (item.status === "completed") return { label: "Concluída", cls: "posted", icon: "checkCircle", cta: "Abrir" };
  if (item.status === "reviewing") return { label: "Em revisão", cls: "reviewing", icon: "eye", cta: "Revisar" };
  if (item.latest_job_id) return { label: "Rascunhando", cls: "drafting", icon: "settings", cta: "Retomar" };
  return { label: "IA pronta", cls: "ai", icon: "sparkle", cta: "Começar" };
}
