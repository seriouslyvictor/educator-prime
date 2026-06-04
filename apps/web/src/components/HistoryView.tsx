import type { LocalExportHistoryItem } from "../types";
import { AppIcon } from "./icons";
import { EmptyState } from "./Workspace";

export function HistoryView({
  items,
  onBack,
}: {
  items: LocalExportHistoryItem[];
  onBack: () => void;
}) {
  return (
    <div className="history-view">
      <div className="history-head">
        <div>
          <div className="progress-eyebrow">Histórico local do navegador</div>
          <h1 className="history-title">Exportações recentes</h1>
        </div>
        <button className="btn btn-secondary" onClick={onBack}>
          <AppIcon name="classroom" />
          Voltar para turmas
        </button>
      </div>

      {items.length === 0 ? (
        <EmptyState icon="history" title="Nenhuma exportação ainda" copy="Exportações concluídas aparecerão aqui depois que este navegador gravar os arquivos." />
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <div className="history-row" key={item.id}>
              <div className="history-icon">
                <AppIcon name="folderOpen" />
              </div>
              <div>
                <div className="history-ttl">{item.courseName}</div>
                <div className="history-sub">
                  {item.activityCount} atividades · {item.fileCount} arquivos · {formatWhen(item.completedAt)}
                </div>
                <div className="history-meta">{item.outputLabel}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatWhen(value: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
