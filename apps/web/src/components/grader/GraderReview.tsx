import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { GradingJob, GradingSubmission, GradingSubmissionFile, PrivacyAudit } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import {
  privacyLabel,
  privacyTone,
  redactionLabel,
  redactionSummary,
  safeStatusLabel,
} from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

type ReviewFilter = "all" | "flagged" | "pending" | "reviewed";

function initials(name: string | null | undefined, fallback: string): string {
  const source = (name ?? "").trim();
  if (!source) return fallback;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

function isBlocked(submission: GradingSubmission | undefined): boolean {
  return Boolean(submission?.error) || submission?.ai_attempt_status === "blocked";
}

function studentLabel(submission: GradingSubmission): string {
  return submission.student_name ?? submission.student_email ?? "Aluno desconhecido";
}

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
  const activeDrafting = Boolean(progress?.phase === "draft" && active && active.ai_score == null && !active.error);
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
                drafting={Boolean(progress?.phase === "draft" && submission.ai_score == null && !submission.error)}
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

        {active ? activeDrafting ? (
          <aside className="suggestion-panel aside-drafting" aria-live="polite">
            <AppIcon name="loader" className="ico spin" />
            <h3>Gerando rascunho...</h3>
            <p>A IA está avaliando esta entrega com a rubrica. O resultado aparece aqui em instantes.</p>
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
                  {active.error ? ` ${safeStatusLabel(active.error)}.` : ""} Tente extrair novamente, dê uma nota manual
                  ou deixe esta entrega para correção manual.
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
              <button className="btn btn-secondary" onClick={() => onRetry(active)} disabled={busy}>
                <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
                {blockedActive ? "Tentar de novo" : "Repetir"}
              </button>
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

function AuditStrip({ audit, onOpen }: { audit: PrivacyAudit; onOpen: () => void }) {
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

function AuditReport({ audit, onClose }: { audit: PrivacyAudit; onClose: () => void }) {
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
                <span className="ar-flags">{redactionSummary(row.redaction_counts)}</span>
              </div>
            ))}
          </section>
        </div>
      </div>
    </>
  );
}

