import { AppIcon } from "./icons";

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
    <div className="progress-view">
      <section className="progress-main">
        <div>
          <div className="progress-eyebrow">
            {deliveryMode === "zip" ? "Packaging placeholder" : "Downloading"} · {courseName}
          </div>
          <h1 className="progress-title">
            {error ? "Export needs attention" : deliveryMode === "zip" ? ".zip delivery is not active yet" : "Streaming submissions"}
          </h1>
          <p className="progress-sub">
            {deliveryMode === "zip"
              ? "Zip packaging is shown as a future delivery mode. Use Chrome or Edge for real folder export today."
              : "Files are streamed from Drive through FastAPI and written into the folder you picked."}
          </p>
        </div>

        <div className="big-stats">
          <Stat label="Completed" value={completed} sub={`/ ${total}`} />
          <Stat label="Remaining" value={remaining} />
          <Stat label="Errors" value={failed} />
          <Stat label="Progress" value={`${pct}%`} />
        </div>

        <div className="bigbar-wrap">
          <div className="bigbar-head">
            <div className="now-playing">
              <AppIcon name={error ? "triangleAlert" : "zap"} />
              <div className="now-playing-path">{error ?? currentPath ?? "Preparing..."}</div>
            </div>
            <div className="percent">{pct}%</div>
          </div>
          <div className="bigbar">
            <div className="bigbar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="progress-actions">
          <button className="btn btn-secondary" onClick={onCancel}>
            Back to workspace
            <span className="kbd kbd-light">Esc</span>
          </button>
        </div>
      </section>

      <aside className="log-panel">
        <div className="log-head">
          <span>Export log</span>
          <span>{log.length} events</span>
        </div>
        <div className="log-list">
          {log.map((item) => (
            <div className={`log-row ${item.kind}`} key={item.id}>
              <AppIcon name={item.kind === "err" ? "triangleAlert" : item.kind === "now" ? "zap" : "checkCircle"} />
              <span className="path">{item.text}</span>
            </div>
          ))}
          {log.length === 0 ? (
            <div className="log-empty">Waiting for the first file...</div>
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
