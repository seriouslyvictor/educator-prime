import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import type {
  GradingJob,
  GradingQueueItem,
  GradingSubmission,
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
  { id: "infer", title: "Infer from work", copy: "Let the draft use the assignment and files.", icon: "sparkle" },
  { id: "brief", title: "Plain brief", copy: "Paste a short grading note for the draft.", icon: "fileText" },
  { id: "structured", title: "Structured rubric", copy: "Use weighted criteria before drafting.", icon: "settings" },
  { id: "saved", title: "Saved", copy: "Reuse a rubric shape from recent work.", icon: "archive" },
  { id: "calibrate", title: "Calibrate first", copy: "Seed the draft with examples to match your taste.", icon: "shield" },
];

const loopModes: Array<{
  id: TeacherLoopMode;
  title: string;
  copy: string;
}> = [
  { id: "auto", title: "Auto-grade", copy: "AI drafts all; you review only flagged rows" },
  { id: "approve", title: "Approve each", copy: "AI proposes a grade per student; you commit it" },
  { id: "cowrite", title: "Co-write", copy: "AI shows reasoning; you write the grade" },
  { id: "off", title: "AI off", copy: "You grade manually; AI just provides the table" },
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
  onRefresh: () => void;
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
        title="Grade with AI"
        subtitle="Draft-only grading beside the download workflow."
        action={
          <>
            <button className="btn btn-secondary" onClick={onDownloadInstead}>
              <AppIcon name="download" /> Download instead
            </button>
            <button className="btn btn-primary" onClick={onRefresh} disabled={loading}>
              <AppIcon name={loading ? "loader" : "refresh"} className={loading ? "ico spin" : "ico"} />
              Refresh
            </button>
          </>
        }
      />

      <div className="grader-search">
        <label className="search">
          <AppIcon name="search" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search classes or assignments"
          />
        </label>
      </div>

      <div className="grader-queue">
        <QueueSection
          title="Continue where you left off"
          empty="No grading drafts in progress."
          items={reviewing}
          onPick={(item) => item.latest_job_id && onOpenJob(item.latest_job_id)}
        />
        <QueueSection title="Ready for AI to draft" empty="No assignments ready." items={ready} onPick={onSetup} />
        <QueueSection
          title="Saved draft sets"
          empty="Completed draft sets will appear here."
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
                  {item.course_name} · {item.submission_count} submissions
                  {item.due_label ? ` · Due ${item.due_label}` : ""}
                </div>
              </div>
              <div className="grader-card-status">
                {item.latest_job_id ? `${item.reviewed_submissions}/${item.total_submissions} reviewed` : "Set up"}
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
        title="Setup rubric"
        subtitle={`${item.course_name} · ${item.activity_title}`}
        action={
          <button className="btn btn-secondary" onClick={onBack}>
            Back
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
                    ["AP Bio · Lab Report (4-part)", "12 times · last May 14", "4 criteria"],
                    ["World Lit · Essay (5-criterion)", "8 times", "4 criteria"],
                    ["Algebra · Problem Set", "23 times", "4 criteria"],
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
                  <span>{rubricMode === "infer" ? "Optional notes" : "Rubric notes"}</span>
                  <textarea
                    value={rubricText}
                    onChange={(event) => setRubricText(event.target.value)}
                    placeholder="Tone, priorities, required evidence, or criteria you want the draft to respect."
                  />
                </label>
              )}
            </CardContent>
            <CardFooter>
              <span>Selected: {rubricMode === "saved" ? "AP Bio · Lab Report (4-part)" : selectedRubric.title}</span>
              <div className="setup-footer-actions">
                <button className="btn btn-ghost" onClick={onBack}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => onStart({ rubricMode, teacherLoop, rubricText })}
                  disabled={busy}
                >
                  <AppIcon name={busy ? "loader" : "sparkle"} className={busy ? "ico spin" : "ico"} />
                  Draft grades for {item.submission_count}
                </button>
              </div>
            </CardFooter>
          </Card>
        </section>

        <aside className="setup-side setup-side-contract">
          <Card className="context-card">
            <CardHeader>
              <CardTitle>Context AI has</CardTitle>
            </CardHeader>
            <CardContent>
              {[
                ["Assignment title + description", ""],
                ["Student submissions", `${item.submission_count} files`],
                ["Attached materials", "2 PDFs"],
                ["Previous graded assignments", "4 examples"],
              ].map((row) => (
                <div className="context-row" key={row[0]}>
                  <AppIcon name="checkCircle" />
                  <span>{row[0]}</span>
                  <em>{row[1]}</em>
                </div>
              ))}
              <div className="context-row muted">
                <AppIcon name="x" />
                <span>Class roster (names hidden)</span>
                <em>privacy</em>
              </div>
            </CardContent>
          </Card>

          <Card className="tip-card">
            <CardContent>
              <div className="tip-title">
                <AppIcon name="sparkle" />
                Tip
              </div>
              <p>
                Try Infer for new assignment formats. The AI is good at spotting structure and proposing criteria that
                match.
              </p>
            </CardContent>
          </Card>

          <Card className="teacher-loop-card">
            <CardHeader>
              <CardTitle>Teacher-in-loop</CardTitle>
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
        subtitle={`${job.reviewed_submissions}/${job.total_submissions} reviewed · cache ${
          job.cache_expires_at ? "available" : "deleted"
        }`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Queue
            </button>
            <button className="btn btn-primary" onClick={onWrap}>
              Wrap drafts
            </button>
          </>
        }
      />
      <div className="review-grid">
        <aside className="student-list">
          <div className="student-list-head">Students</div>
          {job.submissions.map((submission) => (
            <button
              key={submission.id}
              className={`student-row ${submission.id === active?.id ? "active" : ""}`}
              onClick={() => onActiveSubmission(submission.id)}
            >
              <span>{submission.student_name ?? submission.student_email ?? "Unknown student"}</span>
              <small className={`student-state ${statusTone(submission)}`}>
                {submission.reviewed ? "Reviewed" : submission.error ? "Blocked" : submission.flag ? "Check" : "Draft"}
              </small>
            </button>
          ))}
        </aside>

        <section className="submission-preview">
          <div className="preview-paper">
            <div className="preview-file">
              <AppIcon name={active?.mime_type.includes("image") ? "eye" : "fileText"} />
              <div>
                <div>{active?.source_name ?? "No submission selected"}</div>
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
              Structured preview placeholder for V1. Privacy status:{" "}
              {privacyLabel(active?.privacy_status)}. Extraction: {extractionLabel(active?.extraction_status)}.
            </p>
          </div>
        </section>

        <aside className="suggestion-panel">
          <div className="suggestion-head">
            <span>AI draft</span>
            <strong>{active?.confidence ? `${Math.round(active.confidence * 100)}%` : "new"}</strong>
          </div>
          <div className="privacy-status-grid">
            <StatusPill label="Privacy" value={privacyLabel(active?.privacy_status)} tone={privacyTone(active)} />
            <StatusPill label="Input" value={extractionLabel(active?.extraction_status)} tone={extractionTone(active)} />
            <StatusPill label="Engine" value={attemptLabel(active?.ai_attempt_status)} tone={attemptTone(active)} />
          </div>
          {active?.flag ? <div className="flag-note">{active.flag.replace("_", " ")}</div> : null}
          <div className="criteria-list">
            {job.criteria.map((criterion) => (
              <div key={criterion.id} className="criterion-row">
                <span>{criterion.name}</span>
                <strong>{criterion.weight}%</strong>
              </div>
            ))}
          </div>
          <label className="score-input">
            <span>Final score</span>
            <input value={scoreText} onChange={(event) => setScoreText(event.target.value)} inputMode="decimal" />
          </label>
          <label className="feedback-input">
            <span>Feedback draft</span>
            <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
          </label>
          <div className="suggestion-actions">
            <button className="btn btn-secondary" onClick={() => active && onRetry(active)} disabled={!active || busy}>
              <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
              Re-grade
            </button>
            <button
              className="btn btn-primary"
              onClick={() => active && onAccept(active, Number.isFinite(score) ? score : 0, feedback)}
              disabled={!active || busy}
            >
              <AppIcon name="check" />
              Accept & next
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
  if (!status) return "Not checked";
  return status.replaceAll("_", " ");
}

