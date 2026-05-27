import type { LocalExportHistoryItem } from "../types";
import { AppIcon } from "./icons";

export function DoneView({
  result,
  onDownloadAnother,
  onViewHistory,
}: {
  result: LocalExportHistoryItem;
  onDownloadAnother: () => void;
  onViewHistory: () => void;
}) {
  return (
    <div className="done-view">
      <section className="done-card">
        <div className="done-check">
          <AppIcon name="checkCircle" />
        </div>
        <h1 className="done-title">Exportação concluída</h1>
        <p className="done-sub">
          {result.fileCount} arquivos de {result.activityCount} atividades foram gravados na pasta escolhida.
        </p>
        <div className="done-path">
          <AppIcon name="folderOpen" />
          <span>{result.outputLabel}</span>
        </div>
        <div className="done-stats">
          <DoneStat label="Turma" value={result.courseName} />
          <DoneStat label="Atividades" value={result.activityCount.toString()} />
          <DoneStat label="Arquivos" value={result.fileCount.toString()} />
        </div>
        <div className="done-actions">
          <button className="btn btn-primary" onClick={onDownloadAnother}>
            <AppIcon name="download" />
            Baixar outra
          </button>
          <button className="btn btn-secondary" onClick={onViewHistory}>
            <AppIcon name="history" />
            Ver histórico
            <span className="kbd kbd-light">Enter</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function DoneStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="done-stat">
      <div className="val">{value}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}
