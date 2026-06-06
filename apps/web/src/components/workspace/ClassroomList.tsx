import type { Course } from "../../types";
import { EmptyState, SearchBox, SkeletonRows } from "../ui";
import workspaceStyles from "./Workspace.module.css";
void workspaceStyles;

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
    <section className={`${workspaceStyles.pane} pane-left`}>
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


const palette = ["#2A2FE0", "#1F8A5B", "#B8740B", "#6b3fe0", "#c7421e", "#0e7490"];
