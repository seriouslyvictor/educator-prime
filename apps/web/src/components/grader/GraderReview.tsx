import { useEffect, useMemo, useState } from "react";
import type { GradingJob, GradingSubmission } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { attemptLabel, attemptTone, extractionLabel, extractionTone, privacyLabel, privacyTone, safeStatusLabel, statusTone } from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

export function GraderReview({
  job,
  busy,
  activeSubmissionId,
  onActiveSubmission,
  onBack,
  onWrap,
  onAccept,
  onRetry,
}: {
  job: GradingJob;
  busy: boolean;
  activeSubmissionId: string | null;
  onActiveSubmission: (id: string) => void;
  onBack: () => void;
  onWrap: () => void;
  onAccept: (submission: GradingSubmission, score: number, feedback: string) => void;
  onRetry: (submission: GradingSubmission) => void;
}) {
  const active = useMemo(
    () => job.submissions.find((submission) => submission.id === activeSubmissionId) ?? job.submissions[0],
    [activeSubmissionId, job.submissions],
  );
  const [scoreText, setScoreText] = useState(String(active?.final_score ?? active?.ai_score ?? ""));
  const [feedback, setFeedback] = useState(active?.feedback ?? "");

  useEffect(() => {
    setScoreText(String(active?.final_score ?? active?.ai_score ?? ""));
    setFeedback(active?.feedback ?? "");
  }, [active?.id]);

  const score = Number(scoreText);

  return (
    <div className={graderStyles["grader-review"]}>
      <GraderTopbar
        title={job.activity_title}
        subtitle={`${job.reviewed_submissions}/${job.total_submissions} revisadas · cache ${
          job.cache_expires_at ? "disponível" : "apagado"
        }`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Fila
            </button>
            <button className="btn btn-primary" onClick={onWrap}>
              Fechar rascunhos
            </button>
          </>
        }
      />
      <div className="review-grid">
        <aside className="student-list">
          <div className="student-list-head">Alunos</div>
          {job.submissions.map((submission) => (
            <button
              key={submission.id}
              className={`student-row ${submission.id === active?.id ? "active" : ""}`}
              onClick={() => onActiveSubmission(submission.id)}
            >
              <span>{submission.student_name ?? submission.student_email ?? "Aluno desconhecido"}</span>
              <small className={`student-state ${statusTone(submission)}`}>
                {submission.reviewed ? "Revisado" : submission.error ? "Bloqueado" : submission.flag ? "Verificar" : "Rascunho"}
              </small>
            </button>
          ))}
        </aside>

        <section className="submission-preview">
          <div className="preview-paper">
            <div className="preview-file">
              <AppIcon name={active?.mime_type.includes("image") ? "eye" : "fileText"} />
              <div>
                <div>{active?.source_name ?? "Nenhuma entrega selecionada"}</div>
                <span>{active?.mime_type}</span>
              </div>
            </div>
            <div className="preview-lines">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
            <p>
              Prévia estruturada placeholder da V1. Privacidade:{" "}
              {privacyLabel(active?.privacy_status)}. Extração: {extractionLabel(active?.extraction_status)}.
            </p>
          </div>
        </section>

        <aside className="suggestion-panel">
          <div className="suggestion-head">
            <span>Rascunho da IA</span>
            <strong>{active?.confidence ? `${Math.round(active.confidence * 100)}%` : "novo"}</strong>
          </div>
          <div className="privacy-status-grid">
            <StatusPill label="Privacidade" value={privacyLabel(active?.privacy_status)} tone={privacyTone(active)} />
            <StatusPill label="Entrada" value={extractionLabel(active?.extraction_status)} tone={extractionTone(active)} />
            <StatusPill label="Motor" value={attemptLabel(active?.ai_attempt_status)} tone={attemptTone(active)} />
          </div>
          {active?.flag ? <div className="flag-note">{safeStatusLabel(active.flag)}</div> : null}
          <div className="criteria-list">
            {job.criteria.map((criterion) => (
              <div key={criterion.id} className="criterion-row">
                <span>{criterion.name}</span>
                <strong>{criterion.weight}%</strong>
              </div>
            ))}
          </div>
          <label className="score-input">
            <span>Nota final</span>
            <input value={scoreText} onChange={(event) => setScoreText(event.target.value)} inputMode="decimal" />
          </label>
          <label className="feedback-input">
            <span>Rascunho de feedback</span>
            <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
          </label>
          <div className="suggestion-actions">
            <button className="btn btn-secondary" onClick={() => active && onRetry(active)} disabled={!active || busy}>
              <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
              Repetir correção
            </button>
            <button
              className="btn btn-primary"
              onClick={() => active && onAccept(active, Number.isFinite(score) ? score : 0, feedback)}
              disabled={!active || busy}
            >
              <AppIcon name="check" />
              Aceitar e avançar
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className={`status-pill ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


