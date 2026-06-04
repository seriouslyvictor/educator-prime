import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import type {
  GradingJob,
  GradingQueueItem,
  GradingSubmission,
  PrivacyAudit,
  RubricMode,
  TeacherLoopMode,
} from "../types";
import { AppIcon } from "./icons";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  RadioGroup,
  RadioItem,
  Tabs,
  TabsList,
  TabsTrigger,
} from "./ui";

const rubricModes: Array<{
  id: RubricMode;
  title: string;
  copy: string;
  icon: "sparkle" | "fileText" | "settings" | "archive" | "shield";
}> = [
  { id: "infer", title: "Inferir pelo trabalho", copy: "Deixe o rascunho usar a atividade e os arquivos.", icon: "sparkle" },
  { id: "brief", title: "Orientação simples", copy: "Cole uma nota curta de correção para o rascunho.", icon: "fileText" },
  { id: "structured", title: "Rubrica estruturada", copy: "Use critérios com pesos antes do rascunho.", icon: "settings" },
  { id: "saved", title: "Salva", copy: "Reutilize uma rubrica de trabalhos recentes.", icon: "archive" },
  { id: "calibrate", title: "Calibrar primeiro", copy: "Use exemplos para ajustar o rascunho ao seu estilo.", icon: "shield" },
];

const loopModes: Array<{
  id: TeacherLoopMode;
  title: string;
  copy: string;
}> = [
  { id: "auto", title: "Correção automática", copy: "A IA rascunha tudo; você revisa apenas linhas sinalizadas" },
  { id: "approve", title: "Aprovar cada uma", copy: "A IA propõe uma nota por aluno; você confirma" },
  { id: "cowrite", title: "Coescrever", copy: "A IA mostra o raciocínio; você escreve a nota" },
  { id: "off", title: "IA desligada", copy: "Você corrige manualmente; a IA só prepara a tabela" },
];

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
    <div className="g-page" data-screen-label="01 Grader - Queue">
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
            <label className="search">
              <AppIcon name="search" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filtrar atividades..."
              />
            </label>
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

