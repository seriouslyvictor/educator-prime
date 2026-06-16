import { useEffect, useState } from "react";
import type { GradingCriterionInput, GradingJob, GradingQueueItem, PrivacyAudit, RubricMode, TeacherLoopMode } from "../../types";
import { AppIcon } from "../icons";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, RadioGroup, RadioItem, Tabs, TabsList, TabsTrigger } from "../ui";
import { GraderTopbar } from "./GraderTopbar";
import { StructuredCriteriaEditor } from "./setup/StructuredCriteriaEditor";
import { CriteriaRunningPanel, AuditRunningPanel, InferIntroPanel, PreparedPanel } from "./setup/PreparePanels";
import graderStyles from "./Grader.module.css";
void graderStyles;

const rubricModes: Array<{
  id: RubricMode;
  title: string;
  copy: string;
  icon: "sparkle" | "fileText" | "settings" | "archive" | "shield";
  comingSoon?: boolean;
}> = [
  { id: "infer", title: "Inferir pelo trabalho", copy: "Deixe o rascunho usar a atividade e os arquivos.", icon: "sparkle" },
  { id: "brief", title: "Orientação simples", copy: "Cole uma nota curta de correção para o rascunho.", icon: "fileText" },
  { id: "structured", title: "Rubrica estruturada", copy: "Use critérios com pesos antes do rascunho.", icon: "settings" },
  { id: "saved", title: "Salva", copy: "Reutilize uma rubrica de trabalhos recentes.", icon: "archive", comingSoon: true },
  { id: "calibrate", title: "Calibrar primeiro", copy: "Use exemplos para ajustar o rascunho ao seu estilo.", icon: "shield", comingSoon: true },
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
  onInferCriteria,
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
  onInferCriteria: (payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
    includeVisualSubmissions: boolean;
  }) => void;
  onStart: (payload: {
    rubricMode: RubricMode;
    teacherLoop: TeacherLoopMode;
    rubricText: string;
    includeVisualSubmissions: boolean;
    criteria?: GradingCriterionInput[];
  }) => void;
  onContinue: () => void;
  onRerun: () => void;
}) {
  const [rubricMode, setRubricMode] = useState<RubricMode>("infer");
  const [teacherLoop, setTeacherLoop] = useState<TeacherLoopMode>("approve");
  const [rubricText, setRubricText] = useState("");
  const [includeVisualSubmissions, setIncludeVisualSubmissions] = useState(false);
  const [criteria, setCriteria] = useState<GradingCriterionInput[]>([
    { name: "Funcionalidade", weight: 60, description: "Resolve o que foi pedido." },
    { name: "Clareza", weight: 40, description: "Organização, leitura e justificativa." },
  ]);
  const selectedRubric = rubricModes.find((mode) => mode.id === rubricMode) ?? rubricModes[0];
  // Infer mode runs in two steps: first produce the rubric, then let the teacher
  // edit it. Inference has happened once the job carries non-placeholder criteria.
  const criteriaInferred = rubricMode === "infer" && !!job && job.criteria.length > 0 && !hasDefaultCriteria(job);
  const jobCriteriaSignature = job?.criteria.map((c) => `${c.name}:${c.weight}`).join("|") ?? "";

  useEffect(() => {
    setIncludeVisualSubmissions(job?.include_visual_submissions ?? false);
  }, [job?.id, job?.include_visual_submissions]);

  // Load the inferred rubric into the editable state so the teacher edits the real
  // criteria (not a throwaway copy). Edits don't change the signature, so they survive.
  useEffect(() => {
    if (rubricMode === "infer" && job && job.criteria.length > 0 && !hasDefaultCriteria(job)) {
      setCriteria(
        job.criteria.map((criterion) => ({
          name: criterion.name,
          weight: criterion.weight,
          description: criterion.description,
        })),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rubricMode, jobCriteriaSignature]);

  // Once the audit has run we lock the rubric controls (the choice is baked into the
  // created job) and hand off to the inline preparation panel.
  const prepared = audit !== null;
  const inferring = progress?.phase === "criteria" && !progress.done;
  const auditing = progress?.phase === "audit" && !progress.done;
  const preparing = (busy && !prepared) || inferring || auditing;
  const criteriaTotal = criteria.reduce((sum, criterion) => sum + (Number(criterion.weight) || 0), 0);
  // The weighted editor is shown for structured mode and for infer once the rubric
  // has been inferred; both must sum to 100 with named, positive-weight rows.
  const needsCriteriaEditor = rubricMode === "structured" || (rubricMode === "infer" && criteriaInferred);
  const criteriaValid =
    !needsCriteriaEditor ||
    (criteria.length > 0 && criteriaTotal === 100 && criteria.every((criterion) => criterion.name.trim() && criterion.weight > 0));
  const startCriteria = needsCriteriaEditor
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
                disabled={prepared || preparing || mode.comingSoon}
                title={mode.comingSoon ? "Em breve" : mode.copy}
                onClick={() => {
                  if (mode.comingSoon) return;
                  setRubricMode(mode.id);
                }}
              >
                <AppIcon name={mode.icon} />
                <span>{mode.title}</span>
                {mode.comingSoon ? <span className="tab-soon">em breve</span> : null}
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
                criteriaInferred ? (
                  <>
                    <div className="panel-hint">
                      A IA propôs esta rubrica a partir da atividade e de sinais seguros. Edite os critérios,
                      ajuste os pesos ou remova o que quiser antes de auditar.
                    </div>
                    <StructuredCriteriaEditor
                      criteria={criteria}
                      total={criteriaTotal}
                      disabled={prepared || preparing}
                      onChange={setCriteria}
                    />
                  </>
                ) : (
                  <InferIntroPanel submissionCount={job?.total_submissions || item.submission_count} />
                )
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
                <label className="visual-consent">
                  <input
                    type="checkbox"
                    checked={includeVisualSubmissions}
                    disabled={preparing || !!job}
                    onChange={(event) => setIncludeVisualSubmissions(event.target.checked)}
                  />
                  <span>
                    <strong>Incluir envios visuais (fotos e capturas de tela)</strong>
                    <small>
                      Pixels nao podem ser pre-anonimizados; a imagem sera enviada uma vez ao provedor de IA
                      para transcricao, e a transcricao sera anonimizada antes da correcao.
                    </small>
                  </span>
                </label>
                <div className="setup-footer-actions">
                  <button className="btn btn-ghost" onClick={onBack} disabled={preparing}>
                    Cancelar
                  </button>
                  {rubricMode === "infer" && !criteriaInferred ? (
                    <button
                      className="btn btn-primary"
                      onClick={() => onInferCriteria({ rubricMode, teacherLoop, rubricText, includeVisualSubmissions })}
                      disabled={preparing}
                    >
                      <AppIcon name={preparing ? "loader" : "sparkle"} className={preparing ? "ico spin" : "ico"} />
                      Inferir critérios
                    </button>
                  ) : (
                    <button
                      className="btn btn-primary"
                      onClick={() => onStart({ rubricMode, teacherLoop, rubricText, includeVisualSubmissions, criteria: startCriteria })}
                      disabled={preparing || !criteriaValid}
                    >
                      <AppIcon name={preparing ? "loader" : "sparkle"} className={preparing ? "ico spin" : "ico"} />
                      {item.submission_count > 0
                        ? `Auditar e preparar ${item.submission_count}`
                        : "Auditar e preparar rascunhos"}
                    </button>
                  )}
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
                <span>Nomes completos, CPF, contatos e redes sociais</span>
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

function hasDefaultCriteria(job: GradingJob): boolean {
  const names = job.criteria.map((criterion) => criterion.name).join("|");
  const weights = job.criteria.map((criterion) => criterion.weight).join("|");
  return names === "Understanding|Evidence|Reasoning|Clarity" && weights === "30|25|30|15";
}
