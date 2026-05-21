import type { AppView, AuthState, LocalExportHistoryItem } from "../types";
import { AppIcon } from "./icons";
import { ThemeToggle } from "./ThemeToggle";
import type { ThemeMode } from "../types";

export function Rail({
  view,
  auth,
  history,
  onNavigate,
  themeMode,
  onThemeChange,
}: {
  view: AppView;
  auth: AuthState | null;
  history: LocalExportHistoryItem[];
  onNavigate: (view: AppView) => void;
  themeMode: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
}) {
  const connected = Boolean(auth?.signed_in && auth.classroom_scopes && auth.drive_scopes);
  return (
    <aside className="rail">
      <div className="rail-brand">
        <div className="brand-mark">CD</div>
        <div>
          <div className="brand-name">Classroom Downloader</div>
          <div className="brand-sub">Exports beta</div>
        </div>
      </div>

      <div className="rail-nav-label">Workspace</div>
      <nav className="rail-nav">
        <button
          className={`nav-item ${view === "workspace" || view === "connect" ? "active" : ""}`}
          onClick={() => onNavigate(connected ? "workspace" : "connect")}
        >
          <AppIcon name="classroom" />
          Classrooms
        </button>
        <button
          className={`nav-item ${view === "history" ? "active" : ""}`}
          onClick={() => onNavigate("history")}
          disabled={!connected}
        >
          <AppIcon name="history" />
          History
          <span className="nav-count">{history.length}</span>
        </button>
      </nav>

      <div className="rail-nav-label">Connected</div>
      <nav className="rail-nav">
        <ConnectionItem label="Google Classroom" ready={Boolean(auth?.classroom_scopes)} />
        <ConnectionItem label="Google Drive" ready={Boolean(auth?.drive_scopes)} />
      </nav>

      <div className="rail-tools">
        <ThemeToggle mode={themeMode} onChange={onThemeChange} />
      </div>

      <div className="rail-account">
        <div className="avatar">{auth?.email ? auth.email.slice(0, 2).toUpperCase() : "CD"}</div>
        <div className="account-copy">
          <div className="acct-name">
            {auth?.email ?? (connected ? "Google account connected" : "Not signed in")}
          </div>
          <div className={`acct-status ${connected ? "ready" : ""}`}>
            {connected ? "Ready to export" : "Connect to begin"}
          </div>
        </div>
      </div>
    </aside>
  );
}

function ConnectionItem({ label, ready }: { label: string; ready: boolean }) {
  return (
    <button className="nav-item passive" tabIndex={-1}>
      <AppIcon name={label.includes("Drive") ? "folderOpen" : "classroom"} />
      {label}
      <span className={`nav-count ${ready ? "ok" : "needed"}`}>{ready ? "ok" : "needed"}</span>
    </button>
  );
}
