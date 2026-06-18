import type { AuthState } from "../types";
import { AppIcon } from "./icons";
import { InlineError } from "./ui";
import connectStyles from "./ConnectView.module.css";
void connectStyles;

type ConnectViewProps = {
  auth: AuthState | null;
  connecting: boolean;
  deliveryMode: "folder" | "zip";
  error: unknown;
  onConnectIdentity: () => void;
  onConnectClassroom: () => void;
  onConnectDrive: () => void;
};

export function ConnectView({
  auth,
  connecting,
  deliveryMode,
  error,
  onConnectIdentity,
  onConnectClassroom,
  onConnectDrive,
}: ConnectViewProps) {
  const signedIn = Boolean(auth?.signed_in && auth.identity_scopes);
  const classroomReady = Boolean(auth?.classroom_scopes);
  const stage = !signedIn
    ? {
        label: "Entrar com Google",
        icon: "shield" as const,
        action: onConnectIdentity,
        lead: "Entre com sua conta Google escolar. Nesta etapa usamos apenas identidade: nome, e-mail e foto.",
        scopes: [["Identificar sua conta", "Nome, e-mail e foto para abrir sua sessao."]],
      }
    : !classroomReady
      ? {
          label: "Permitir leitura do Classroom",
          icon: "classroom" as const,
          action: onConnectClassroom,
          lead: "Conta conectada. Permita a leitura do Classroom para listar suas turmas e atividades.",
          scopes: [
            ["Ler turmas ativas", "Somente as turmas que voce leciona."],
            ["Ler atividades", "Titulos, estados e prazos das atividades."],
          ],
        }
      : {
          label: "Continuar",
          icon: "check" as const,
          action: onConnectDrive,
          lead: "Classroom conectado. O Drive sera pedido somente quando voce exportar ou corrigir arquivos.",
          scopes: [["Google Classroom pronto", "Voce pode navegar por turmas e atividades."]],
        };

  return (
    <div className={connectStyles.connect}>
      <section className="connect-card">
        <div className="connect-logo">CD</div>
        <h1>Bem-vindo ao Classroom Downloader</h1>
        <p className="lead">{stage.lead}</p>

        <div className="scope-list">
          {stage.scopes.map(([title, copy]) => (
            <ScopeItem key={title} title={title} copy={copy} />
          ))}
        </div>

        <Notice
          icon={deliveryMode === "folder" ? "folderOpen" : "archive"}
          tone={deliveryMode === "folder" ? "info" : "warning"}
          title={deliveryMode === "folder" ? "Pronto para salvar direto na pasta" : "Entrega .zip em preparacao"}
          copy={
            deliveryMode === "folder"
              ? "Chrome e Edge podem gravar os arquivos direto na pasta que voce escolher."
              : "Este navegador nao consegue gravar em uma pasta. O modo zip esta planejado, mas ainda nao esta ativo nesta versao."
          }
        />

        {auth?.email ? (
          <Notice
            icon="folderOpen"
            tone="info"
            title={auth.name ?? auth.email}
            copy={auth.email}
          />
        ) : null}

        {error ? <InlineError error={error} onAction={stage.action} /> : null}

        <div className="connect-actions">
          <button className="btn btn-primary" onClick={stage.action} disabled={connecting}>
            <AppIcon name={connecting ? "loader" : stage.icon} className={connecting ? "ico spin" : "ico"} />
            {connecting ? "Conectando..." : stage.label}
          </button>
        </div>
        <p className="tiny">Permissoes adicionais aparecem somente quando a acao escolhida precisa delas.</p>
      </section>
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
