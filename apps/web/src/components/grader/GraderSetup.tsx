import { useState } from "react";
import type { GradingQueueItem, RubricMode, TeacherLoopMode } from "../../types";
import { AppIcon } from "../icons";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, RadioGroup, RadioItem, Tabs, TabsList, TabsTrigger } from "../ui";
import { GraderTopbar } from "./GraderTopbar";
import graderStyles from "./Grader.module.css";

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
    <div className={graderStyles["grader-page"]}>
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

