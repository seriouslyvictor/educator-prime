import {
  BookOpenCheck,
  CheckCircle2,
  Download,
  FileDown,
  FolderOpen,
  GraduationCap,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "./lib/api";
import { exportJobToFolder, isFolderExportSupported } from "./lib/folder-export";
import type { Activity, AuthState, Course, ExportJob } from "./types";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Empty,
  Progress,
  Skeleton,
} from "./components/ui";

const classroomScopes = [
  "classroom.courses.readonly",
  "classroom.coursework.students.readonly",
  "classroom.student-submissions.students.readonly",
  "classroom.profile.emails",
  "drive.readonly",
];

export function App() {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [selectedActivityIds, setSelectedActivityIds] = useState<string[]>([]);
  const [job, setJob] = useState<ExportJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportProgress, setExportProgress] = useState({
    completed: 0,
    total: 0,
    currentPath: "",
  });

  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId),
    [courses, selectedCourseId],
  );

  const folderSupported = isFolderExportSupported();

  useEffect(() => {
    void bootstrap();
  }, []);

  async function bootstrap() {
    setLoading(true);
    setError(null);
    try {
      const [authState, courseList] = await Promise.all([api.authMe(), api.courses()]);
      setAuth(authState);
      setCourses(courseList);
      if (courseList[0]) {
        setSelectedCourseId(courseList[0].id);
        await loadActivities(courseList[0].id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load app state.");
    } finally {
      setLoading(false);
    }
  }

  async function loadActivities(courseId: string) {
    setError(null);
    setActivities([]);
    setSelectedActivityIds([]);
    setJob(null);
    try {
      const activityList = await api.activities(courseId);
      setActivities(activityList);
      setSelectedActivityIds(activityList.map((activity) => activity.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load activities.");
    }
  }

  async function connectClassroom() {
    setBusy(true);
    setError(null);
    try {
      await api.connectGoogle(classroomScopes);
      setAuth(await api.authMe());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to connect Google.");
    } finally {
      setBusy(false);
    }
  }

  async function createAndDownloadExport() {
    if (!selectedCourse || selectedActivityIds.length === 0) return;

    setBusy(true);
    setError(null);
    setExportProgress({ completed: 0, total: 0, currentPath: "" });
    try {
      const exportJob = await api.createExport(selectedCourse.id, selectedActivityIds);
      setJob(exportJob);
      await exportJobToFolder(exportJob, (completed, total, currentPath) => {
        setExportProgress({ completed, total, currentPath });
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  function toggleActivity(activityId: string) {
    setSelectedActivityIds((current) =>
      current.includes(activityId)
        ? current.filter((id) => id !== activityId)
        : [...current, activityId],
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CD</div>
          <div>
            <strong>Classroom Downloader</strong>
            <span>Exports & manifests</span>
          </div>
        </div>
        <nav>
          <a className="active">
            <BookOpenCheck />
            Classrooms
          </a>
          <a>
            <FileDown />
            Export Jobs
          </a>
          <a>
            <ShieldCheck />
            Permissions
          </a>
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <p className="eyebrow">MVP workspace</p>
            <h1>Classroom exports</h1>
          </div>
          <div className="topbar-actions">
            <Badge variant={folderSupported ? "success" : "warning"}>
              {folderSupported ? "Folder export ready" : "Chrome/Edge required"}
            </Badge>
            <Button variant="outline" onClick={() => void bootstrap()} disabled={loading || busy}>
              <RefreshCw data-icon="inline-start" />
              Refresh
            </Button>
          </div>
        </header>

        <section className="content-grid">
          <Card className="hero-card">
            <CardHeader>
              <CardTitle>Download student submissions into regular folders</CardTitle>
              <CardDescription>
                Choose a course, select activities, pick a destination folder, and the browser
                writes the class/activity/student file tree locally.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="hero-actions">
                <Button onClick={connectClassroom} disabled={busy}>
                  {busy ? <Loader2 className="spin" data-icon="inline-start" /> : <ShieldCheck data-icon="inline-start" />}
                  Connect Classroom & Drive
                </Button>
                <Button
                  variant="outline"
                  onClick={createAndDownloadExport}
                  disabled={
                    busy ||
                    !folderSupported ||
                    !selectedCourse ||
                    selectedActivityIds.length === 0
                  }
                >
                  <FolderOpen data-icon="inline-start" />
                  Pick folder & export
                </Button>
              </div>
              {error ? (
                <div className="alert">
                  <TriangleAlert />
                  <span>{error}</span>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Google connection</CardTitle>
              <CardDescription>Progressive OAuth status for this user.</CardDescription>
            </CardHeader>
            <CardContent>
              {auth ? (
                <div className="status-list">
                  <StatusRow label="Signed in" ok={auth.signed_in} />
                  <StatusRow label="Classroom scopes" ok={auth.classroom_scopes} />
                  <StatusRow label="Drive readonly scope" ok={auth.drive_scopes} />
                  <p className="muted">{auth.email ?? "OAuth credentials not configured yet"}</p>
                </div>
              ) : (
                <Skeleton className="status-skeleton" />
              )}
            </CardContent>
          </Card>
        </section>

        <section className="content-grid columns">
          <Card>
            <CardHeader>
              <CardTitle>Active classrooms</CardTitle>
              <CardDescription>Archived courses are excluded by the API.</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="table-skeleton" />
              ) : courses.length === 0 ? (
                <Empty
                  icon={<GraduationCap />}
                  title="No active courses"
                  description="Connect Classroom to list non-archived classes."
                />
              ) : (
                <div className="table-list">
                  {courses.map((course) => (
                    <button
                      className={course.id === selectedCourseId ? "row selected" : "row"}
                      key={course.id}
                      onClick={() => {
                        setSelectedCourseId(course.id);
                        void loadActivities(course.id);
                      }}
                    >
                      <span>
                        <strong>{course.name}</strong>
                        <small>{course.section ?? "No section"}</small>
                      </span>
                      <Badge>{course.course_state}</Badge>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Activities</CardTitle>
              <CardDescription>Select the work to include in the export.</CardDescription>
            </CardHeader>
            <CardContent>
              {activities.length === 0 ? (
                <Empty
                  icon={<Download />}
                  title="No activities loaded"
                  description="Select a classroom to fetch coursework."
                />
              ) : (
                <div className="table-list">
                  {activities.map((activity) => (
                    <label className="row checkbox-row" key={activity.id}>
                      <input
                        type="checkbox"
                        checked={selectedActivityIds.includes(activity.id)}
                        onChange={() => toggleActivity(activity.id)}
                      />
                      <span>
                        <strong>{activity.title}</strong>
                        <small>{activity.due_label ?? activity.work_type}</small>
                      </span>
                      <Badge>{activity.state}</Badge>
                    </label>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="content-grid">
          <Card>
            <CardHeader>
              <CardTitle>Export progress</CardTitle>
              <CardDescription>
                Files are streamed from FastAPI and written by the browser into your selected folder.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Progress
                value={
                  exportProgress.total
                    ? (exportProgress.completed / exportProgress.total) * 100
                    : 0
                }
              />
              <div className="progress-copy">
                <strong>
                  {exportProgress.completed}/{exportProgress.total || job?.total_files || 0} files
                </strong>
                <span>{exportProgress.currentPath || "No export running."}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Manifest preview</CardTitle>
              <CardDescription>Email-first filenames generated by the backend.</CardDescription>
            </CardHeader>
            <CardContent>
              {!job ? (
                <Empty
                  icon={<FileDown />}
                  title="No manifest yet"
                  description="Run an export to preview the generated file paths."
                />
              ) : (
                <div className="manifest">
                  {job.files.map((file) => (
                    <div className="manifest-row" key={file.id}>
                      <CheckCircle2 />
                      <span>{file.output_path}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  );
}

function StatusRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <Badge variant={ok ? "success" : "warning"}>{ok ? "Ready" : "Needed"}</Badge>
    </div>
  );
}