function extractionLabel(status?: string | null) {
  if (!status) return "Pending";
  return status.replaceAll("_", " ");
}

function attemptLabel(status?: string | null) {
  if (!status) return "Pending";
  return status.replaceAll("_", " ");
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
        title="Draft wrap"
        subtitle={`${job.activity_title} · ${job.course_name}`}
        action={
          <>
            <button className="btn btn-secondary" onClick={onBack}>
              Review drafts
            </button>
            <button className="btn btn-primary" onClick={onQueue}>
              Save draft set
            </button>
          </>
        }
      />
      <div className="wrap-grid">
        <section className="wrap-main">
          <div className="wrap-stats">
            <div className="wrap-stat">
              <span>Reviewed</span>
              <strong>
                {job.reviewed_submissions}/{job.total_submissions}
              </strong>
            </div>
            <div className="wrap-stat">
              <span>Average</span>
              <strong>{average}</strong>
            </div>
            <div className="wrap-stat">
              <span>Needs check</span>
              <strong>{outliers.length}</strong>
            </div>
          </div>
          <div className="distribution">
            {job.submissions.map((submission) => (
              <div key={submission.id} className="dist-row">
                <span>{submission.student_name ?? "Unknown"}</span>
                <div>
                  <i style={{ width: `${Math.min(100, submission.final_score ?? 0)}%` }} />
                </div>
                <strong>{submission.final_score ?? "-"}</strong>
              </div>
            ))}
          </div>
          <section className="grader-section outliers">
            <div className="grader-section-head">
              <span>Outliers and flags</span>
              <span>{outliers.length}</span>
            </div>
            {outliers.length ? (
              outliers.map((submission) => (
                <div key={submission.id} className="outlier-row">
                  <span>{submission.student_name ?? submission.student_email ?? "Unknown student"}</span>
                  <small>{submission.flag ?? "Low score"}</small>
                </div>
              ))
            ) : (
              <div className="grader-empty">No flagged drafts in this set.</div>
            )}
          </section>
        </section>
        <aside className="wrap-side">
          <div className="mini-note">
            These are saved grading drafts only. Export CSV or keep reviewing; nothing is posted to Classroom in V1.
          </div>
          <a className="btn btn-primary export-link" href={api.gradingCsvUrl(job.id)}>
            <AppIcon name="fileDown" /> Export CSV
          </a>
          <button className="btn btn-secondary" onClick={onDeleteCache} disabled={busy || !job.cache_expires_at}>
            <AppIcon name={busy ? "loader" : "archive"} className={busy ? "ico spin" : "ico"} />
            Delete cached files now
          </button>
          <div className="cache-note">
            {job.cache_expires_at
              ? `Cached files expire ${new Date(job.cache_expires_at).toLocaleString()}`
              : "Cached files deleted; grade drafts remain saved."}
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
