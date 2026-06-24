import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "../../lib/api";
import type { GradingJob, GradingSubmission } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { classroomActivityUrl, firstStudentPostingUrl, scoreOf, studentLabel, withAuthUser } from "./domain";
import { safeStatusLabel } from "./graderStatus";
import graderStyles from "./Grader.module.css";
import { PostingPiP } from "./pip/PostingPiP";
import { useDocumentPiP } from "./pip/useDocumentPiP";
void graderStyles;

function postingClipboardText(submission: GradingSubmission): string {
  return `Nota: ${scoreOf(submission)}/100\n\n${submission.feedback ?? ""}`;
}

export function GraderWrap({
  job,
  busy,
  accountEmail,
  onBack,
  onQueue,
  onDeleteCache,
  onJobUpdate,
}: {
  job: GradingJob;
  busy: boolean;
  accountEmail: string | null;
  onBack: () => void;
  onQueue: () => void;
  onDeleteCache: () => void;
  onJobUpdate: (job: GradingJob) => void;
}) {
  const [preparingLinks, setPreparingLinks] = useState(false);
  const [postingBusyId, setPostingBusyId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [postingError, setPostingError] = useState<string | null>(null);

  // Document PiP companion
  const { isSupported: pipSupported, isOpen: pipOpen, pipWindow, open: openPiP, close: closePiP } = useDocumentPiP();
  // Queue snapshot: captured when PiP opens so auto-marking doesn't reshuffle under the card
  const pipQueueRef = useRef<GradingSubmission[]>([]);

  const grades = job.submissions
    .map(scoreOf)
    .filter((value): value is number => value != null);
  const mean = grades.length ? Math.round(grades.reduce((sum, value) => sum + value, 0) / grades.length) : 0;
  const sorted = [...grades].sort((a, b) => a - b);
  const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
  const min = sorted[0] ?? 0;
  const max = sorted[sorted.length - 1] ?? 0;
  const timeSaved = ((job.submissions.length * 8) / 60).toFixed(1);

  const buckets = Array.from({ length: 10 }, () => 0);
  for (const grade of grades) {
    buckets[Math.min(9, Math.max(0, Math.floor(grade / 10)))] += 1;
  }
  const peak = Math.max(1, ...buckets);

  const outliers = job.submissions.filter(
    (submission) => submission.flag || submission.error || (scoreOf(submission) ?? 100) < 70,
  );
  const gradedSubmissions = useMemo(
    () =>
      job.submissions
        .filter((submission) => submission.final_score != null)
        .sort((a, b) => studentLabel(a).localeCompare(studentLabel(b), "pt-BR")),
    [job.submissions],
  );
  const postedCount = gradedSubmissions.filter((submission) => submission.posted_to_classroom).length;
  const missingClassroomLinks = gradedSubmissions.some((submission) => !submission.alternate_link);

  async function prepareClassroomLinks() {
    setPreparingLinks(true);
    setPostingError(null);
    try {
      onJobUpdate(await api.prepareClassroomLinks(job.id));
    } catch (caught) {
      setPostingError(caught instanceof Error ? caught.message : "Falha ao preparar links do Classroom.");
    } finally {
      setPreparingLinks(false);
    }
  }

  useEffect(() => {
    if (!gradedSubmissions.length || !missingClassroomLinks || preparingLinks) return;
    void prepareClassroomLinks();
  }, [gradedSubmissions.length, missingClassroomLinks, job.id]);

  async function copyPostingText(submission: GradingSubmission) {
    setPostingError(null);
    try {
      await navigator.clipboard.writeText(postingClipboardText(submission));
      setCopiedId(submission.id);
      window.setTimeout(() => {
        setCopiedId((current) => (current === submission.id ? null : current));
      }, 1600);
    } catch {
      setPostingError("Não foi possível copiar para a área de transferência.");
    }
  }

  async function togglePosted(submission: GradingSubmission) {
    setPostingBusyId(submission.id);
    setPostingError(null);
    try {
      const updated = await api.markSubmissionPosted(
        job.id,
        submission.id,
        !submission.posted_to_classroom,
      );
      onJobUpdate(updated);
    } catch (caught) {
      setPostingError(caught instanceof Error ? caught.message : "Falha ao marcar postagem.");
    } finally {
      setPostingBusyId(null);
    }
  }

  // PiP helpers
  const pipQueue = useMemo(
    () => gradedSubmissions.filter((s) => !s.posted_to_classroom),
    [gradedSubmissions],
  );

  async function handleOpenPiP() {
    // Snapshot queue at open time so auto-marking doesn't reshuffle mid-session
    pipQueueRef.current = pipQueue;
    // Order matters. documentPictureInPicture.requestWindow() requires the
    // opener to be visible + user-activated; window.open()'s new tab makes the
    // opener hidden. So kick off the PiP request FIRST (synchronously, while the
    // opener is still visible), then open the Classroom tab in the SAME gesture
    // turn so neither popup is blocked. Awaiting before window.open would let the
    // new tab hide the opener and the PiP would silently fail to render.
    const pipReady = openPiP();
    const target = firstStudentPostingUrl(pipQueueRef.current, job, accountEmail);
    window.open(target, "classroom-posting");
    await pipReady;
  }

  async function handlePiPMarkPosted(submission: GradingSubmission) {
    setPostingError(null);
    try {
      const updated = await api.markSubmissionPosted(job.id, submission.id, true);
      onJobUpdate(updated);
    } catch (caught) {
      setPostingError(caught instanceof Error ? caught.message : "Falha ao marcar postagem via PiP.");
    }
  }

  return (
    <div className={graderStyles["g-page"]}>
      <GraderTopbar
        title={`Pronto para fechar · ${job.activity_title}`}
        subtitle={`${grades.length} de ${job.total_submissions} com nota · ${job.flagged_submissions} para uma segunda olhada`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              <AppIcon name="chevronRight" className="ico flip" />
              Revisar rascunhos
            </button>
            <button className="btn btn-primary" onClick={onQueue}>
              Salvar e voltar à fila
            </button>
          </>
        }
      />
      <div className="wrap-grid">
        <section className="wrap-main">
          <div className="summary-row">
            <SummaryStat label="Média" value={`${mean}`} sub="/100" />
            <SummaryStat label="Mediana" value={`${median}`} sub="/100" />
            <SummaryStat label="Amplitude" value={`${min}–${max}`} />
            <SummaryStat label="Tempo economizado" value={`~${timeSaved}h`} sub="vs. manual" />
          </div>

          <div className="distribution-card">
            <div className="dist-head">
              <h3>Distribuição de notas</h3>
              <span>faixas de 10</span>
            </div>
            <div className="histogram">
              {buckets.map((count, index) => (
                <div key={index} className={`hb ${index < 3 ? "dim" : index < 6 ? "warn" : ""}`}>
                  {count > 0 ? <span className="hb-count">{count}</span> : null}
                  <div className="hb-bar" style={{ height: `${(count / peak) * 100}%` }} />
                </div>
              ))}
            </div>
            <div className="histogram-axis">
              {["0", "10", "20", "30", "40", "50", "60", "70", "80", "90"].map((x) => (
                <div key={x} className="ax">
                  {x}
                </div>
              ))}
            </div>
          </div>

          <div className="outlier-card">
            <div className="grader-section-head">
              <span>Vale uma segunda olhada</span>
              <span>{outliers.length}</span>
            </div>
            {outliers.length ? (
              outliers.map((submission) => (
                <div key={submission.id} className="outlier-row">
                  <div className="outlier-copy">
                    <span>{studentLabel(submission)}</span>
                    <small>
                      {submission.error
                        ? safeStatusLabel(submission.error)
                        : submission.flag
                          ? safeStatusLabel(submission.flag)
                          : "Nota baixa"}
                    </small>
                  </div>
                  <strong>{scoreOf(submission) ?? "—"}</strong>
                </div>
              ))
            ) : (
              <div className="grader-empty">Nenhum rascunho sinalizado neste conjunto.</div>
            )}
          </div>

          <div className="classroom-post-card">
            <div className="grader-section-head classroom-post-head">
              <span>Postar no Classroom</span>
              <span>
                {postedCount} de {gradedSubmissions.length} postados
              </span>
            </div>
            <div className="classroom-post-note">
              A API do Classroom não permite autopostar notas e feedback em atividades criadas pelo professor; este painel acelera a postagem manual.
            </div>
            {postingError ? <div className="classroom-post-error">{postingError}</div> : null}
            <div className="classroom-post-actions">
              <button
                className="btn btn-secondary"
                onClick={() => void prepareClassroomLinks()}
                disabled={busy || preparingLinks}
              >
                <AppIcon name={preparingLinks ? "loader" : "refresh"} className={preparingLinks ? "ico spin" : "ico"} />
                Preparar postagem
              </button>
              <button
                className="btn btn-primary"
                onClick={() => void handleOpenPiP()}
                disabled={!pipSupported || pipQueue.length === 0}
                title={
                  !pipSupported
                    ? "Requer Chrome ou Edge 116+"
                    : pipQueue.length === 0
                    ? "Nenhum aluno pendente de postagem"
                    : undefined
                }
              >
                <AppIcon name="pictureInPicture" />
                Postagem guiada
              </button>
            </div>
            {gradedSubmissions.length ? (
              <div className="classroom-post-list">
                {gradedSubmissions.map((submission) => {
                  const score = scoreOf(submission);
                  const classroomUrl = submission.alternate_link
                    ? withAuthUser(submission.alternate_link, accountEmail)
                    : classroomActivityUrl(job, accountEmail);
                  const postedBusy = postingBusyId === submission.id;
                  return (
                    <div key={submission.id} className="classroom-post-row">
                      <div className="classroom-post-copy">
                        <div className="classroom-post-title">
                          <span>{studentLabel(submission)}</span>
                          <strong>{score}/100</strong>
                        </div>
                        <p>{submission.feedback || "Sem feedback registrado."}</p>
                      </div>
                      <div className="classroom-post-buttons">
                        <button
                          className="btn btn-secondary"
                          onClick={() => void copyPostingText(submission)}
                        >
                          <AppIcon name={copiedId === submission.id ? "check" : "clipboard"} />
                          {copiedId === submission.id ? "Copiado!" : "Copiar nota + feedback"}
                        </button>
                        <a
                          className="btn btn-secondary"
                          href={classroomUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <AppIcon name="externalLink" />
                          {submission.alternate_link ? "Abrir no Classroom" : "Abrir atividade"}
                        </a>
                        <button
                          className={`btn ${submission.posted_to_classroom ? "btn-primary" : "btn-secondary"}`}
                          onClick={() => void togglePosted(submission)}
                          disabled={postedBusy}
                        >
                          <AppIcon name={postedBusy ? "loader" : "checkCircle"} className={postedBusy ? "ico spin" : "ico"} />
                          {submission.posted_to_classroom ? "Postado" : "Marcar como postado"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="grader-empty">Nenhuma entrega com nota final para postar.</div>
            )}
          </div>
        </section>

        <aside className="wrap-side">
          <a className="btn btn-primary export-link" href={api.gradingCsvUrl(job.id)}>
            <AppIcon name="fileDown" /> Exportar CSV
          </a>
          <button className="btn btn-secondary" onClick={onDeleteCache} disabled={busy || !job.cache_expires_at}>
            <AppIcon name={busy ? "loader" : "archive"} className={busy ? "ico spin" : "ico"} />
            Apagar arquivos em cache agora
          </button>
          <div className="cache-note">
            {job.cache_expires_at
              ? `Arquivos em cache expiram em ${new Date(job.cache_expires_at).toLocaleString("pt-BR")}`
              : "Arquivos em cache apagados; as notas continuam salvas."}
          </div>
        </aside>
      </div>

      {/* PiP posting companion portal */}
      {pipOpen && pipWindow && pipQueueRef.current.length > 0 && (
        <PostingPiP
          job={job}
          queue={pipQueueRef.current}
          pipWindow={pipWindow}
          onMarkPosted={(submission) => void handlePiPMarkPosted(submission)}
          onClose={closePiP}
        />
      )}
    </div>
  );
}

function SummaryStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="summary-stat">
      <div className="lbl">{label}</div>
      <div className="val">
        {value}
        {sub ? <span className="sub">{sub}</span> : null}
      </div>
    </div>
  );
}
