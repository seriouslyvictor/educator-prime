import { api } from "../../lib/api";
import type { GradingJob, GradingSubmission } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import { safeStatusLabel } from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

function scoreOf(submission: GradingSubmission): number | null {
  return submission.final_score ?? submission.ai_score ?? null;
}

export function GraderWrap({
  job,
  busy,
  onBack,
  onQueue,
  onDeleteCache,
}: {
  job: GradingJob;
  busy: boolean;
  onBack: () => void;
  onQueue: () => void;
  onDeleteCache: () => void;
}) {
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

  return (
    <div className={graderStyles["grader-page"]}>
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
                    <span>{submission.student_name ?? submission.student_email ?? "Aluno desconhecido"}</span>
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
        </section>

        <aside className="wrap-side">
          <div className="mini-note">
            Estes são rascunhos de correção salvos. Exporte o CSV ou continue revisando; nada é publicado no
            Classroom nesta versão.
          </div>
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
