import { useMemo, useState } from "react";
import type { Activity, Course, GradingQueueItem } from "../../types";
import { referenceQueueStatus } from "../grader/GraderQueue";
import { AppIcon } from "../icons";
import { EmptyState, SearchBox, SkeletonRows } from "../ui";
import turmasStyles from "./Turmas.module.css";

const palette = ["#2A2FE0", "#1F8A5B", "#B8740B", "#6b3fe0", "#c7421e", "#0e7490"];

type ActivityGroup = "todo" | "review" | "done";

type GroupConfig = {
  id: ActivityGroup;
  title: string;
  icon: "listChecks" | "sparkle" | "checkCircle";
};

const groups: GroupConfig[] = [
  { id: "todo", title: "A corrigir", icon: "listChecks" },
  { id: "review", title: "Em revisão", icon: "sparkle" },
  { id: "done", title: "Concluídas", icon: "checkCircle" },
];

export function TurmasView({
  courses,
  activeCourseId,
  activities,
  classQuery,
  activityQuery,
  loadingCourses,
  loadingActivities,
  busy,
  deliveryMode,
  gradingByActivity,
  onPickCourse,
  onClassQuery,
  onActivityQuery,
  onGrade,
  onRegrade,
  onPreview,
  onDownload,
  onSendToQueue,
}: {
  courses: Course[];
  activeCourseId: string;
  activities: Activity[];
  classQuery: string;
  activityQuery: string;
  loadingCourses: boolean;
  loadingActivities: boolean;
  busy: boolean;
  deliveryMode: "folder" | "zip";
  gradingByActivity: Map<string, GradingQueueItem>;
  onPickCourse: (courseId: string) => void;
  onClassQuery: (query: string) => void;
  onActivityQuery: (query: string) => void;
  onGrade: (activity: Activity) => void;
  onRegrade: (activity: Activity) => void;
  onPreview: (activity: Activity) => void;
  onDownload: (activity: Activity) => void;
  onSendToQueue: (activities: Activity[]) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const activeCourse = courses.find((course) => course.id === activeCourseId);
  const filteredCourses = courses.filter((course) =>
    `${course.name} ${course.section ?? ""}`.toLowerCase().includes(classQuery.toLowerCase()),
  );
  const filteredActivities = activities.filter((activity) =>
    `${activity.title} ${activity.work_type}`.toLowerCase().includes(activityQuery.toLowerCase()),
  );

  const grouped = useMemo(() => {
    const rows: Record<ActivityGroup, Activity[]> = { todo: [], review: [], done: [] };
    for (const activity of filteredActivities) {
      rows[groupFor(activity, gradingByActivity.get(activity.id))].push(activity);
    }
    return rows;
  }, [filteredActivities, gradingByActivity]);

  const toggleSelected = (activityId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(activityId)) next.delete(activityId);
      else next.add(activityId);
      return next;
    });
  };
  const disabled = busy || !activeCourse;

  return (
    <div className={turmasStyles["turmas-screen"]}>
      <aside className="turmas-side">
        <div className="turmas-side-head">Turmas</div>
        <SearchBox value={classQuery} onChange={onClassQuery} placeholder="Filtrar turmas..." />
        <div className="turmas-class-list">
          {loadingCourses ? <SkeletonRows count={5} /> : null}
          {!loadingCourses && filteredCourses.length === 0 ? (
            <EmptyState icon="search" title="Nenhuma turma" copy="Tente outro filtro." />
          ) : null}
          {!loadingCourses
            ? filteredCourses.map((course, index) => (
                <button
                  key={course.id}
                  className={`turmas-class ${course.id === activeCourseId ? "active" : ""}`}
                  onClick={() => onPickCourse(course.id)}
                >
                  <span className="turmas-dot" style={{ background: palette[index % palette.length] }} />
                  <span>
                    <strong>{course.name}</strong>
                    <small>{course.section ?? "Sem seção"}</small>
                  </span>
                  <em>{course.course_state}</em>
                </button>
              ))
            : null}
        </div>
      </aside>

      <section className="turmas-main">
        <header className="turmas-head">
          <div>
            <h1>{activeCourse?.name ?? "Selecione uma turma"}</h1>
            <p>
              {activeCourse?.name ?? "Turma"} · {activities.length} atividades · selecione para enviar à fila
            </p>
          </div>
          <SearchBox value={activityQuery} onChange={onActivityQuery} placeholder="Filtrar atividades..." />
        </header>

        <div className="turmas-body">
          {selected.size > 0 ? (
            <div className="turmas-bulk">
              <span>
                <b>{selected.size}</b> selecionada{selected.size === 1 ? "" : "s"}
              </span>
              <button onClick={() => setSelected(new Set())}>Limpar</button>
              <button
                className="turmas-bulk-send"
                onClick={() => {
                  const chosen = activities.filter((activity) => selected.has(activity.id));
                  onSendToQueue(chosen);
                  setSelected(new Set());
                }}
              >
                <AppIcon name="send" />
                Enviar {selected.size} para a fila
              </button>
            </div>
          ) : null}

          {loadingActivities ? <SkeletonRows count={7} /> : null}
          {!loadingActivities && filteredActivities.length === 0 ? (
            <EmptyState
              icon="file"
              title="Nenhuma atividade"
              copy={
                activityQuery
                  ? "Nenhuma atividade corresponde à busca."
                  : "Esta turma ainda não tem atividades - isso não é um erro."
              }
            />
          ) : null}

          {!loadingActivities
            ? groups.map((group) => (
                <section className={`turmas-group ${group.id}`} key={group.id}>
                  <div className="turmas-group-head">
                    <span className="turmas-group-ic">
                      <AppIcon name={group.icon} />
                    </span>
                    <h2>{group.title}</h2>
                    <span>{grouped[group.id].length}</span>
                  </div>
                  {grouped[group.id].length > 0 ? (
                    <div className={`turmas-card ${selected.size ? "has-selection" : ""}`}>
                      {grouped[group.id].map((activity) => {
                        const grading = gradingByActivity.get(activity.id);
                        const status = grading ? referenceQueueStatus(grading) : null;
                        const action = actionFor(grading);
                        const isSelected = selected.has(activity.id);
                        return (
                          <div className={`turmas-row ${isSelected ? "selected" : ""}`} key={activity.id}>
                            <button
                              className={`turmas-cb ${isSelected ? "on" : ""}`}
                              onClick={() => toggleSelected(activity.id)}
                              aria-label={`Selecionar ${activity.title}`}
                            >
                              <AppIcon name="check" />
                            </button>
                            <div className="turmas-row-main">
                              <strong>{activity.title}</strong>
                              <small>
                                {activity.work_type} · {activity.due_label ?? "Sem prazo"} ·{" "}
                                {activity.state === "PUBLISHED" ? "Publicado" : activity.state}
                              </small>
                            </div>
                            <div className="turmas-row-status">
                              {status ? (
                                <span className={`turmas-status ${status.cls}`}>
                                  <AppIcon name={status.icon} />
                                  {status.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="turmas-actions">
                              <button
                                className={`turmas-primary ${action.ai ? "ai" : ""}`}
                                disabled={disabled}
                                onClick={() => onGrade(activity)}
                              >
                                {action.ai ? <AppIcon name="sparkle" /> : <AppIcon name={action.icon} />}
                                {action.label}
                              </button>
                              <div className="turmas-menu-wrap">
                                <button
                                  className="turmas-icon-btn"
                                  onClick={() => setOpenMenu(openMenu === activity.id ? null : activity.id)}
                                  aria-label="Mais ações"
                                >
                                  <AppIcon name="moreHorizontal" />
                                </button>
                                {openMenu === activity.id ? (
                                  <div className="turmas-menu">
                                    <button onClick={() => { setOpenMenu(null); onPreview(activity); }}>
                                      <AppIcon name="eye" /> Prévia
                                    </button>
                                    <button
                                      disabled={disabled || deliveryMode === "zip"}
                                      onClick={() => { setOpenMenu(null); onDownload(activity); }}
                                    >
                                      <AppIcon name={deliveryMode === "zip" ? "archive" : "folderOpen"} /> Baixar entregas
                                    </button>
                                    <button disabled={disabled} onClick={() => { setOpenMenu(null); onRegrade(activity); }}>
                                      <AppIcon name="refresh" /> Reclassificar
                                    </button>
                                    <button disabled>
                                      <AppIcon name="arrowRight" /> Abrir no Classroom
                                    </button>
                                  </div>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </section>
              ))
            : null}
        </div>
      </section>
    </div>
  );
}

function groupFor(_activity: Activity, grading: GradingQueueItem | undefined): ActivityGroup {
  if (!grading || grading.status === "ready") return "todo";
  if (grading.status === "completed") return "done";
  return "review";
}

function actionFor(grading: GradingQueueItem | undefined): {
  label: string;
  icon: "eye" | "checkCircle";
  ai: boolean;
} {
  if (!grading?.latest_job_id) return { label: "Corrigir com IA", icon: "eye", ai: true };
  if (grading.status === "completed") {
    return { label: "Ver notas", icon: "checkCircle", ai: false };
  }
  if (grading.status === "reviewing") return { label: "Revisar", icon: "eye", ai: false };
  return { label: "Retomar", icon: "eye", ai: false };
}
