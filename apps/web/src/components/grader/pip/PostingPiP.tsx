import { useCallback, useEffect, useRef, useState } from "react";
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

function classroomActivityUrl(job: GradingJob): string {
  return `https://classroom.google.com/c/${job.course_id}/a/${job.activity_id}/details`;
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
    <div className={styles["pip-done"]}>
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
  // Classroom full-reloads on every external navigation (it's only SPA-fast
  // internally), so we navigate the named tab ONCE to land in the activity and
  // let the teacher use Classroom's own student switcher from there.
  const [hasNavigated, setHasNavigated] = useState(false);

  const cur = queue[Math.min(idx, queue.length - 1)];
  const nextUp = queue.slice(idx + 1, idx + 4);
  const grade = scoreOf(cur);
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

    // 2. First click only: open the named Classroom tab (deep link when
    //    available, activity page otherwise). Subsequent clicks never navigate.
    if (!hasNavigated) {
      pipWindow.open(cur.alternate_link ?? classroomActivityUrl(job), "classroom-posting");
      setHasNavigated(true);
    }

    // 3. Mark posted (fire-and-forget; errors surface via onMarkPosted callback)
    onMarkPosted(cur);

    // 4. Show "Copiado ✓" state, advance after 1350ms
    setPhase("copied");
    setTimeout(advance, 1350);
  };

  // Keyboard shortcuts — listen on the PiP document so they only fire while
  // the PiP window is focused (Space in the Classroom tab keeps typing spaces).
  // preventDefault on keydown also stops a focused button's native Space
  // activation, so actions never double-fire.
  const keyActions = useRef({ handleCTA, advance, goBack, onClose, phase, idx });
  keyActions.current = { handleCTA, advance, goBack, onClose, phase, idx };

  useEffect(() => {
    const doc = pipWindow.document;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return;
      const a = keyActions.current;
      if (event.code === "Space") {
        event.preventDefault();
        if (a.phase === "done") a.onClose();
        else if (a.phase === "idle") void a.handleCTA();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        if (a.phase === "idle") a.advance();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        if (a.phase === "idle" && a.idx > 0) a.goBack();
      }
    };
    doc.addEventListener("keydown", onKeyDown);
    return () => doc.removeEventListener("keydown", onKeyDown);
  }, [pipWindow]);

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
      <div className={styles["pip-student-section"]}>
        <div className={styles["pip-student-label"]}>Aluno atual</div>
        <div className={styles["pip-student-row"]}>
          <h2 className={styles["pip-student-name"]}>{studentLabel(cur)}</h2>
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
              Pular →
            </button>
          </div>
        )}

        {idx === 0 && (
          <div className={styles["hint"]}>
            <kbd className={styles["hint-kbd"]}>espaço</kbd> copia e avança ·
            no Classroom, ordene a lista por nome para seguir a fila
          </div>
        )}
      </div>

      {/* Queue — "A seguir" (ported from PiPC) */}
      {nextUp.length > 0 && (
        <div>
          <div className={styles["queue-head"]}>A seguir</div>
          {nextUp.map((s, i) => {
            const g = scoreOf(s);
            return (
              <div
                key={s.id}
                className={styles["queue-row"]}
                style={{ opacity: Math.max(0.22, 1 - i * 0.28) }}
              >
                <span className={styles["queue-num"]}>{idx + i + 2}</span>
                <span className={styles["queue-name"]}>{studentLabel(s)}</span>
                <span
                  className={styles["queue-grade"]}
                  style={{ color: scoreColor(g) }}
                >
                  {g ?? "—"}
                </span>
              </div>
            );
          })}
        </div>
      )}
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
