import type { AppView, AuthState, LocalExportHistoryItem } from "../types";
import { AppIcon } from "./icons";
import { ShieldCheck } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import type { ThemeMode } from "../types";
import railStyles from "./Rail.module.css";

export function Rail({
  view,
  auth,
  history,
  onNavigate,
  onLogout,
  themeMode,
  onThemeChange,
}: {
  view: AppView;
  auth: AuthState | null;
  history: LocalExportHistoryItem[];
  onNavigate: (view: AppView) => void;
  onLogout: () => void;
  themeMode: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
}) {
  const connected = Boolean(auth?.signed_in && auth.classroom_scopes && auth.drive_scopes);
  const accountName = auth?.name ?? auth?.email ?? (connected ? "Conta Google conectada" : "Não conectado");
  const fallbackInitials = getInitials(auth?.name, auth?.email);
  return (
    <aside className={railStyles.rail}>
      <div className="rail-brand">
        <div className="brand-mark">CD</div>
        <div>
          <div className="brand-name">Classroom Downloader</div>
          <div className="brand-sub">Exportações beta</div>
        </div>
      </div>

      <div className="rail-nav-label">Área de trabalho</div>
      <nav className="rail-nav">
        {auth?.is_admin ? (
          <button
            className={`nav-item ${view === "admin" ? "active" : ""}`}
            onClick={() => onNavigate("admin")}
          >
            <ShieldCheck data-icon="inline-start" />
            Admin
          </button>
        ) : null}
        <button
          className={`nav-item ${view.startsWith("grader") ? "active" : ""}`}
          onClick={() => onNavigate("graderQueue")}
          disabled={!connected}
        >
          <AppIcon name="sparkle" />
          Corrigir com IA
        </button>
        <button
          className={`nav-item ${view === "workspace" || view === "connect" ? "active" : ""}`}
          onClick={() => onNavigate(connected ? "workspace" : "connect")}
        >
          <AppIcon name="classroom" />
          Turmas
        </button>
        <button
          className={`nav-item ${view === "history" ? "active" : ""}`}
          onClick={() => onNavigate("history")}
          disabled={!connected}
        >
          <AppIcon name="history" />
          Histórico
          <span className="nav-count">{history.length}</span>
        </button>
      </nav>

      <div className="rail-nav-label">Conectado</div>
      <nav className="rail-nav">
        <ConnectionItem label="Google Classroom" ready={Boolean(auth?.classroom_scopes)} />
        <ConnectionItem label="Google Drive" ready={Boolean(auth?.drive_scopes)} />
      </nav>

      <div className="rail-tools">
        <ThemeToggle mode={themeMode} onChange={onThemeChange} />
      </div>

      <div className="rail-account">
        <div className="avatar" aria-hidden="true">
          {auth?.picture ? <img src={auth.picture} alt="" referrerPolicy="no-referrer" /> : fallbackInitials}
        </div>
        <div className="account-copy">
          <div className="acct-name">{accountName}</div>
          <div className={`acct-status ${connected ? "ready" : ""}`}>
            {connected ? "Pronto para exportar" : "Conecte para começar"}
          </div>
        </div>
        {auth?.signed_in ? (
          <button className="logout-btn" type="button" onClick={onLogout} title="Sair da conta Google">
            <AppIcon name="logout" />
          </button>
        ) : null}
      </div>
    </aside>
  );
}

function getInitials(name?: string | null, email?: string | null) {
  const source = name?.trim() || email?.split("@")[0] || "";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase() || "CD";
}

function ConnectionItem({ label, ready }: { label: string; ready: boolean }) {
  return (
    <button className="nav-item passive" tabIndex={-1}>
      <AppIcon name={label.includes("Drive") ? "folderOpen" : "classroom"} />
      {label}
      <span className={`nav-count ${ready ? "ok" : "needed"}`}>{ready ? "ok" : "necessário"}</span>
    </button>
  );
}
