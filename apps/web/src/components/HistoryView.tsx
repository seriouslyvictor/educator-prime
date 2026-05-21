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
          <div className="progress-eyebrow">Local browser history</div>
          <h1 className="history-title">Recent exports</h1>
        </div>
        <button className="btn btn-secondary" onClick={onBack}>
          <AppIcon name="classroom" />
          Back to classrooms
        </button>
      </div>

      {items.length === 0 ? (
        <EmptyState icon="history" title="No exports yet" copy="Completed exports will appear here after this browser writes them." />
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
                  {item.activityCount} activities · {item.fileCount} files · {formatWhen(item.completedAt)}
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
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
