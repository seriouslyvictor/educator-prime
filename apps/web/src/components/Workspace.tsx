import type { Activity, Course } from "../types";
import { AppIcon } from "./icons";

export function ClassroomList({
  courses,
  activeId,
  query,
  loading,
  onPick,
  onQuery,
}: {
  courses: Course[];
  activeId: string;
  query: string;
  loading: boolean;
  onPick: (courseId: string) => void;
  onQuery: (query: string) => void;
}) {
  const filtered = courses.filter((course) =>
    `${course.name} ${course.section ?? ""}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <section className="pane pane-left">
      <div className="pane-head">
        <span>Turmas · {courses.length}</span>
      </div>
      <div className="pane-search">
        <SearchBox value={query} onChange={onQuery} placeholder="Filtrar turmas..." />
      </div>
      <div className="pane-body">
        {loading ? <SkeletonRows count={5} /> : null}
        {!loading && filtered.length === 0 ? (
          <EmptyState icon="search" title="Nenhum resultado" copy="Tente outro filtro de turma." />
        ) : null}
        {!loading
          ? filtered.map((course, index) => (
              <button
                key={course.id}
                className={`class-row ${course.id === activeId ? "active" : ""}`}
                onClick={() => onPick(course.id)}
              >
                <span className="class-dot" style={{ color: palette[index % palette.length] }} />
                <span className="class-main">
                  <span className="ttl">{course.name}</span>
                  <span className="sub">{course.section ?? "Sem seção"}</span>
                </span>
                <span className="meta">{course.course_state}</span>
              </button>
            ))
          : null}
      </div>
    </section>
  );
}

export function ActivityList({
  course,
  activities,
  query,
  loading,
  onQuery,
  onGrade,
  onPreview,
  onDownload,
  busy,
  deliveryMode,
}: {
  course: Course | undefined;
  activities: Activity[];
  query: string;
  loading: boolean;
  onQuery: (query: string) => void;
  onGrade: (activity: Activity) => void;
  onPreview: (activity: Activity) => void;
  onDownload: (activity: Activity) => void;
  busy: boolean;
  deliveryMode: "folder" | "zip";
}) {
  const filtered = activities.filter((activity) =>
    `${activity.title} ${activity.work_type}`.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <section className="pane pane-right">
      <div className="assign-toolbar">
        <div className="toolbar-left">
          <div className="toolbar-title">{course?.name ?? "Selecione uma turma"}</div>
          <div className="toolbar-sub">{activities.length} atividades</div>
        </div>
        <div className="head-tools">
          <SearchBox value={query} onChange={onQuery} placeholder="Filtrar atividades..." />
        </div>
      </div>

      <div className="assign-list">
        {loading ? <SkeletonRows count={7} /> : null}
        {!loading && filtered.length === 0 ? (
          <EmptyState icon="file" title="Nenhuma atividade" copy="Esta turma não tem atividades correspondentes." />
        ) : null}
        {!loading
          ? filtered.map((activity) => {
              const disabled = busy || !course;
              return (
                <div key={activity.id} className="assign-row">
                  <div className="a-main">
                    <div className="ttl">{activity.title}</div>
                    <div className="meta-row">
                      <span className="work-pill">
                        <AppIcon name={workTypeIcon(activity.work_type)} />
                        {activity.work_type}
                      </span>
                      <span className="sep" />
                      <span>{activity.due_label ?? "Sem prazo"}</span>
                    </div>
                  </div>
                  <div className="a-right">
                    <span className={`badge ${activity.state === "PUBLISHED" ? "badge-pub" : "badge-draft"}`}>
                      {activity.state === "PUBLISHED" ? "Publicado" : activity.state}
                    </span>
                    <div className="assign-actions">
                      <button className="btn btn-primary" onClick={() => onGrade(activity)} disabled={disabled}>
                        <AppIcon name="sparkle" />
                        Corrigir com IA
                      </button>
                      <button className="icon-text-btn" onClick={() => onPreview(activity)} disabled={disabled}>
                        <AppIcon name="eye" />
                        Prévia
                      </button>
                      <button
                        className="icon-text-btn"
                        onClick={() => onDownload(activity)}
                        disabled={disabled || deliveryMode === "zip"}
                      >
                        <AppIcon name={deliveryMode === "zip" ? "archive" : "folderOpen"} />
                        Baixar
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          : null}
      </div>
    </section>
  );
}

export function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div className="search">
      <AppIcon name="search" />
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  copy,
}: {
  icon: "search" | "file" | "folderOpen" | "history";
  title: string;
  copy: string;
}) {
  return (
    <div className="empty-state">
      <AppIcon name={icon} />
      <h3>{title}</h3>
      <p>{copy}</p>
    </div>
  );
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div className="skeleton-row" key={index} />
      ))}
    </>
  );
}

function workTypeIcon(type: string): "sparkle" | "info" | "fileText" | "file" {
  if (type.toLowerCase().includes("quiz")) return "sparkle";
  if (type.toLowerCase().includes("question")) return "info";
  if (type.toLowerCase().includes("material")) return "fileText";
  return "file";
}

const palette = ["#059669", "#10b981", "#047857", "#34d399", "#1f8a5b", "#0f766e"];
