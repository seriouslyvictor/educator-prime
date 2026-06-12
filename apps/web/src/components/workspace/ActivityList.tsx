import type { Activity, Course, GradingQueueItem } from "../../types";
import { referenceQueueStatus } from "../grader/GraderQueue";
import { AppIcon } from "../icons";
import { EmptyState, SearchBox, SkeletonRows } from "../ui";
import workspaceStyles from "./Workspace.module.css";
void workspaceStyles;

export function ActivityList({
  course,
  activities,
  query,
  loading,
  onQuery,
  onGrade,
  onRegrade,
  onPreview,
  onDownload,
  busy,
  deliveryMode,
  gradingByActivity,
}: {
  course: Course | undefined;
  activities: Activity[];
  query: string;
  loading: boolean;
  onQuery: (query: string) => void;
  onGrade: (activity: Activity) => void;
  onRegrade: (activity: Activity) => void;
  onPreview: (activity: Activity) => void;
  onDownload: (activity: Activity) => void;
  busy: boolean;
  deliveryMode: "folder" | "zip";
  gradingByActivity: Map<string, GradingQueueItem>;
}) {
  const filtered = activities.filter((activity) =>
    `${activity.title} ${activity.work_type}`.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <section className={`${workspaceStyles.pane} pane-right`}>
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
          <EmptyState icon="file" title="Nenhuma atividade" copy="Nenhuma entrega ainda - isso não é um erro." />
        ) : null}
        {!loading
          ? filtered.map((activity) => {
              const disabled = busy || !course;
              const grading = gradingByActivity.get(activity.id);
              const gradingStatus = grading ? referenceQueueStatus(grading) : null;
              const primaryLabel = grading?.status === "completed"
                ? "Abrir revisão"
                : grading?.latest_job_id
                  ? "Retomar"
                  : "Corrigir com IA";
              const primaryIcon = grading?.status === "completed"
                ? "checkCircle"
                : grading?.latest_job_id
                  ? "eye"
                  : "sparkle";
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
                    {gradingStatus ? (
                      <span className={`grading-chip ${gradingStatus.cls}`}>
                        <AppIcon name={gradingStatus.icon} />
                        {gradingStatus.label}
                      </span>
                    ) : null}
                    <div className="assign-actions">
                      <button className="btn btn-primary" onClick={() => onGrade(activity)} disabled={disabled}>
                        <AppIcon name={primaryIcon} />
                        {primaryLabel}
                      </button>
                      {grading?.status === "completed" || grading?.status === "reviewing" ? (
                        <button className="icon-text-btn" onClick={() => onRegrade(activity)} disabled={disabled}>
                          <AppIcon name="refresh" />
                          Reclassificar
                        </button>
                      ) : null}
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


function workTypeIcon(type: string): "sparkle" | "info" | "fileText" | "file" {
  if (type.toLowerCase().includes("quiz")) return "sparkle";
  if (type.toLowerCase().includes("question")) return "info";
  if (type.toLowerCase().includes("material")) return "fileText";
  return "file";
}
