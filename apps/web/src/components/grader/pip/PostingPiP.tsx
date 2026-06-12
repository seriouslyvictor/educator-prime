import { useCallback, useState } from "react";
import { createPortal } from "react-dom";

import type { GradingJob, GradingSubmission } from "../../../types";
import { AppIcon } from "../../icons";
import { Button } from "../../ui/button";
import styles from "./PostingPiP.module.css";

// ── helpers (mirrors GraderWrap helpers — duplicated to avoid circular deps) ──

function scoreOf(submission: GradingSubmission): number | null {
  return submission.final_score ?? submission.ai_score ?? null;
}

function studentLabel(submission: GradingSubmission): string {
  return submission.student_name ?? submission.student_email ?? "Aluno desconhecido";
}

function scoreColor(g: number | null): string {
  if (g == null) return "var(--muted-2)";
  return g >= 85 ? "var(--ink)" : g >= 65 ? "var(--warning)" : "var(--danger)";
}

function postingFeedbackText(submission: GradingSubmission): string {
  return submission.feedback ?? "";
}

// ── component props ───────────────────────────────────────────────────────────

export interface PostingPiPProps {
  job: GradingJob;
  queue: GradingSubmission[];
  pipWindow: Window;
  onMarkPosted(submission: GradingSubmission): void;
  onClose(): void;
}

// ── DoneScreen ────────────────────────────────────────────────────────────────

function DoneScreen({
  count,
  job,
  onClose,
}: {
  count: number;
  job: GradingJob;
  onClose(): void;
}) {
  return (
    <div className={styles["done"]}>
      <div className={styles["done-circle"]}>
        <AppIcon name="checkCircle" className={styles["done-icon"]} />
      </div>
      <div className={styles["done-title"]}>Tudo postado!</div>
      <div className={styles["done-sub"]}>
        {count} aluno{count !== 1 ? "s" : ""} · {job.course_name}
        <br />
        {job.activity_title}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onClose}
        className={styles["done-btn"]}
      >
        Fechar
      </Button>
    </div>
  );
}

// ── card ──────────────────────────────────────────────────────────────────────

const PREVIEW = 96;

type Phase = "idle" | "copied" | "done";

