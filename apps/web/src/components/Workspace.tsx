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
        <span>Classrooms · {courses.length}</span>
      </div>
      <div className="pane-search">
        <SearchBox value={query} onChange={onQuery} placeholder="Filter classes..." />
      </div>
      <div className="pane-body">
        {loading ? <SkeletonRows count={5} /> : null}
        {!loading && filtered.length === 0 ? (
          <EmptyState icon="search" title="No matches" copy="Try a different class filter." />
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
                  <span className="sub">{course.section ?? "No section"}</span>
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
  selectedIds,
  query,
  cursorIndex,
  keyboardActive,
  loading,
  onToggle,
  onToggleAll,
  onQuery,
}: {
  course: Course | undefined;
  activities: Activity[];
  selectedIds: string[];
  query: string;
  cursorIndex: number;
  keyboardActive: boolean;
  loading: boolean;
  onToggle: (activityId: string) => void;
  onToggleAll: (activities: Activity[], selected: boolean) => void;
  onQuery: (query: string) => void;
}) {
  const filtered = activities.filter((activity) =>
    `${activity.title} ${activity.work_type}`.toLowerCase().includes(query.toLowerCase()),
  );
  const allSelected =
    filtered.length > 0 && filtered.every((activity) => selectedIds.includes(activity.id));

  return (
    <section className="pane pane-right">
      <div className="assign-toolbar">
        <div className="toolbar-left">
          <div className="toolbar-title">{course?.name ?? "Select a classroom"}</div>
          <div className="toolbar-sub">
            {activities.length} activities · {selectedIds.length} selected
          </div>
        </div>
        <div className="head-tools">
          <SearchBox value={query} onChange={onQuery} placeholder="Filter activities..." />
          <button className="btn btn-secondary" onClick={() => onToggleAll(filtered, !allSelected)}>
            <AppIcon name="check" />
            {allSelected ? "Deselect" : "Select all"}
            <span className="kbd">Ctrl+A</span>
          </button>
        </div>
      </div>

      <div className="assign-list">
        {loading ? <SkeletonRows count={7} /> : null}
        {!loading && filtered.length === 0 ? (
          <EmptyState icon="file" title="No activities" copy="This class has no matching coursework." />
        ) : null}
        {!loading
          ? filtered.map((activity, index) => {
              const selected = selectedIds.includes(activity.id);
              const cursor = keyboardActive && index === cursorIndex;
              return (
                <div
                  key={activity.id}
                  className={`assign-row ${selected ? "selected" : ""} ${cursor ? "cursor" : ""}`}
                  onClick={() => onToggle(activity.id)}
                  role="checkbox"
                  aria-checked={selected}
                  tabIndex={0}
                >
                  <span className="checkbox">{selected ? <AppIcon name="check" /> : null}</span>
                  <div className="a-main">
                    <div className="ttl">{activity.title}</div>
                    <div className="meta-row">
                      <span className="work-pill">
                        <AppIcon name={workTypeIcon(activity.work_type)} />
                        {activity.work_type}
                      </span>
                      <span className="sep" />
                      <span>{activity.due_label ?? "No due date"}</span>
                    </div>
                  </div>
                  <div className="a-right">
                    <span className={`badge ${activity.state === "PUBLISHED" ? "badge-pub" : "badge-draft"}`}>
                      {activity.state === "PUBLISHED" ? "Live" : activity.state}
                    </span>
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
