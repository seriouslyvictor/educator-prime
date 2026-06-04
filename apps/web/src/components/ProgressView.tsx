import { AppIcon } from "./icons";
import progressStyles from "./ProgressView.module.css";
void progressStyles;

export type ProgressLogItem = {
  id: string;
  kind: "ok" | "err" | "now";
  text: string;
};

export function ProgressView({
  courseName,
  total,
  completed,
  failed,
  currentPath,
  log,
  error,
  deliveryMode,
  onCancel,
}: {
  courseName: string;
  total: number;
  completed: number;
  failed: number;
  currentPath: string;
  log: ProgressLogItem[];
  error: string | null;
  deliveryMode: "folder" | "zip";
  onCancel: () => void;
}) {
  const pct = total ? Math.round((completed / total) * 100) : 0;
  const remaining = Math.max(0, total - completed - failed);
  return (
    <div className={progressStyles["progress-view"]}>
      <section className="progress-main">
        <div>
          <div className="progress-eyebrow">
            {deliveryMode === "zip" ? "Empacotamento placeholder" : "Baixando"} · {courseName}
          </div>
          <h1 className="progress-title">
            {error ? "A exportação precisa de atenção" : deliveryMode === "zip" ? "A entrega .zip ainda não está ativa" : "Transmitindo entregas"}
          </h1>
          <p className="progress-sub">
            {deliveryMode === "zip"
              ? "O empacotamento zip aparece como modo futuro. Use Chrome ou Edge para exportar para uma pasta hoje."
              : "Os arquivos são transmitidos do Drive pelo FastAPI e gravados na pasta que você escolheu."}
          </p>
        </div>

        <div className="big-stats">
          <Stat label="Concluídos" value={completed} sub={`/ ${total}`} />
          <Stat label="Restantes" value={remaining} />
          <Stat label="Erros" value={failed} />
          <Stat label="Progresso" value={`${pct}%`} />
        </div>

        <div className="bigbar-wrap">
          <div className="bigbar-head">
            <div className="now-playing">
              <AppIcon name={error ? "triangleAlert" : "zap"} />
              <div className="now-playing-path">{error ?? currentPath ?? "Preparando..."}</div>
            </div>
            <div className="percent">{pct}%</div>
          </div>
          <div className="bigbar">
            <div className="bigbar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="progress-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            Voltar à área de trabalho
            <span className="kbd kbd-light">Esc</span>
          </button>
        </div>
      </section>

      <aside className="log-panel">
        <div className="log-head">
          <span>Log da exportação</span>
          <span>{log.length} eventos</span>
        </div>
        <div className="log-list">
          {log.map((item) => (
            <div className={`log-row ${item.kind}`} key={item.id}>
              <AppIcon name={item.kind === "err" ? "triangleAlert" : item.kind === "now" ? "zap" : "checkCircle"} />
              <span className="path">{item.text}</span>
            </div>
          ))}
          {log.length === 0 ? (
            <div className="log-empty">Aguardando o primeiro arquivo...</div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="stat">
      <div className="lbl">{label}</div>
      <div className="val">
        {value}
        {sub ? <span className="sm">{sub}</span> : null}
      </div>
    </div>
  );
}
