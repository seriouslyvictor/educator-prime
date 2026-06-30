import { Send, ShieldCheck, Users } from "lucide-react";
import { ApiError } from "../lib/api";
import { Button } from "@/components/ui/button";
import { AppIcon } from "./icons";
import { InlineError } from "./ui";
import loginStyles from "./LoginScreen.module.css";

export function LoginScreen({
  connecting,
  deliveryMode,
  error,
  versionSkew,
  onConnect,
}: {
  connecting: boolean;
  deliveryMode: "folder" | "zip";
  error: unknown;
  versionSkew: boolean;
  onConnect: () => void;
}) {
  return (
    <div className={loginStyles["ls-root"]}>
      {/* ── Left: brand/pitch aside ───────────────────────── */}
      <aside className="ls-aside">
        <div className="ls-brand">
          <span className="ls-mark">CD</span>
          Educator Prime
        </div>

        <div className="ls-pitch">
          <div className="ls-eyebrow">
            <span className="ls-glyph">✦</span>
            Correção com IA · privacidade primeiro
          </div>
          <h1>Corrija uma turma inteira sem perder o fim de semana.</h1>
          <p>
            Um fluxo guiado leva você do começo ao fim — escolher a turma, preparar, corrigir com
            rascunhos da IA e postar. Um passo de cada vez.
          </p>
          <div className="ls-steps">
            <div className="ls-step">
              <span className="ls-n">1</span>
              <Users size={15} aria-hidden="true" />
              Escolha a turma e as atividades
            </div>
            <div className="ls-step">
              <span className="ls-n">2</span>
              <ShieldCheck size={15} aria-hidden="true" />
              A IA audita a privacidade e rascunha as notas
            </div>
            <div className="ls-step">
              <span className="ls-n">3</span>
              <Send size={15} aria-hidden="true" />
              Você revisa e posta no Classroom
            </div>
          </div>
        </div>

        <div className="ls-foot">
          Nada vai para a IA antes da auditoria de privacidade obrigatória.
        </div>
      </aside>

      {/* ── Right: login card ─────────────────────────────── */}
      <main className="ls-main">
        <div className="ls-card">
          <h2 className="ls-card-title">Entrar</h2>
          <p className="ls-card-sub">Acesse com a conta da sua escola para continuar.</p>

          {versionSkew ? (
            <InlineError
              error={
                new ApiError(
                  0,
                  "version_skew",
                  "Frontend and backend versions differ.",
                )
              }
              onAction={() => window.location.reload()}
            />
          ) : null}

          {/* Scopes the OAuth will request */}
          <div className="ls-scope-list">
            <ScopeRow
              title="Ler turmas ativas e listas"
              copy="Somente as turmas que você leciona."
            />
            <ScopeRow
              title="Ler atividades e entregas"
              copy="Títulos, estados, prazos e arquivos entregues."
            />
            <ScopeRow
              title="Ler arquivos anexados do Drive"
              copy="Acesso somente leitura para copiar os arquivos localmente."
            />
          </div>

          {/* Browser delivery-mode notice */}
          <DeliveryNotice deliveryMode={deliveryMode} />

          {/* Connect error (non-gate) */}
          {error ? <InlineError error={error} onAction={onConnect} /> : null}

          {/* Primary OAuth action */}
          <Button
            variant="outline"
            className="ls-sso-btn"
            type="button"
            onClick={onConnect}
            disabled={connecting}
          >
            {connecting ? (
              <AppIcon name="loader" className="ico spin" />
            ) : (
              <span className="ls-g">G</span>
            )}
            {connecting ? "Conectando..." : "Continuar com o Google Sala de Aula"}
          </Button>

          <p className="ls-note">
            <span className="ls-note-glyph">✦</span>{" "}
            Nunca modificamos nem apagamos nada no Google Classroom ou Drive. O app apenas lê e
            exporta.
          </p>
        </div>
      </main>
    </div>
  );
}

function ScopeRow({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="ls-scope-item">
      <AppIcon name="check" className="ico ls-check-icon" />
      <div>
        <div className="ls-scope-lbl">{title}</div>
        <div className="ls-scope-desc">{copy}</div>
      </div>
    </div>
  );
}

function DeliveryNotice({ deliveryMode }: { deliveryMode: "folder" | "zip" }) {
  const isFolder = deliveryMode === "folder";
  return (
    <div className={`ls-notice ${isFolder ? "ls-notice-info" : "ls-notice-warning"}`}>
      <div className="ls-notice-icon">
        <AppIcon name={isFolder ? "folderOpen" : "archive"} />
      </div>
      <div>
        <div className="ls-notice-title">
          {isFolder ? "Pronto para salvar direto na pasta" : "Entrega .zip em preparação"}
        </div>
        <div className="ls-notice-desc">
          {isFolder
            ? "Chrome e Edge podem gravar os arquivos direto na pasta que você escolher."
            : "Este navegador não consegue gravar em uma pasta. O modo zip está planejado, mas ainda não está ativo nesta versão."}
        </div>
      </div>
    </div>
  );
}