function PrivacyBlock({ submission }: { submission: GradingSubmission }) {
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

function StudentRow({
  submission,
  active,
  drafting,
  onPick,
}: {
  submission: GradingSubmission;
  active: boolean;
  drafting: boolean;
  onPick: () => void;
}) {
  const blocked = isBlocked(submission);
  const meta = submission.reviewed
    ? { icon: "checkCircle" as const, tone: "ok", label: "revisado" }
    : blocked
      ? { icon: "triangleAlert" as const, tone: "danger", label: "bloqueado" }
      : submission.flag
        ? { icon: "triangleAlert" as const, tone: "warn", label: "verificar" }
        : { icon: "sparkle" as const, tone: "ai", label: "rascunho da IA" };

  return (
    <button className={`student-row ${active ? "active" : ""} ${drafting ? "drafting" : ""}`} onClick={onPick}>
      <div className="student-avatar small">{initials(submission.student_name, "AL")}</div>
      <div className="student-row-copy">
        <div className="student-name">{studentLabel(submission)}</div>
        <div className={`student-meta ${meta.tone}`}>
          {drafting ? <span className="dot-spin" /> : <AppIcon name={meta.icon} />}
          {drafting ? "gerando rascunho..." : meta.label}
        </div>
      </div>
      <div className="student-score">
        {drafting ? (
          <span className="skeleton score-skeleton" />
        ) : submission.final_score != null ? (
          <span className="final">{submission.final_score}</span>
        ) : submission.ai_score != null ? (
          <span className="ai-suggest">✦ {submission.ai_score}</span>
        ) : (
          <span className="none">—</span>
        )}
      </div>
    </button>
  );
}

// Mirror the backend's inline allowlist: only types it serves with
// `Content-Disposition: inline` are embedded; everything else is a download card.
const INLINE_IMAGE_MIME = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const INLINE_TEXT_MIME = new Set([
  "text/plain",
  "text/csv",
  "text/markdown",
  "text/x-python",
  "text/x-java-source",
  "text/x-c",
  "text/x-c++",
  "text/x-csharp",
  "text/x-go",
  "text/x-rust",
  "text/x-php",
  "text/x-ruby",
  "text/x-sql",
  "application/json",
  "application/ld+json",
  "application/xml",
  "application/xhtml+xml",
  "application/javascript",
  "application/typescript",
  "application/x-yaml",
  "application/yaml",
]);
const INLINE_TEXT_EXTENSIONS = new Set([
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".xml",
  ".yaml",
  ".yml",
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".css",
  ".scss",
  ".html",
  ".htm",
  ".java",
  ".c",
  ".h",
  ".cpp",
  ".hpp",
  ".cs",
  ".go",
  ".rs",
  ".php",
  ".rb",
  ".sql",
  ".sh",
  ".ps1",
  ".bat",
  ".ini",
  ".toml",
  ".lock",
]);

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function isInlineTextSubmission(sourceName: string, mime: string): boolean {
  if (mime.startsWith("text/") || INLINE_TEXT_MIME.has(mime)) return true;
  return mime === "application/octet-stream" && INLINE_TEXT_EXTENSIONS.has(extensionOf(sourceName));
}

// A student's submission may carry several attachments; show one tab per file.
function SubmissionFiles({ job, submission }: { job: GradingJob; submission: GradingSubmission }) {
  const files: GradingSubmissionFile[] = submission.files?.length
    ? submission.files
    : [{ source_file_id: submission.source_file_id, source_name: submission.source_name, mime_type: submission.mime_type }];
  const [activeFileId, setActiveFileId] = useState(files[0].source_file_id);
  useEffect(() => {
    setActiveFileId(files[0].source_file_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submission.id]);
  const activeFile = files.find((file) => file.source_file_id === activeFileId) ?? files[0];

  return (
    <>
      {files.length > 1 ? (
        <div className="file-tabs" role="tablist" aria-label="Arquivos da entrega">
          {files.map((file) => (
            <button
              key={file.source_file_id}
              role="tab"
              aria-selected={file.source_file_id === activeFile.source_file_id}
              className={`file-tab ${file.source_file_id === activeFile.source_file_id ? "active" : ""}`}
              onClick={() => setActiveFileId(file.source_file_id)}
            >
              <AppIcon name="fileText" /> {file.source_name}
            </button>
          ))}
        </div>
      ) : null}
      <SubmissionPreview job={job} submission={submission} file={activeFile} />
    </>
  );
}

function SubmissionPreview({
  job,
  submission,
  file,
}: {
  job: GradingJob;
  submission: GradingSubmission;
  file: GradingSubmissionFile;
}) {
  const url = api.submissionPreviewUrl(job.id, submission.id, file.source_file_id);
  const mime = (file.mime_type ?? "").split(";")[0].trim().toLowerCase();
  const title = `Entrega de ${studentLabel(submission)}`;

  if (INLINE_IMAGE_MIME.has(mime)) {
    return (
      <div className="preview-media">
        <img className="preview-image" src={url} alt={title} />
      </div>
    );
  }
  if (isInlineTextSubmission(file.source_name, mime)) {
    return <SubmissionTextPreview url={url} title={title} fileName={file.source_name} mimeType={file.mime_type} />;
  }
  if (mime === "application/pdf") {
    return <iframe className="preview-frame" src={url} title={title} />;
  }
  return (
    <div className="preview-card">
      <AppIcon name="fileText" />
      <div className="preview-card-copy">
        <strong>{file.source_name}</strong>
        <span>{file.mime_type || "arquivo"}</span>
      </div>
      <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
        <AppIcon name="download" /> Baixar original
      </a>
    </div>
  );
}

function SubmissionTextPreview({
  url,
  title,
  fileName,
  mimeType,
}: {
  url: string;
  title: string;
  fileName: string;
  mimeType: string;
}) {
  const [state, setState] = useState<{ loading: boolean; content: string; error: string | null }>({
    loading: true,
    content: "",
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, content: "", error: null });
    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("Falha ao carregar a previsualização.");
        return response.text();
      })
      .then((content) => {
        if (!cancelled) setState({ loading: false, content, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            loading: false,
            content: "",
            error: error instanceof Error ? error.message : "Falha ao carregar a previsualização.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return (
    <div className="preview-code" aria-label={title}>
      <div className="preview-code-toolbar">
        <div className="preview-code-copy">
          <strong>{fileName}</strong>
          <span>{mimeType || "texto"}</span>
        </div>
        <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
          <AppIcon name="download" /> Baixar original
        </a>
      </div>
      {state.loading ? (
        <div className="preview-code-state">
          <AppIcon name="loader" className="ico spin" /> Carregando previsualização
        </div>
      ) : state.error ? (
        <div className="preview-code-state danger">
          <AppIcon name="triangleAlert" /> {state.error}
        </div>
      ) : (
        <pre className="preview-code-body">
          <code>{state.content}</code>
        </pre>
      )}
    </div>
  );
}

function BlockedEvidence({
  jobId,
  submission,
  busy,
  onRetry,
}: {
  jobId: string;
  submission: GradingSubmission;
  busy: boolean;
  onRetry: () => void;
}) {
  const url = api.submissionPreviewUrl(jobId, submission.id);
  return (
    <div className="preview-blocked">
      <AppIcon name="triangleAlert" />
      <h2>Esta entrega não pôde ser lida pela IA</h2>
      <p>
        {submission.error ? `${safeStatusLabel(submission.error)}. ` : ""}
        Você ainda pode abrir o arquivo original, tentar extrair novamente ou dar uma nota manual no painel ao lado.
      </p>
      <div className="preview-blocked-actions">
        <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
          <AppIcon name="download" /> Baixar original
        </a>
        <button className="btn btn-ai" onClick={onRetry} disabled={busy}>
          <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
          Tentar extrair novamente
        </button>
      </div>
    </div>
  );
}
