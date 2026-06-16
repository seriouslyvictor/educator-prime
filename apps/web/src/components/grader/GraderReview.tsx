import { useEffect, useMemo, useState } from "react";
import type { GradingJob, GradingSubmission, PrivacyAudit } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { studentLabel } from "./domain";
import { initials, isBlocked, isVisualSubmission } from "./review/reviewHelpers";
import { AuditStrip, AuditReport } from "./review/AuditStrip";
import { PrivacyBlock } from "./review/PrivacyBlock";
import { StudentRow } from "./review/StudentRow";
import { SubmissionFiles, BlockedEvidence } from "./review/SubmissionPreview";
import { errorLayerLabel, safeStatusLabel } from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

type ReviewFilter = "all" | "flagged" | "pending" | "reviewed";

function hasDefaultCriteria(job: GradingJob): boolean {
  const names = job.criteria.map((criterion) => criterion.name).join("|");
  const weights = job.criteria.map((criterion) => criterion.weight).join("|");
  return names === "Understanding|Evidence|Reasoning|Clarity" && weights === "30|25|30|15";
}

export function GraderReview({
  job,
  busy,
  audit,
  progress,
  activeSubmissionId,
  draftingSubmissionId,
  onActiveSubmission,
  onBack,
  onWrap,
  onAccept,
  onRetry,
}: {
  job: GradingJob;
  busy: boolean;
  audit: PrivacyAudit | null;
  progress: {
    phase: "audit" | "criteria" | "draft";
    processed: number;
    total: number;
    current: string;
    done: boolean;
    error: string | null;
  } | null;
  activeSubmissionId: string | null;
  draftingSubmissionId: string | null;
  onActiveSubmission: (id: string) => void;
  onBack: () => void;
  onWrap: () => void;
  onAccept: (submission: GradingSubmission, score: number, feedback: string) => void;
  onRetry: (submission: GradingSubmission) => void;
}) {
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [reportOpen, setReportOpen] = useState(false);
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

  const counts = useMemo(() => {
    let reviewed = 0;
    let blocked = 0;
    let pending = 0;
    for (const submission of job.submissions) {
      if (submission.reviewed) reviewed += 1;
      else if (isBlocked(submission)) blocked += 1;
      else pending += 1;
    }
    return { reviewed, blocked, pending };
  }, [job.submissions]);

  const shown = useMemo(
    () =>
      job.submissions.filter((submission) => {
        if (filter === "flagged") return Boolean(submission.flag) || isBlocked(submission);
        if (filter === "pending") return !submission.reviewed;
        if (filter === "reviewed") return submission.reviewed;
        return true;
      }),
    [filter, job.submissions],
  );

  const total = job.submissions.length || 1;
  const blockedActive = isBlocked(active);
  const draftInProgress = Boolean(progress?.phase === "draft" && !progress.done);
  // A submission is still "pending" while the draft run hasn't produced a result for it.
  const isPending = (submission: GradingSubmission | undefined): boolean =>
    Boolean(
      draftInProgress &&
        submission &&
        submission.ai_score == null &&
        submission.final_score == null &&
        !submission.error &&
        !submission.reviewed,
    );
  const activePending = isPending(active);
  const activeDrafting = Boolean(active && active.id === draftingSubmissionId);
  const score = Number(scoreText);
  const hasValidScore = scoreText.trim() !== "" && Number.isFinite(score);

  const goRelative = (delta: number) => {
    if (!active) return;
    const list = shown.length ? shown : job.submissions;
    const index = list.findIndex((submission) => submission.id === active.id);
    const next = list[index + delta];
    if (next) onActiveSubmission(next.id);
  };

  const accept = () => {
    if (active && hasValidScore && !busy) onAccept(active, score, feedback);
  };

  // Keyboard review: J/K to move, Enter to accept — ignored while typing in a field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName.toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      if (event.key === "j" || event.key === "J") {
        event.preventDefault();
        goRelative(1);
      } else if (event.key === "k" || event.key === "K") {
        event.preventDefault();
        goRelative(-1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        accept();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const activeIndex = active ? job.submissions.findIndex((submission) => submission.id === active.id) : -1;

  return (
    <div className={graderStyles["grader-review"]}>
      <GraderTopbar
        title={job.activity_title}
        subtitle={`${job.reviewed_submissions}/${job.total_submissions} revisadas · ${counts.blocked} bloqueadas · salvo automaticamente`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Fila
            </button>
            <button className="btn btn-primary" onClick={onWrap} disabled={job.reviewed_submissions === 0}>
              <AppIcon name="checkCircle" />
              Fechar {job.reviewed_submissions} rascunhos
            </button>
          </>
        }
      />
      {audit ? <AuditStrip audit={audit} onOpen={() => setReportOpen(true)} /> : null}
      {progress?.phase === "draft" && !progress.done ? (
        <div className="stream-strip">
          <AppIcon name="sparkle" />
          <span>Gerando rascunhos da IA</span>
          <div className="stream-bar">
            <span style={{ width: `${(progress.processed / Math.max(progress.total, 1)) * 100}%` }} />
          </div>
          <strong>{progress.processed}/{Math.max(progress.total, 1)}</strong>
        </div>
      ) : null}
      <div className="review-grid">
        <aside className="student-list">
          <div className="student-list-head">
            <div className="grade-progress">
              <span>
                <strong>{counts.reviewed}</strong>/{job.submissions.length} revisadas
              </span>
              <span className="grade-progress-ai">
                <AppIcon name="sparkle" /> {counts.pending} rascunhos
              </span>
            </div>
            <div className="grade-list-bar" aria-hidden="true">
              <i className="seg reviewed" style={{ width: `${(counts.reviewed / total) * 100}%` }} />
              <i className="seg flag" style={{ width: `${(counts.blocked / total) * 100}%` }} />
              <i className="seg pending" style={{ width: `${(counts.pending / total) * 100}%` }} />
            </div>
            <div className="grade-filters" role="tablist" aria-label="Filtrar alunos">
              {(
                [
                  ["all", `Todas ${job.submissions.length}`],
                  ["flagged", `Sinalizadas ${counts.blocked + job.submissions.filter((s) => s.flag && !isBlocked(s)).length}`],
                  ["pending", "Pendentes"],
                  ["reviewed", "Concluídas"],
                ] as Array<[ReviewFilter, string]>
              ).map(([id, label]) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={filter === id}
                  className={`grade-filter ${filter === id ? "active" : ""}`}
                  onClick={() => setFilter(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="grade-list-body">
            {shown.map((submission) => (
              <StudentRow
                key={submission.id}
                submission={submission}
                active={submission.id === active?.id}
                drafting={submission.id === draftingSubmissionId}
                queued={isPending(submission) && submission.id !== draftingSubmissionId}
                onPick={() => onActiveSubmission(submission.id)}
              />
            ))}
            {shown.length === 0 ? <div className="grade-empty">Nenhum aluno neste filtro.</div> : null}
          </div>
        </aside>

        <section className="grade-preview">
          {active ? (
            <>
              <div className="preview-head">
                <div className="preview-student">
                  <div className="student-avatar">{initials(active.student_name, "AL")}</div>
                  <div className="preview-student-copy">
                    <div className="name">{studentLabel(active)}</div>
                    <div className="file">
                      {active.files && active.files.length > 1
                        ? `${active.files.length} arquivos`
                        : `${active.source_name} · ${active.mime_type}`}
                      {active.confidence != null && !blockedActive
                        ? ` · ${Math.round(active.confidence * 100)}% confiança`
                        : ""}
                      {isVisualSubmission(active) ? <span className="visual-badge">visual transcrito</span> : null}
                    </div>
                  </div>
                </div>
                <div className="preview-nav">
                  <button className="nav-arrow" onClick={() => goRelative(-1)} aria-label="Anterior">
                    <AppIcon name="chevronRight" className="ico flip" />
                  </button>
                  <span className="counter">
                    {activeIndex + 1} / {job.submissions.length}
                  </span>
                  <button className="nav-arrow" onClick={() => goRelative(1)} aria-label="Próximo">
                    <AppIcon name="chevronRight" />
                  </button>
                </div>
              </div>
              <div className="preview-doc">
                {blockedActive ? (
                  <BlockedEvidence jobId={job.id} submission={active} busy={busy} onRetry={() => onRetry(active)} />
                ) : (
                  <SubmissionFiles job={job} submission={active} />
                )}
              </div>
            </>
          ) : (
            <div className="grade-empty">Selecione um aluno.</div>
          )}
        </section>

        {active ? activePending ? (
          <aside className="suggestion-panel aside-drafting" aria-live="polite">
            <AppIcon name={activeDrafting ? "loader" : "sparkle"} className={activeDrafting ? "ico spin" : "ico"} />
            <h3>{activeDrafting ? "Gerando rascunho..." : "Na fila"}</h3>
            <p>
              {activeDrafting
                ? "A IA está avaliando esta entrega com a rubrica. O resultado aparece aqui em instantes."
                : "Esta entrega está na fila e será avaliada em seguida."}
            </p>
          </aside>
        ) : (
          <aside className="suggestion-panel" aria-live="polite">
            <div className="aside-head">
              <div className="aside-eyebrow">
                {blockedActive ? (
                  <>
                    <AppIcon name="triangleAlert" /> Não foi possível corrigir
                  </>
                ) : (
                  <>
                    <AppIcon name="sparkle" /> IA sugere
                  </>
                )}
              </div>
              <div className="aside-score">
                <span className="big">{active.ai_score != null ? active.ai_score : "—"}</span>
                <span className="of">/100</span>
                {active.confidence != null && !blockedActive ? (
                  <span className="conf">
                    confiança <strong>{Math.round(active.confidence * 100)}%</strong>
                  </span>
                ) : null}
              </div>
              {active.feedback && !blockedActive ? <div className="aside-summary">{active.feedback}</div> : null}
            </div>

            <PrivacyBlock submission={active} />

            {blockedActive ? (
              <div className="flag-banner danger">
                <AppIcon name="triangleAlert" />
                <div>
                  <strong>A IA não pôde gerar um rascunho.</strong>
                  {active.error ? (
                    <>
                      {" "}
                      <span className="error-layer">{errorLayerLabel(active.error)}</span>: {safeStatusLabel(active.error)}.
                    </>
                  ) : null}{" "}
                  {active.error_retryable ? "Tente novamente, " : ""}dê uma nota manual ou deixe esta entrega para
                  correção manual.
                </div>
              </div>
            ) : active.flag ? (
              <div className="flag-banner warn">
                <AppIcon name="triangleAlert" />
                <div>
                  <strong>Vale uma olhada.</strong> {safeStatusLabel(active.flag)}.
                </div>
              </div>
            ) : null}

            {job.rubric_mode === "infer" && hasDefaultCriteria(job) ? (
              <div className="criteria-pending">
                <AppIcon name="sparkle" />
                A IA vai sugerir os critérios após analisar as entregas.
              </div>
            ) : (
              <div className="breakdown">
                {job.criteria.map((criterion) => (
                  <div key={criterion.id} className="bd-row">
                    <div className="bd-head">
                      <span className="bd-name">{criterion.name}</span>
                      <span className="bd-weight">{criterion.weight}%</span>
                    </div>
                    {criterion.latest_ai_note ? <div className="bd-note">{criterion.latest_ai_note}</div> : null}
                  </div>
                ))}
              </div>
            )}

            <label className="score-input">
              <span>{blockedActive ? "Nota manual" : "Nota final"}</span>
              <input
                value={scoreText}
                onChange={(event) => setScoreText(event.target.value)}
                inputMode="decimal"
                placeholder={blockedActive ? "—" : undefined}
              />
            </label>
            <label className="feedback-input">
              <span>Feedback</span>
              <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
            </label>

            <div className="suggestion-actions">
              {!blockedActive || active.error_retryable ? (
                <button className="btn btn-secondary" onClick={() => onRetry(active)} disabled={busy}>
                  <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
                  {blockedActive ? "Tentar novamente" : "Repetir"}
                </button>
              ) : null}
              <button className="btn btn-ai" onClick={accept} disabled={!hasValidScore || busy}>
                <AppIcon name="check" />
                {blockedActive ? "Salvar nota manual" : "Aceitar e avançar"}
              </button>
            </div>
            <div className="kbd-hints">
              <span className="kbd-neutral">J</span> próximo · <span className="kbd-neutral">K</span> anterior ·{" "}
              <span className="kbd-neutral">Enter</span> aceitar
            </div>
          </aside>
        ) : null}
      </div>
      {reportOpen && audit ? <AuditReport audit={audit} onClose={() => setReportOpen(false)} /> : null}
    </div>
  );
}

