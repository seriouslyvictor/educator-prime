import { api } from "../../lib/api";
import type { GradingJob } from "../../types";
import { AppIcon } from "../icons";
import { GraderTopbar } from "./GraderTopbar";
import graderStyles from "./Grader.module.css";
void graderStyles;

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
  const scores = job.submissions.map((submission) => submission.final_score ?? 0);
  const average = scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0;
  const outliers = job.submissions.filter((submission) => (submission.final_score ?? 0) < 70 || submission.flag);

  return (
    <div className={graderStyles["grader-page"]}>
      <GraderTopbar
        title="Fechamento dos rascunhos"
        subtitle={`${job.activity_title} · ${job.course_name}`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Revisar rascunhos
            </button>
            <button className="btn btn-primary" onClick={onQueue}>
              Salvar conjunto
            </button>
          </>
        }
      />
      <div className="wrap-grid">
        <section className="wrap-main">
          <div className="wrap-stats">
            <div className="wrap-stat">
              <span>Revisados</span>
              <strong>
                {job.reviewed_submissions}/{job.total_submissions}
              </strong>
            </div>
            <div className="wrap-stat">
              <span>Média</span>
              <strong>{average}</strong>
            </div>
            <div className="wrap-stat">
              <span>Precisa revisar</span>
              <strong>{outliers.length}</strong>
            </div>
          </div>
          <div className="distribution">
            {job.submissions.map((submission) => (
              <div key={submission.id} className="dist-row">
                <span>{submission.student_name ?? "Desconhecido"}</span>
                <div>
                  <i style={{ width: `${Math.min(100, submission.final_score ?? 0)}%` }} />
                </div>
                <strong>{submission.final_score ?? "-"}</strong>
              </div>
            ))}
          </div>
          <section className="grader-section outliers">
            <div className="grader-section-head">
              <span>Desvios e sinais</span>
              <span>{outliers.length}</span>
            </div>
            {outliers.length ? (
              outliers.map((submission) => (
                <div key={submission.id} className="outlier-row">
                  <span>{submission.student_name ?? submission.student_email ?? "Aluno desconhecido"}</span>
                  <small>{submission.flag ?? "Nota baixa"}</small>
                </div>
              ))
            ) : (
              <div className="grader-empty">Nenhum rascunho sinalizado neste conjunto.</div>
            )}
          </section>
        </section>
        <aside className="wrap-side">
          <div className="mini-note">
            Estes são apenas rascunhos de correção salvos. Exporte o CSV ou continue revisando; nada é publicado no Classroom na V1.
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
              : "Arquivos em cache apagados; rascunhos de notas continuam salvos."}
          </div>
        </aside>
      </div>
    </div>
  );
}


