import { AppIcon } from "./icons";

export function ActionBar({
  selectedCount,
  fileEstimate,
  deliveryMode,
  disabled,
  busy,
  onDryRun,
  onDownload,
}: {
  selectedCount: number;
  fileEstimate: number;
  deliveryMode: "folder" | "zip";
  disabled: boolean;
  busy: boolean;
  onDryRun: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="action-bar">
      <div className="bar-summary">
        <span className="bar-count">{selectedCount}</span>
        <span className="bar-sub">
          {selectedCount === 1 ? "activity" : "activities"} · {fileEstimate || "ready"} files
        </span>
      </div>
      <button className="btn btn-ghost-dark" onClick={onDryRun} disabled={disabled || busy}>
        <AppIcon name="eye" />
        Dry run
        <span className="kbd">Ctrl+D</span>
      </button>
      <button className="btn btn-on-ink-primary" onClick={onDownload} disabled={disabled || busy}>
        <AppIcon name={deliveryMode === "zip" ? "archive" : "folderOpen"} />
        {deliveryMode === "zip" ? ".zip not available yet" : busy ? "Preparing..." : "Pick folder & download"}
        <span className="kbd">Ctrl+Enter</span>
      </button>
    </div>
  );
}
