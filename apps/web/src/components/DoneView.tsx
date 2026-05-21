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
        <h1 className="done-title">Export complete</h1>
        <p className="done-sub">
          {result.fileCount} files from {result.activityCount} activities were written to your selected folder.
        </p>
        <div className="done-path">
          <AppIcon name="folderOpen" />
          <span>{result.outputLabel}</span>
        </div>
        <div className="done-stats">
          <DoneStat label="Course" value={result.courseName} />
          <DoneStat label="Activities" value={result.activityCount.toString()} />
          <DoneStat label="Files" value={result.fileCount.toString()} />
        </div>
        <div className="done-actions">
          <button className="btn btn-primary" onClick={onDownloadAnother}>
            <AppIcon name="download" />
            Download another
          </button>
          <button className="btn btn-secondary" onClick={onViewHistory}>
            <AppIcon name="history" />
            View history
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