function referenceQueueStatus(item: GradingQueueItem): {
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

function LegacyGraderQueue({
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
  const reviewing = filtered.filter((item) => item.latest_job_id && item.status !== "completed");
  const ready = filtered.filter((item) => !item.latest_job_id);
  const completed = filtered.filter((item) => item.status === "completed");

  return (
    <div className="grader-page">
      <GraderTopbar
        title="Corrigir com IA"
        subtitle="Correção em rascunho, ao lado do fluxo de download."
        action={
          <>
            <button className="btn btn-secondary" onClick={onDownloadInstead}>
              <AppIcon name="download" /> Baixar em vez disso
            </button>
            {onRefresh ? (
              <button className="btn btn-primary" onClick={onRefresh} disabled={loading}>
                <AppIcon name={loading ? "loader" : "refresh"} className={loading ? "ico spin" : "ico"} />
                Atualizar
              </button>
            ) : null}
          </>
        }
      />

      <div className="grader-search">
        <label className="search">
          <AppIcon name="search" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar turmas ou atividades"
          />
        </label>
      </div>

      <div className="grader-queue">
        <QueueSection
          title="Continue de onde parou"
          empty="Nenhum rascunho de correção em andamento."
          items={reviewing}
          onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
        />
        <QueueSection title="Prontas para rascunho com IA" empty="Nenhuma atividade pronta." items={ready} onPick={onSetup} />
        <QueueSection
          title="Conjuntos de rascunhos salvos"
          empty="Conjuntos concluídos aparecerão aqui."
          items={completed}
          onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
        />
      </div>
    </div>
  );
}

function QueueSection({
  title,
  empty,
  items,
  onPick,
}: {
  title: string;
  empty: string;
  items: GradingQueueItem[];
  onPick: (item: GradingQueueItem) => void;
}) {
  return (
    <section className="grader-section">
      <div className="grader-section-head">
        <span>{title}</span>
        <span>{items.length}</span>
      </div>
      {items.length === 0 ? (
        <div className="grader-empty">{empty}</div>
      ) : (
        <div className="grader-card-list">
          {items.map((item) => (
            <button
              key={`${item.course_id}-${item.activity_id}-${item.latest_job_id ?? "new"}`}
              className="grader-card"
              onClick={() => onPick(item)}
            >
              <div className="grader-card-main">
                <div className="grader-card-title">{item.activity_title}</div>
                <div className="grader-card-sub">
                  {item.course_name} · {item.submission_count} entregas
                  {item.due_label ? ` · Prazo ${item.due_label}` : ""}
                </div>
              </div>
              <div className="grader-card-status">
                {item.latest_job_id ? `${item.reviewed_submissions}/${item.total_submissions} revisadas` : "Configurar"}
              </div>
              <AppIcon name="chevronRight" />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

export function GraderSetup({
  item,
  busy,
  onBack,
  onStart,
}: {
  item: GradingQueueItem;
  busy: boolean;
  onBack: () => void;
  onStart: (payload: { rubricMode: RubricMode; teacherLoop: TeacherLoopMode; rubricText: string }) => void;
}) {
  const [rubricMode, setRubricMode] = useState<RubricMode>("infer");
  const [teacherLoop, setTeacherLoop] = useState<TeacherLoopMode>("approve");
  const [rubricText, setRubricText] = useState("");
  const selectedRubric = rubricModes.find((mode) => mode.id === rubricMode) ?? rubricModes[0];

  return (
    <div className="grader-page">
      <GraderTopbar
        title="Configurar rubrica"
        subtitle={`${item.course_name} · ${item.activity_title}`}
        action={
          <button className="btn btn-secondary" onClick={onBack}>
            Voltar
          </button>
        }
      />
      <div className="setup-grid setup-grid-contract">
        <section className="setup-main setup-main-contract">
          <Tabs className="rubric-tabs">
            <TabsList>
            {rubricModes.map((mode) => (
              <TabsTrigger
                key={mode.id}
                active={rubricMode === mode.id}
                onClick={() => setRubricMode(mode.id)}
              >
                <AppIcon name={mode.icon} />
                <span>{mode.title}</span>
              </TabsTrigger>
            ))}
            </TabsList>
          </Tabs>

          <Card className="rubric-panel">
            <CardContent>
              {rubricMode !== "saved" ? <p className="rubric-mode-copy">{selectedRubric.copy}</p> : null}
              {rubricMode === "saved" ? (
                <div className="saved-rubric-list">
                  {[
                    ["AP Bio · Relatório de laboratório (4 partes)", "12 vezes · última em 14 de maio", "4 critérios"],
                    ["Literatura · Redação (5 critérios)", "8 vezes", "4 critérios"],
                    ["Álgebra · Lista de problemas", "23 vezes", "4 critérios"],
                  ].map((row, index) => (
                    <button key={row[0]} className={`saved-rubric-row ${index === 0 ? "active" : ""}`}>
                      <span className="saved-rubric-dot" />
                      <span>
                        <strong>{row[0]}</strong>
                        <small>{row[1]}</small>
                      </span>
                      <em>{row[2]}</em>
                      <AppIcon name="eye" />
                    </button>
                  ))}
                </div>
              ) : (
                <label className="rubric-input">
                  <span>{rubricMode === "infer" ? "Notas opcionais" : "Notas da rubrica"}</span>
                  <textarea
                    value={rubricText}
                    onChange={(event) => setRubricText(event.target.value)}
                    placeholder="Tom, prioridades, evidências exigidas ou critérios que o rascunho deve respeitar."
                  />
                </label>
              )}
            </CardContent>
            <CardFooter>
              <span>Selecionado: {rubricMode === "saved" ? "AP Bio · Relatório de laboratório (4 partes)" : selectedRubric.title}</span>
              <div className="setup-footer-actions">
                <button className="btn btn-ghost" onClick={onBack}>
                  Cancelar
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => onStart({ rubricMode, teacherLoop, rubricText })}
                  disabled={busy}
                >
                  <AppIcon name={busy ? "loader" : "sparkle"} className={busy ? "ico spin" : "ico"} />
                  {item.submission_count > 0
                    ? `Auditar privacidade de ${item.submission_count}`
                    : "Auditar privacidade"}
                </button>
              </div>
            </CardFooter>
          </Card>
        </section>

        <aside className="setup-side setup-side-contract">
          <Card className="context-card">
            <CardHeader>
              <CardTitle>Contexto que a IA tem</CardTitle>
            </CardHeader>
            <CardContent>
              {[
                ["Título + descrição da atividade", ""],
                ["Entregas dos alunos", item.submission_count > 0 ? `${item.submission_count} arquivos` : "carregadas ao auditar"],
                ["Materiais anexados", "2 PDFs"],
                ["Atividades corrigidas antes", "4 exemplos"],
              ].map((row) => (
                <div className="context-row" key={row[0]}>
                  <AppIcon name="checkCircle" />
                  <span>{row[0]}</span>
                  <em>{row[1]}</em>
                </div>
              ))}
              <div className="context-row muted">
                <AppIcon name="x" />
                <span>Lista da turma (nomes ocultos)</span>
                <em>privacidade</em>
              </div>
            </CardContent>
          </Card>

          <Card className="tip-card">
            <CardContent>
              <div className="tip-title">
                <AppIcon name="sparkle" />
                Dica
              </div>
              <p>
                Use Inferir para novos formatos de atividade. A IA costuma identificar a estrutura e sugerir critérios
                compatíveis.
              </p>
            </CardContent>
          </Card>

          <Card className="teacher-loop-card">
            <CardHeader>
              <CardTitle>Professor no processo</CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup>
                {loopModes.map((mode) => (
                  <RadioItem
                    key={mode.id}
                    active={teacherLoop === mode.id}
                    onClick={() => setTeacherLoop(mode.id)}
                  >
                    <strong>{mode.title}</strong>
                    <small>{mode.copy}</small>
                  </RadioItem>
                ))}
              </RadioGroup>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

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
    <div className="grader-review">
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

function privacyLabel(status?: string | null) {
  if (!status) return "Não verificado";
  const labels: Record<string, string> = {
    clean: "limpo",
    redacted: "redigido",
    partial_redaction: "redação parcial",
    high_reidentification_risk: "alto risco de reidentificação",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function extractionLabel(status?: string | null) {
  if (!status) return "Pendente";
  const labels: Record<string, string> = {
    supported: "suportado",
    degraded: "degradado",
    unsupported: "não suportado",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function attemptLabel(status?: string | null) {
  if (!status) return "Pendente";
  const labels: Record<string, string> = {
    pending: "pendente",
    completed: "concluído",
    blocked: "bloqueado",
    failed: "falhou",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

function safeStatusLabel(value?: string | null) {
  if (!value) return "";
  const labels: Record<string, string> = {
    privacy_blocked: "bloqueado por privacidade",
    unsupported_file_type: "tipo de arquivo não suportado",
    high_reidentification_risk: "alto risco de reidentificação",
    partial_redaction: "redação parcial",
    low_confidence: "baixa confiança",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function privacyTone(submission?: GradingSubmission) {
  if (!submission?.privacy_status) return "neutral";
  if (submission.privacy_status === "clean") return "ok";
  if (submission.privacy_status === "redacted") return "warn";
  return "danger";
}

function extractionTone(submission?: GradingSubmission) {
  if (!submission?.extraction_status) return "neutral";
  if (submission.extraction_status === "supported") return "ok";
  if (submission.extraction_status === "degraded") return "warn";
  return "danger";
}

function attemptTone(submission?: GradingSubmission) {
  if (!submission?.ai_attempt_status) return "neutral";
  if (submission.ai_attempt_status === "completed") return "ok";
  if (submission.ai_attempt_status === "blocked") return "danger";
  return "warn";
}

function statusTone(submission: GradingSubmission) {
  if (submission.error || submission.ai_attempt_status === "blocked") return "danger";
  if (submission.flag || submission.privacy_status === "redacted" || submission.extraction_status === "degraded") {
    return "warn";
  }
  return "ok";
}

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
    <div className="grader-page">
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
    <div className="grader-page">
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

function GraderTopbar({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action: ReactNode;
}) {
  return (
    <header className="grader-topbar">
      <div>
        <div className="grader-title">{title}</div>
        <div className="grader-subtitle">{subtitle}</div>
      </div>
      <div className="grader-actions">{action}</div>
    </header>
  );
}
