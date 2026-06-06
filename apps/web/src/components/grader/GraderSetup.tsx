import { useState } from "react";
import type { GradingCriterionInput, GradingJob, GradingQueueItem, PrivacyAudit, RubricMode, TeacherLoopMode } from "../../types";
import { api } from "../../lib/api";
import { AppIcon } from "../icons";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, RadioGroup, RadioItem, Tabs, TabsList, TabsTrigger } from "../ui";
import { GraderTopbar } from "./GraderTopbar";
import { extractionLabel, privacyLabel, safeStatusLabel } from "./graderStatus";
import graderStyles from "./Grader.module.css";
void graderStyles;

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

export function GraderSetup({
  item,
  job,
  busy,
  audit,
  progress,
  onBack,
  onStart,
  onContinue,
  onRerun,
}: {
  item: GradingQueueItem;
  job: GradingJob | null;
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
  onBack: () => void;
  onStart: (payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
    criteria?: GradingCriterionInput[];
  }) => void;
  onContinue: () => void;
  onRerun: () => void;
}) {
  const [rubricMode, setRubricMode] = useState<RubricMode>("infer");
  const [teacherLoop, setTeacherLoop] = useState<TeacherLoopMode>("approve");
  const [rubricText, setRubricText] = useState("");
  const [criteria, setCriteria] = useState<GradingCriterionInput[]>([
    { name: "Funcionalidade", weight: 60, description: "Resolve o que foi pedido." },
    { name: "Clareza", weight: 40, description: "Organização, leitura e justificativa." },
  ]);
  const selectedRubric = rubricModes.find((mode) => mode.id === rubricMode) ?? rubricModes[0];
  const inferredCriteria = job?.criteria.length
    ? job.criteria.map((criterion) => ({
        name: criterion.name,
        weight: criterion.weight,
        description: criterion.description,
      }))
    : criteria;

  // Once the audit has run we lock the rubric controls (the choice is baked into the
  // created job) and hand off to the inline preparation panel.
  const prepared = audit !== null;
  const inferring = progress?.phase === "criteria" && !progress.done;
  const auditing = progress?.phase === "audit" && !progress.done;
  const preparing = (busy && !prepared) || inferring || auditing;
  const criteriaTotal = criteria.reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0);
  const criteriaValid =
    rubricMode !== "structured" ||
    (criteria.length > 0 && criteriaTotal === 100 && criteria.every((criterion) => criterion.name.trim() && criterion.weight > 0));
  const startCriteria =
    rubricMode === "structured"
      ? criteria.map((criterion) => ({
          name: criterion.name.trim(),
          weight: Number(criterion.weight) || 0,
          description: criterion.description?.trim() || null,
        }))
      : undefined;

  return (
    <div className="g-page">
      <GraderTopbar
        title="Preparar correção com IA"
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
                disabled={prepared || preparing}
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
              {item.latest_job_id ? (
                <div className="regrade-note">
                  <AppIcon name="refresh" />
                  Isto cria uma nova rodada; a anterior fica no histórico.
                </div>
              ) : null}
              {inferring ? (
                <CriteriaRunningPanel progress={progress} />
              ) : auditing ? (
                <AuditRunningPanel progress={progress} total={job?.total_submissions || item.submission_count} />
              ) : rubricMode === "infer" ? (
                <InferCriteriaPanel
                  criteria={inferredCriteria}
                  disabled={prepared || preparing}
                  onChange={setCriteria}
                  submissionCount={job?.total_submissions || item.submission_count}
                />
              ) : rubricMode === "structured" ? (
                <StructuredCriteriaEditor
                  criteria={criteria}
                  total={criteriaTotal}
                  disabled={prepared || preparing}
                  onChange={setCriteria}
                />
              ) : rubricMode === "saved" ? (
                <div className="saved-rubric-list">
                  {[
                    ["AP Bio · Relatório de laboratório (4 partes)", "12 vezes · última em 14 de maio", "4 critérios"],
                    ["Literatura · Redação (5 critérios)", "8 vezes", "4 critérios"],
                    ["Álgebra · Lista de problemas", "23 vezes", "4 critérios"],
                  ].map((row, index) => (
                    <button key={row[0]} className={`saved-rubric-row ${index === 0 ? "active" : ""}`} disabled={prepared || preparing}>
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
                  <span>Notas da rubrica</span>
                  <textarea
                    value={rubricText}
                    onChange={(event) => setRubricText(event.target.value)}
                    disabled={prepared || preparing}
                    placeholder="Tom, prioridades, evidências exigidas ou critérios que o rascunho deve respeitar."
                  />
                </label>
              )}
            </CardContent>
            {!prepared ? (
              <CardFooter className="setup-prepare-footer">
                <p className="prep-note">
                  <AppIcon name="info" /> A auditoria não chama a IA; ela prepara os arquivos e mostra bloqueios
                  antes dos rascunhos.
                </p>
                <div className="setup-footer-actions">
                  <button className="btn btn-ghost" onClick={onBack} disabled={preparing}>
                    Cancelar
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={() => onStart({ rubricMode, teacherLoop, rubricText, criteria: startCriteria })}
                    disabled={preparing || !criteriaValid}
                  >
                    <AppIcon name={preparing ? "loader" : "sparkle"} className={preparing ? "ico spin" : "ico"} />
                    {item.submission_count > 0
                      ? `Auditar e preparar ${item.submission_count}`
                      : "Auditar e preparar rascunhos"}
                  </button>
                </div>
              </CardFooter>
            ) : null}
          </Card>

          {prepared && audit ? (
            <PreparedPanel audit={audit} busy={busy} onContinue={onContinue} onRerun={onRerun} />
          ) : null}
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
                <AppIcon name="eyeOff" />
                <span>Nomes e e-mails dos alunos</span>
                <em>ocultados</em>
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
                    disabled={prepared || preparing}
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

function StructuredCriteriaEditor({
  criteria,
  total,
  disabled,
  onChange,
}: {
  criteria: GradingCriterionInput[];
  total: number;
  disabled: boolean;
  onChange: (criteria: GradingCriterionInput[]) => void;
}) {
  const update = (index: number, patch: Partial<GradingCriterionInput>) => {
    onChange(criteria.map((criterion, rowIndex) => (rowIndex === index ? { ...criterion, ...patch } : criterion)));
  };
  const remove = (index: number) => {
    onChange(criteria.filter((_, rowIndex) => rowIndex !== index));
  };
  const add = () => {
    onChange([...criteria, { name: "", weight: 0, description: "" }]);
  };

  return (
    <div className="criteria-editor">
      <div className="criteria-editor-head">
        <span>Critérios da rubrica</span>
        <strong className={total === 100 ? "ok" : "warn"}>{total}/100</strong>
      </div>
      <div className="criteria-editor-rows">
        {criteria.map((criterion, index) => (
          <div className="criteria-editor-row" key={index}>
            <input
              value={criterion.name}
              onChange={(event) => update(index, { name: event.target.value })}
              disabled={disabled}
              placeholder="Critério"
            />
            <input
              value={criterion.weight}
              onChange={(event) => update(index, { weight: Number(event.target.value) || 0 })}
              disabled={disabled}
              min={0}
              max={100}
              type="number"
              aria-label="Peso"
            />
            <input
              value={criterion.description ?? ""}
              onChange={(event) => update(index, { description: event.target.value })}
              disabled={disabled}
              placeholder="Descrição opcional"
            />
            <button className="icon-text-btn" onClick={() => remove(index)} disabled={disabled || criteria.length <= 1}>
              <AppIcon name="x" />
            </button>
          </div>
        ))}
      </div>
      <div className="criteria-editor-foot">
        <button className="btn btn-secondary" onClick={add} disabled={disabled}>
          <AppIcon name="plus" /> Adicionar critério
        </button>
        {total !== 100 ? <span>Os pesos precisam somar 100.</span> : null}
      </div>
    </div>
  );
}

function CriteriaRunningPanel({
  progress,
}: {
  progress: {
    processed: number;
    total: number;
    current: string;
  };
}) {
  return (
    <div className="criteria-running">
      <div className="audit-run-eyebrow">
        <AppIcon name="sparkle" /> Definindo critérios
      </div>
      <div className="audit-run-title">
        <AppIcon name="loader" className="ico spin" />
        <h2>Inferindo rubrica</h2>
      </div>
      <p className="audit-run-current">
        {progress.current || "Lendo a descrição da atividade e sinais estruturais."}
      </p>
      <div className="audit-run-meter-row">
        <strong>{progress.processed}/{Math.max(progress.total, 1)}</strong>
        <span>{Math.round((progress.processed / Math.max(progress.total, 1)) * 100)}%</span>
      </div>
      <div className="audit-run-meter">
        <span style={{ width: `${(progress.processed / Math.max(progress.total, 1)) * 100}%` }} />
      </div>
      <div className="audit-run-note">A professora verá e poderá editar os critérios antes da auditoria.</div>
    </div>
  );
}

function AuditRunningPanel({
  progress,
  total,
}: {
  progress: {
    processed: number;
    total: number;
    current: string;
  };
  total: number;
}) {
  const progressTotal = progress.total || total || 1;
  const pct = Math.round((progress.processed / progressTotal) * 100);
  return (
    <div className="audit-run">
      <div className="audit-run-eyebrow">
        <AppIcon name="shield" /> Preparando entregas · a IA ainda não viu nada
      </div>
      <div className="audit-run-title">
        <AppIcon name="loader" className="ico spin" />
        <h2>Auditoria de privacidade</h2>
      </div>
      <div className="audit-run-current">
        Verificando <strong>{progress.current || "entregas"}</strong> — mascarando nomes, e-mails e identificadores.
      </div>
      <div className="audit-run-meter-row">
        <strong>{progress.processed}/{progressTotal}</strong>
        <span>{pct}%</span>
      </div>
      <div className="audit-run-meter"><span style={{ width: `${pct}%` }} /></div>
      <div className="audit-run-note">
        Esta etapa é obrigatória. Nenhum dado vai para a IA antes da auditoria concluir.
      </div>
    </div>
  );
}

function InferCriteriaPanel({
  criteria,
  disabled,
  submissionCount,
  onChange,
}: {
  criteria: GradingCriterionInput[];
  disabled: boolean;
  submissionCount: number;
  onChange: (criteria: GradingCriterionInput[]) => void;
}) {
  const toggle = (index: number) => {
    if (disabled) return;
    const next = criteria.filter((_, rowIndex) => rowIndex !== index);
    onChange(next.length ? next : criteria);
  };
  const updateWeight = (index: number, weight: number) => {
    onChange(criteria.map((criterion, rowIndex) => (rowIndex === index ? { ...criterion, weight } : criterion)));
  };
  const activeTotal = criteria.reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0);
  return (
    <>
      <div className="panel-hint">
        A IA analisou a descrição da atividade e sinais seguros. Rubrica proposta para{" "}
        <strong>{submissionCount || "as"} entregas</strong> — edite ou remova o que quiser:
      </div>
      <div className="criteria-list">
        {criteria.map((criterion, index) => (
          <div className="criterion-row ai-proposed" key={`${criterion.name}-${index}`}>
            <div className="criterion-left">
              <button className="sk-cb on" onClick={() => toggle(index)} disabled={disabled} aria-label="Remover critério">
                <AppIcon name="check" />
              </button>
              <div>
                <div className="crit-name">{criterion.name}</div>
                <div className="crit-hint">{criterion.description ?? "Critério inferido pela IA."}</div>
              </div>
            </div>
            <div className="criterion-right">
              <input
                className="crit-weight"
                value={criterion.weight}
                disabled={disabled}
                type="number"
                min={1}
                max={100}
                onChange={(event) => updateWeight(index, Number(event.target.value) || 0)}
                aria-label={`Peso de ${criterion.name}`}
              />
              <button className="icon-btn" disabled={disabled} title="Editar">
                <AppIcon name="moreHorizontal" />
              </button>
            </div>
          </div>
        ))}
      </div>
      <div className="suggestion-strip">
        <span className={`qc-pill ${activeTotal === 100 ? "posted" : "reviewing"}`}>Pesos somam {activeTotal}%</span>
        <span className="qc-pill ai"><AppIcon name="sparkle" /> Rubrica inferida antes da auditoria</span>
      </div>
    </>
  );
}

function PreparedPanel({
  audit,
  busy,
  onContinue,
  onRerun,
}: {
  audit: PrivacyAudit;
  busy: boolean;
  onContinue: () => void;
  onRerun: () => void;
}) {
  const readyForDraft = audit.passed_files + audit.redacted_files;
  const blocked = audit.blocked_files;
  const highRisk = audit.high_risk_files > 0;

  return (
    <section className="prep-panel" aria-live="polite">
      <div className="prep-panel-head">
        <AppIcon name="checkCircle" className="ico" />
        <strong>Preparação concluída</strong>
      </div>

      <p className="prep-headline">
        <strong>{readyForDraft}</strong> {readyForDraft === 1 ? "entrega pronta" : "entregas prontas"} para rascunho
        {blocked > 0 ? (
          <> · <strong>{blocked}</strong> {blocked === 1 ? "bloqueada fica manual" : "bloqueadas ficam manuais"}</>
        ) : null}
        .
      </p>

      <div className="audit-summary">
        <AuditStat label="Aprovados" value={audit.passed_files} tone="ok" />
        <AuditStat label="Redigidos" value={audit.redacted_files} tone="warn" />
        <AuditStat label="Bloqueados" value={audit.blocked_files} tone="danger" />
        <AuditStat label="Alto risco" value={audit.high_risk_files} tone="danger" />
      </div>

      {highRisk ? (
        <div className="flag-note">
          A auditoria encontrou linhas de alto risco. O rascunho fica bloqueado até essas entregas serem tratadas.
        </div>
      ) : null}

      <details className="prep-details">
        <summary>Detalhes da auditoria</summary>
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
      </details>

      <div className="prep-actions">
        <button className="btn btn-secondary" onClick={onRerun} disabled={busy}>
          <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
          Reexecutar auditoria
        </button>
        <button className="btn btn-ai" onClick={onContinue} disabled={busy || highRisk}>
          <AppIcon name={busy ? "loader" : "sparkle"} className={busy ? "ico spin" : "ico"} />
          {readyForDraft > 0 ? `Gerar ${readyForDraft} rascunhos e revisar` : "Gerar rascunhos e revisar"}
        </button>
      </div>
    </section>
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
