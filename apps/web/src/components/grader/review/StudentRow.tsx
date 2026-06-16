import { AppIcon } from "../../icons";
import { studentLabel } from "../domain";
import { initials, isBlocked, isVisualSubmission } from "./reviewHelpers";
import type { GradingSubmission } from "../../../types";

export function StudentRow({
  submission,
  active,
  drafting,
  queued,
  onPick,
}: {
  submission: GradingSubmission;
  active: boolean;
  drafting: boolean;
  queued: boolean;
  onPick: () => void;
}) {
  const blocked = isBlocked(submission);
  const meta = submission.reviewed
    ? { icon: "checkCircle" as const, tone: "ok", label: "revisado" }
    : blocked
      ? { icon: "triangleAlert" as const, tone: "danger", label: "bloqueado" }
      : submission.flag
        ? { icon: "triangleAlert" as const, tone: "warn", label: "verificar" }
        : { icon: "sparkle" as const, tone: "ai", label: "rascunho da IA" };

  return (
    <button className={`student-row ${active ? "active" : ""} ${drafting ? "drafting" : ""}`} onClick={onPick}>
      <div className="student-avatar small">{initials(submission.student_name, "AL")}</div>
      <div className="student-row-copy">
        <div className="student-name">{studentLabel(submission)}</div>
        <div className={`student-meta ${drafting ? "ai" : queued ? "muted" : meta.tone}`}>
          {drafting ? (
            <span className="dot-spin" />
          ) : queued ? (
            <span className="dot-queued" />
          ) : (
            <AppIcon name={meta.icon} />
          )}
          {drafting ? "gerando rascunho..." : queued ? "na fila" : meta.label}
          {isVisualSubmission(submission) ? <span className="visual-dot">visual</span> : null}
        </div>
      </div>
      <div className="student-score">
        {drafting || queued ? (
          <span className="skeleton score-skeleton" />
        ) : submission.final_score != null ? (
          <span className="final">{submission.final_score}</span>
        ) : submission.ai_score != null ? (
          <span className="ai-suggest">✦ {submission.ai_score}</span>
        ) : (
          <span className="none">—</span>
        )}
      </div>
    </button>
  );
}