function PostingPiPCard({
  job,
  queue,
  pipWindow,
  onMarkPosted,
  onClose,
}: PostingPiPProps) {
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [expanded, setExpanded] = useState(false);
  const [clipError, setClipError] = useState<string | null>(null);

  const cur = queue[Math.min(idx, queue.length - 1)];
  const grade = scoreOf(cur);
  const isNoLink = !cur.alternate_link;
  const feedText = cur.feedback ?? "";
  const feedShort =
    feedText.length > PREVIEW ? feedText.slice(0, PREVIEW) + "…" : feedText;

  const advance = useCallback(() => {
    setPhase("idle");
    setExpanded(false);
    setClipError(null);
    if (idx + 1 < queue.length) {
      setIdx((i) => i + 1);
    } else {
      setPhase("done");
    }
  }, [idx, queue.length]);

  const goBack = () => {
    setPhase("idle");
    setExpanded(false);
    setClipError(null);
    setIdx((i) => i - 1);
  };

  const handleCTA = async () => {
    setClipError(null);
    // 1. Copy feedback text to clipboard (PiP window first, opener fallback)
    try {
      if (pipWindow.navigator?.clipboard) {
        await pipWindow.navigator.clipboard.writeText(postingFeedbackText(cur));
      } else {
        await navigator.clipboard.writeText(postingFeedbackText(cur));
      }
    } catch {
      try {
        await navigator.clipboard.writeText(postingFeedbackText(cur));
      } catch {
        setClipError("Não foi possível copiar para a área de transferência.");
        return; // do NOT advance on clipboard failure
      }
    }

    // 2. Navigate Classroom tab (named tab reuse) when link exists
    if (cur.alternate_link) {
      pipWindow.open(cur.alternate_link, "classroom-posting");
    }

    // 3. Mark posted (fire-and-forget; errors surface via onMarkPosted callback)
    onMarkPosted(cur);

    // 4. Show "Copiado ✓" state, advance after 1350ms
    setPhase("copied");
    setTimeout(advance, 1350);
  };

  if (phase === "done") {
    return (
      <div className={styles["card"]}>
        <DoneScreen count={queue.length} job={job} onClose={onClose} />
      </div>
    );
  }

  return (
    <div className={styles["card"]}>
      {/* Progress header */}
      <div className={styles["progress-header"]}>
        <button
          className={styles["back-arrow"]}
          onClick={goBack}
          disabled={idx === 0}
          title="Aluno anterior"
          style={{ color: idx === 0 ? "var(--border)" : "var(--muted)" }}
        >
          <AppIcon name="arrowLeft" className={styles["back-icon"]} />
        </button>
        <div className={styles["progress-track"]}>
          <div
            className={styles["progress-fill"]}
            style={{ width: `${(idx / queue.length) * 100}%` }}
          />
        </div>
        <span className={styles["progress-counter"]}>
          {idx} de {queue.length}
        </span>
      </div>

      {/* Student name — NUCLEAR */}
      <div className={styles["student-section"]}>
        <div className={styles["student-label"]}>Aluno atual</div>
        <div className={styles["student-row"]}>
          <h2 className={styles["student-name"]}>{studentLabel(cur)}</h2>
          <div className={styles["grade-block"]}>
            <div
              className={styles["grade-value"]}
              style={{ color: scoreColor(grade) }}
            >
              {grade ?? "—"}
            </div>
            <div className={styles["grade-denom"]}>/100</div>
          </div>
        </div>
      </div>

      {/* Feedback preview */}
      <div className={styles["feedback-section"]}>
        <div className={styles["feedback-box"]}>
          {expanded ? feedText : feedShort}
          {feedText.length > PREVIEW && (
            <button
              className={styles["expand-btn"]}
              onClick={() => setExpanded((e) => !e)}
            >
              {expanded ? " ↑ menos" : " ↓ mais"}
            </button>
          )}
        </div>

        {/* No-link warning chip */}
        {isNoLink && (
          <div className={styles["nolink-chip"]}>
            <AppIcon name="triangleAlert" className={styles["nolink-icon"]} />
            Link direto ausente — abra o Classroom manualmente
          </div>
        )}

        {/* Clipboard failure error chip */}
        {clipError && (
          <div className={styles["error-chip"]}>
            <AppIcon name="triangleAlert" className={styles["error-icon"]} />
            {clipError}
          </div>
        )}
      </div>

      {/* CTA */}
      <div className={styles["cta-section"]}>
        <button
          className={styles["cta-btn"]}
          onClick={() => void handleCTA()}
          disabled={phase === "copied"}
          style={{
            background:
              phase === "copied" ? "var(--success)" : "var(--ai)",
          }}
        >
          {phase === "copied" ? (
            <>
              <AppIcon name="check" className={styles["cta-icon"]} />
              Copiado ✓
            </>
          ) : isNoLink ? (
            <>
              <AppIcon name="paperclip" className={styles["cta-icon"]} />
              Copiar feedback
            </>
          ) : (
            <>
              <AppIcon name="paperclip" className={styles["cta-icon"]} />
              Copiar e avançar →
            </>
          )}
        </button>

        {phase !== "copied" && (
          <div className={styles["secondary-row"]}>
            <button
              className={styles["secondary-btn"]}
              onClick={goBack}
              disabled={idx === 0}
              style={{
                color: idx === 0 ? "transparent" : "var(--muted)",
                cursor: idx === 0 ? "default" : "pointer",
              }}
            >
              ← Anterior
            </button>
            <button
              className={styles["secondary-btn"]}
              onClick={advance}
              style={{ color: "var(--muted)" }}
            >
              {isNoLink ? "Avançar sem copiar →" : "Pular →"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── portal wrapper ────────────────────────────────────────────────────────────

export function PostingPiP(props: PostingPiPProps) {
  return createPortal(
    <PostingPiPCard {...props} />,
    props.pipWindow.document.body,
  );
}
