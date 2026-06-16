import { api } from "../../../lib/api";
import { AppIcon } from "../../icons";
import { extractionLabel, privacyLabel, redactionSummary, safeStatusLabel } from "../graderStatus";
import type { PrivacyAudit } from "../../../types";

export function CriteriaRunningPanel({
  progress,
}: {
  progress: {
    processed: number;
    total: number;
    current: string;
  };
}) {
  return (
    <div className="criteria-running">
      <div className="audit-run-eyebrow">
        <AppIcon name="sparkle" /> Definindo critérios
      </div>
      <div className="audit-run-title">
        <AppIcon name="loader" className="ico spin" />
        <h2>Inferindo rubrica</h2>
      </div>
      <p className="audit-run-current">
        {progress.current || "Lendo a descrição da atividade e sinais estruturais."}
      </p>
      <div className="audit-run-meter-row">
        <strong>{progress.processed}/{Math.max(progress.total, 1)}</strong>
        <span>{Math.round((progress.processed / Math.max(progress.total, 1)) * 100)}%</span>
      </div>
      <div className="audit-run-meter">
        <span style={{ width: `${(progress.processed / Math.max(progress.total, 1)) * 100}%` }} />
      </div>
      <div className="audit-run-note">A professora verá e poderá editar os critérios antes da auditoria.</div>
    </div>
  );
}

export function AuditRunningPanel({
  progress,
  total,
}: {
  progress: {
    processed: number;
    total: number;
    current: string;
  };
  total: number;
}) {
  const progressTotal = progress.total || total || 1;
  const pct = Math.round((progress.processed / progressTotal) * 100);
  return (
    <div className="audit-run">
      <div className="audit-run-eyebrow">
        <AppIcon name="shield" /> Preparando entregas · a IA ainda não viu nada
      </div>
      <div className="audit-run-title">
        <AppIcon name="loader" className="ico spin" />
        <h2>Auditoria de privacidade</h2>
      </div>
      <div className="audit-run-current">
        Verificando <strong>{progress.current || "entregas"}</strong> — mascarando nomes, e-mails e identificadores.
      </div>
      <div className="audit-run-meter-row">
        <strong>{progress.processed}/{progressTotal}</strong>
        <span>{pct}%</span>
      </div>
      <div className="audit-run-meter"><span style={{ width: `${pct}%` }} /></div>
      <div className="audit-run-note">
        Esta etapa é obrigatória. Nenhum dado vai para a IA antes da auditoria concluir.
      </div>
    </div>
  );
}

export function InferIntroPanel({ submissionCount }: { submissionCount: number }) {
  return (
    <div className="panel-hint">
      A IA vai ler a descrição da atividade e uma amostra segura das entregas
      {submissionCount ? ` (${submissionCount})` : ""} para propor uma rubrica. Clique em
      “Inferir critérios” — você poderá editar os critérios e pesos antes de auditar.
    </div>
  );
}

export function PreparedPanel({
  audit,
  busy,
  onContinue,
  onRerun,
}: {
  audit: PrivacyAudit;
  busy: boolean;
  onContinue: () => void;
  onRerun: () => void;
}) {
  const readyForDraft = audit.passed_files + audit.redacted_files;
  const blocked = audit.blocked_files;
  const highRisk = audit.high_risk_files > 0;

  return (
    <section className="prep-panel" aria-live="polite">
      <div className="prep-panel-head">
        <AppIcon name="checkCircle" className="ico" />
        <strong>Preparação concluída</strong>
      </div>

      <p className="prep-headline">
        <strong>{readyForDraft}</strong> {readyForDraft === 1 ? "entrega pronta" : "entregas prontas"} para rascunho
        {blocked > 0 ? (
          <> · <strong>{blocked}</strong> {blocked === 1 ? "bloqueada fica manual" : "bloqueadas ficam manuais"}</>
        ) : null}
        .
      </p>

      <div className="audit-summary">
        <AuditStat label="Aprovados" value={audit.passed_files} tone="ok" />
        <AuditStat label="Redigidos" value={audit.redacted_files} tone="warn" />
        <AuditStat label="Bloqueados" value={audit.blocked_files} tone="danger" />
        <AuditStat label="Alto risco" value={audit.high_risk_files} tone="danger" />
      </div>

      {highRisk ? (
        <div className="flag-note">
          A auditoria encontrou linhas de alto risco. O rascunho fica bloqueado até essas entregas serem tratadas.
        </div>
      ) : null}

      <details className="prep-details">
        <summary>Detalhes da auditoria</summary>
        <div className="audit-actions">
          <a className="btn btn-secondary" href={api.privacyAuditCsvUrl(audit.job_id)}>
            <AppIcon name="fileDown" /> Exportar CSV
          </a>
          <a className="btn btn-secondary" href={api.privacyAuditJsonUrl(audit.job_id)}>
            <AppIcon name="fileText" /> Exportar JSON
          </a>
        </div>
        <section className="audit-table" aria-label="Linhas da auditoria de privacidade">
          <div className="audit-row audit-row-head">
            <span>Aluno</span>
            <span>Arquivo</span>
            <span>Entrada</span>
            <span>Privacidade</span>
            <span>Sinais</span>
          </div>
          {audit.rows.map((row) => (
            <div className="audit-row" key={row.id}>
              <span>{row.student_label}</span>
              <span>{row.redacted_source_name}</span>
              <span>
                {extractionLabel(row.extraction_status)}
                {row.extraction_status === "pending_vision" ? (
                  <small className="visual-audit-note">
                    Imagem sera enviada uma vez para transcricao ao gerar rascunhos.
                  </small>
                ) : null}
              </span>
              <span className={`student-state ${row.privacy_status === "clean" ? "ok" : row.audit_pass ? "warn" : "danger"}`}>
                {safeStatusLabel(row.blocked_reason) || privacyLabel(row.privacy_status)}
              </span>
              <span>{redactionSummary(row.redaction_counts)}</span>
            </div>
          ))}
        </section>
      </details>

      <div className="prep-actions">
        <button className="btn btn-secondary" onClick={onRerun} disabled={busy}>
          <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
          Reexecutar auditoria
        </button>
        <button className="btn btn-ai" onClick={onContinue} disabled={busy || highRisk}>
          <AppIcon name={busy ? "loader" : "sparkle"} className={busy ? "ico spin" : "ico"} />
          {readyForDraft > 0 ? `Gerar ${readyForDraft} rascunhos e revisar` : "Gerar rascunhos e revisar"}
        </button>
      </div>
    </section>
  );
}

function AuditStat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className={`audit-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
