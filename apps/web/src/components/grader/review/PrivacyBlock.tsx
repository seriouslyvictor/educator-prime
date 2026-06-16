import { AppIcon } from "../../icons";
import { privacyTone, privacyLabel, redactionLabel } from "../graderStatus";
import type { GradingSubmission } from "../../../types";

export function PrivacyBlock({ submission }: { submission: GradingSubmission }) {
  const tone = privacyTone(submission);
  const label = privacyLabel(submission.privacy_status);
  // Only redaction categories belong here — never the engine's grading flags,
  // which surface in the flag-banner above.
  const flags = submission.privacy_flags ?? [];
  return (
    <div className={`privacy-block ${tone}`}>
      <div className="pb-row">
        <span className="pb-ic">
          <AppIcon name={tone === "danger" ? "lock" : tone === "warn" ? "eyeOff" : "shield"} />
        </span>
        <div className="pb-main">
          <div className="pb-head">
            <span className="pb-label">Privacidade</span>
            <span className={`pb-tag ${tone}`}>{label}</span>
          </div>
          <div className="pb-desc">
            {tone === "danger"
              ? "Retida da IA ou sem rascunho seguro; corrija manualmente."
              : tone === "warn"
                ? "Identificadores foram ocultados antes de a IA ler."
                : "Nenhum dado pessoal direto encontrado no corpo da entrega."}
          </div>
          {flags.length ? (
            <div className="pb-flags">
              {flags.map((flag) => (
                <span className="pb-flag" key={flag}><AppIcon name="eyeOff" /> {redactionLabel(flag)}</span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
