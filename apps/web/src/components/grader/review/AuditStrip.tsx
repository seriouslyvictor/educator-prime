import { AppIcon } from "../../icons";
import { privacyLabel, redactionSummary, safeStatusLabel } from "../graderStatus";
import type { PrivacyAudit } from "../../../types";

export function AuditStrip({ audit, onOpen }: { audit: PrivacyAudit; onOpen: () => void }) {
  return (
    <div className="audit-strip">
      <div className="as-lead">
        <span className="as-shield"><AppIcon name="shield" /></span>
        <div className="as-text">
          <strong>Auditoria de privacidade aprovada</strong>
          <span>{audit.total_files} verificadas · nomes completos, CPF, telefones, e-mails e redes sociais ocultados da IA</span>
        </div>
      </div>
      <div className="as-counts">
        <span className="as-count ok"><b>{audit.passed_files}</b> limpas</span>
        <span className="as-count warn"><b>{audit.redacted_files}</b> redigidas</span>
        <span className="as-count danger"><b>{audit.blocked_files + audit.high_risk_files}</b> retidas</span>
      </div>
      <button className="as-report" onClick={onOpen}>
        <AppIcon name="fileText" /> Ver relatório
      </button>
    </div>
  );
}

export function AuditReport({ audit, onClose }: { audit: PrivacyAudit; onClose: () => void }) {
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer audit-drawer">
        <div className="drawer-head">
          <div>
            <div className="drawer-title"><AppIcon name="shield" /> Relatório de privacidade</div>
            <div className="drawer-sub">
              {audit.total_files} entregas · {audit.passed_files} limpas · {audit.redacted_files} redigidas ·{" "}
              {audit.blocked_files + audit.high_risk_files} retidas
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}><AppIcon name="x" /></button>
        </div>
        <div className="drawer-body audit-drawer-body">
          <div className="audit-reassure in-drawer">
            <AppIcon name="eyeOff" />
            Antes de qualquer correção, nomes completos, CPF, RG, telefones, e-mails e redes sociais foram ocultados da IA (nomes próprios isolados podem permanecer).
          </div>
          <section className="audit-table" aria-label="Linhas da auditoria de privacidade">
            <div className="audit-row audit-row-head">
              <span>Aluno</span>
              <span>Arquivo</span>
              <span>Privacidade</span>
              <span>Sinais</span>
            </div>
            {audit.rows.map((row) => (
              <div className="audit-row" key={row.id}>
                <span className="ar-name">{row.student_label}</span>
                <span className="ar-file">{row.redacted_source_name}</span>
                <span className={`student-state ${row.privacy_status === "clean" ? "ok" : row.audit_pass ? "warn" : "danger"}`}>
                  {safeStatusLabel(row.blocked_reason) || privacyLabel(row.privacy_status)}
                </span>
                <span className="ar-flags">
                  {redactionSummary(row.redaction_counts)}
                  {row.extraction_status === "pending_vision" ? (
                    <small className="visual-audit-note">
                      Imagem sera enviada uma vez para transcricao ao gerar rascunhos.
                    </small>
                  ) : null}
                </span>
              </div>
            ))}
          </section>
        </div>
      </div>
    </>
  );
}
