import { useState } from "react";
import type { GradingQueueItem } from "../../types";
import { AppIcon } from "../icons";
import { SearchBox } from "../ui";
import graderStyles from "./Grader.module.css";
void graderStyles;

export function GraderQueue({
  items,
  loading,
  onRefresh,
  onSetup,
  onOpenJob,
  onDownloadInstead,
}: {
  items: GradingQueueItem[];
  loading: boolean;
  onRefresh?: () => void;
  onSetup: (item: GradingQueueItem) => void;
  onOpenJob: (jobId: string) => void;
  onDownloadInstead: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = items.filter((item) =>
    `${item.course_name} ${item.activity_title}`.toLowerCase().includes(query.toLowerCase()),
  );
  const drafting = filtered.filter((item) => item.latest_job_id && item.status !== "completed");
  const ready = filtered.filter((item) => !item.latest_job_id);
  const completed = filtered.filter((item) => item.status === "completed");
  const hasItems = items.length > 0;
  const hasFilteredItems = filtered.length > 0;

  return (
    <div className={graderStyles["g-page"]} data-screen-label="01 Grader - Queue">
      <div className="g-topbar">
        <div>
          <div className="g-crumb">
            <span>
              <span className="ai-glyph">✦</span> Corrigir com IA
            </span>
          </div>
          <h1 className="g-title">O que você quer corrigir?</h1>
          <div className="g-subtitle">
            {hasItems
              ? `${items.length} atividades acompanhadas pela IA`
              : "Envie uma atividade pela tela de Turmas para preparar a correção com IA."}
          </div>
        </div>
        <div className="g-topbar-actions">
          {hasItems ? (
            <SearchBox value={query} onChange={setQuery} placeholder="Filtrar atividades..." />
          ) : null}
          <div className="g-actions">
            <button className="btn btn-secondary" onClick={onDownloadInstead}>
              <AppIcon name="download" /> Baixar em vez disso
            </button>
            {onRefresh ? (
              <button className="btn btn-primary" onClick={onRefresh} disabled={loading}>
                <AppIcon name={loading ? "loader" : "refresh"} className={loading ? "ico spin" : "ico"} />
                Atualizar
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="queue-wrap">
        {!hasItems ? (
          <div className="ai-empty-state">
            <div className="ai-empty-badge">
              <AppIcon name="sparkle" />
            </div>
            <h2>Nenhuma atividade na fila de IA</h2>
            <p>
              Escolha uma turma, encontre a atividade desejada e clique em Corrigir com IA.
              A auditoria de privacidade e os rascunhos aparecerão aqui quando a fila começar.
            </p>
            <div className="ai-empty-actions">
              <button className="btn btn-primary" onClick={onDownloadInstead}>
                <AppIcon name="classroom" /> Ir para Turmas
              </button>
            </div>
          </div>
        ) : !hasFilteredItems ? (
          <div className="queue-empty">Nenhuma atividade corresponde a "{query}".</div>
        ) : (
          <>
            {drafting.length > 0 ? (
              <ReferenceQueueSection
                title="Continue de onde parou"
                count={drafting.length}
                items={drafting}
                onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
              />
            ) : null}
            {ready.length > 0 ? (
              <ReferenceQueueSection
                title="Prontas para rascunho com IA"
                count={ready.length}
                items={ready}
                onPick={onSetup}
              />
            ) : null}
            {completed.length > 0 ? (
              <ReferenceQueueSection
                title="Conjuntos concluídos"
                count={completed.length}
                items={completed}
                onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
              />
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function ReferenceQueueSection({
  title,
  count,
  items,
  onPick,
}: {
  title: string;
  count: number;
  items: GradingQueueItem[];
  onPick: (item: GradingQueueItem) => void;
}) {
  return (
    <section>
      <div className="queue-section-head">
        <h2>{title}</h2>
        <span className="count">{count}</span>
      </div>
      <div className="queue-grid">
        {items.map((item) => (
          <ReferenceQueueCard
            key={`${item.course_id}-${item.activity_id}-${item.latest_job_id ?? "new"}`}
            item={item}
            onPick={onPick}
          />
        ))}
      </div>
    </section>
  );
}

function ReferenceQueueCard({
  item,
  onPick,
}: {
  item: GradingQueueItem;
  onPick: (item: GradingQueueItem) => void;
}) {
  const total = item.total_submissions || item.submission_count || 0;
  const reviewed = item.reviewed_submissions || 0;
  const pct = total > 0 ? Math.min(100, (reviewed / total) * 100) : 0;
  const status = referenceQueueStatus(item);
  const featured = status.cls === "ai" || status.cls === "drafting";

  return (
    <button className={`queue-card ${featured ? "featured" : ""}`} onClick={() => onPick(item)}>
      <div className="queue-card-top">
        <div className="queue-card-copy">
          <div className="queue-course">
            <span className="dot" />
            {item.course_name}
          </div>
          <h3 className="queue-card-title">{item.activity_title}</h3>
        </div>
        <span className={`qc-pill ${status.cls}`}>
          <AppIcon name={status.icon} />
          {status.label}
        </span>
      </div>

      <div className="queue-card-meta">
        <span>Atividade</span>
        {item.due_label ? (
          <>
            <span className="sep" />
            <span>{item.due_label}</span>
          </>
        ) : null}
        <span className="sep" />
        <span>{item.submission_count} entregas</span>
      </div>

      <div className="queue-card-progress">
        <div className="qcp-bar">
          <div className={`qcp-bar-fill ${status.cls === "ai" ? "ai" : ""}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="qcp-label">
          {reviewed}/{total} revisadas
        </span>
      </div>

      <div className="queue-card-footer">
        <span className="queue-card-note">
          {status.cls === "posted" ? "Rascunhos concluídos" : <><span className="ai-glyph">✦</span> pronto para IA</>}
        </span>
        <span className="qc-cta">
          {status.cta}
          <AppIcon name="chevronRight" />
        </span>
      </div>
    </button>
  );
}

export function referenceQueueStatus(item: GradingQueueItem): {
  label: string;
  cls: string;
  icon: "sparkle" | "eye" | "settings" | "checkCircle";
  cta: string;
} {
  if (item.status === "completed") return { label: "Concluída", cls: "posted", icon: "checkCircle", cta: "Abrir" };
  if (item.status === "reviewing") return { label: "Em revisão", cls: "reviewing", icon: "eye", cta: "Revisar" };
  if (item.latest_job_id) return { label: "Rascunhando", cls: "drafting", icon: "settings", cta: "Retomar" };
  return { label: "IA pronta", cls: "ai", icon: "sparkle", cta: "Começar" };
}


