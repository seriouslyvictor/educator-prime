import { AppIcon } from "./icons";

export function ConnectView({
  connecting,
  deliveryMode,
  error,
  onConnect,
}: {
  connecting: boolean;
  deliveryMode: "folder" | "zip";
  error: string | null;
  onConnect: () => void;
}) {
  return (
    <div className="connect">
      <section className="connect-card">
        <div className="connect-logo">CD</div>
        <h1>Welcome to Classroom Downloader</h1>
        <p className="lead">
          Pull student submissions into a tidy local folder with Classroom rosters, Drive files,
          and email-first filenames already handled.
        </p>

        <div className="scope-list">
          <ScopeItem title="Read active classrooms and rosters" copy="Only the classes you teach." />
          <ScopeItem title="Read coursework and submissions" copy="Titles, states, due labels, and turned-in files." />
          <ScopeItem title="Read attached Drive files" copy="Read-only access so files can be copied locally." />
        </div>

        <Notice
          icon={deliveryMode === "folder" ? "folderOpen" : "archive"}
          tone={deliveryMode === "folder" ? "info" : "warning"}
          title={deliveryMode === "folder" ? "Direct-to-folder ready" : ".zip delivery placeholder"}
          copy={
            deliveryMode === "folder"
              ? "Chrome and Edge can write files straight into a folder you pick."
              : "This browser cannot write to a folder. Zip delivery is planned, but not active in this build."
          }
        />

        {error ? <InlineError message={error} /> : null}

        <div className="connect-actions">
          <button className="btn btn-primary" onClick={onConnect} disabled={connecting}>
            <AppIcon name={connecting ? "loader" : "shield"} className={connecting ? "ico spin" : "ico"} />
            {connecting ? "Connecting..." : "Connect school Google account"}
          </button>
        </div>
        <p className="tiny">
          We never modify or delete anything in Google Classroom or Drive. The MVP only reads and exports.
        </p>
      </section>
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <div className="inline-error">
      <AppIcon name="triangleAlert" />
      <span>{message}</span>
    </div>
  );
}

function Notice({
  icon,
  tone,
  title,
  copy,
}: {
  icon: "folderOpen" | "archive";
  tone: "info" | "warning";
  title: string;
  copy: string;
}) {
  return (
    <div className={`notice notice-${tone}`}>
      <div className="notice-icon">
        <AppIcon name={icon} />
      </div>
      <div className="notice-copy">
        <div className="notice-title">{title}</div>
        <div className="notice-desc">{copy}</div>
      </div>
    </div>
  );
}

function ScopeItem({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="scope-item">
      <AppIcon name="check" />
      <div>
        <div className="lbl">{title}</div>
        <div className="desc">{copy}</div>
      </div>
    </div>
  );
}
