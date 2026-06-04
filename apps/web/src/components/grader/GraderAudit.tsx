import { api } from "../../lib/api";
import type { PrivacyAudit } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { extractionLabel, privacyLabel, safeStatusLabel } from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

export function GraderAudit({
  audit,
  busy,
  onBack,
  onRerun,
  onContinue,
}: {
  audit: PrivacyAudit;
  busy: boolean;
  onBack: () => void;
  onRerun: () => void;
  onContinue: () => void;
}) {
  const highRisk = audit.high_risk_files > 0;
  return (
    <div className={graderStyles["grader-page"]}>
      <GraderTopbar
        title="Auditoria de privacidade"
        subtitle="Apenas metadados seguros. Nenhuma chamada de IA foi feita."
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Voltar
            </button>
            <button className="btn btn-secondary" onClick={onRerun} disabled={busy}>
              <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
              Reexecutar
            </button>
            <button className="btn btn-primary" onClick={onContinue} disabled={busy || highRisk}>
              <AppIcon name="shield" />
              Continuar para rascunho
            </button>
          </>
        }
      />
      <div className="audit-layout">
        <section className="audit-summary">
          <AuditStat label="Aprovados" value={audit.passed_files} tone="ok" />
          <AuditStat label="Redigidos" value={audit.redacted_files} tone="warn" />
          <AuditStat label="Bloqueados" value={audit.blocked_files} tone="danger" />
          <AuditStat label="Alto risco" value={audit.high_risk_files} tone="danger" />
        </section>
        {highRisk ? (
          <div className="flag-note">
            A auditoria encontrou linhas de alto risco. O rascunho fica bloqueado até essas entregas serem tratadas.
          </div>
        ) : null}
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
              <span>{extractionLabel(row.extraction_status)}</span>
              <span className={`student-state ${row.privacy_status === "clean" ? "ok" : row.audit_pass ? "warn" : "danger"}`}>
                {safeStatusLabel(row.blocked_reason) || privacyLabel(row.privacy_status)}
              </span>
              <span>{row.privacy_flags.length ? row.privacy_flags.map(safeStatusLabel).join(", ") : "Nenhum"}</span>
            </div>
          ))}
        </section>
      </div>
    </div>
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


