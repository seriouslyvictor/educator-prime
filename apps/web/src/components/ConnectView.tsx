import { AppIcon } from "./icons";
import connectStyles from "./ConnectView.module.css";
void connectStyles;

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
    <div className={connectStyles.connect}>
      <section className="connect-card">
        <div className="connect-logo">CD</div>
        <h1>Bem-vindo ao Classroom Downloader</h1>
        <p className="lead">
          Traga as entregas dos alunos para uma pasta local organizada, com turmas do Classroom,
          arquivos do Drive e nomes seguros já tratados.
        </p>

        <div className="scope-list">
          <ScopeItem title="Ler turmas ativas e listas" copy="Somente as turmas que você leciona." />
          <ScopeItem title="Ler atividades e entregas" copy="Títulos, estados, prazos e arquivos entregues." />
          <ScopeItem title="Ler arquivos anexados do Drive" copy="Acesso somente leitura para copiar os arquivos localmente." />
        </div>

        <Notice
          icon={deliveryMode === "folder" ? "folderOpen" : "archive"}
          tone={deliveryMode === "folder" ? "info" : "warning"}
          title={deliveryMode === "folder" ? "Pronto para salvar direto na pasta" : "Entrega .zip em preparação"}
          copy={
            deliveryMode === "folder"
              ? "Chrome e Edge podem gravar os arquivos direto na pasta que você escolher."
              : "Este navegador não consegue gravar em uma pasta. O modo zip está planejado, mas ainda não está ativo nesta versão."
          }
        />

        {error ? <InlineError message={error} /> : null}

        <div className="connect-actions">
          <button className="btn btn-primary" onClick={onConnect} disabled={connecting}>
            <AppIcon name={connecting ? "loader" : "shield"} className={connecting ? "ico spin" : "ico"} />
            {connecting ? "Conectando..." : "Conectar conta Google escolar"}
          </button>
        </div>
        <p className="tiny">
          Nunca modificamos nem apagamos nada no Google Classroom ou Drive. O app apenas lê e exporta.
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
