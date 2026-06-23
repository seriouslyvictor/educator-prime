import { useCallback, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { GradingJob, GradingSubmission } from "../../../types";
import { AppIcon } from "../../icons";
import { scoreColor, scoreOf, studentLabel } from "../domain";
import styles from "./PostingPiP.module.css";

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

// Grid shows up to this many students at once; the rest stay reachable by scroll.
const GRID_LIMIT = 18;

// ── card ──────────────────────────────────────────────────────────────────────

function PostingPiPCard({
  job,
  queue,
  pipWindow,
  onMarkPosted,
  onClose,
}: PostingPiPProps) {
  const [copied, setCopied] = useState<Record<string, boolean>>({});
  const [clipError, setClipError] = useState<string | null>(null);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const copyFeedback = useCallback(
    async (submission: GradingSubmission) => {
      setClipError(null);
      // Copy feedback text only (PiP window clipboard first, opener as fallback).
      try {
        if (pipWindow.navigator?.clipboard) {
          await pipWindow.navigator.clipboard.writeText(postingFeedbackText(submission));
        } else {
          await navigator.clipboard.writeText(postingFeedbackText(submission));
        }
      } catch {
        try {
          await navigator.clipboard.writeText(postingFeedbackText(submission));
        } catch {
          setClipError("Não foi possível copiar para a área de transferência.");
          return;
        }
      }

      // Mark posted so the main panel tracks progress; the grid snapshot stays put.
      onMarkPosted(submission);

      setCopied((prev) => ({ ...prev, [submission.id]: true }));
      clearTimeout(timers.current[submission.id]);
      timers.current[submission.id] = setTimeout(() => {
        setCopied((prev) => {
          const next = { ...prev };
          delete next[submission.id];
          return next;
        });
      }, 1350);
    },
    [pipWindow, onMarkPosted],
  );

  return (
    <div className={styles["card"]}>
      <div className={styles["grid-header"]}>
        <div className={styles["grid-title-block"]}>
          <div className={styles["grid-label"]}>Postar no Classroom</div>
          <h2 className={styles["grid-title"]}>{job.activity_title}</h2>
        </div>
        <span className={styles["grid-counter"]}>{queue.length} alunos</span>
      </div>

      {clipError && (
        <div className={styles["error-chip"]}>
          <AppIcon name="triangleAlert" className={styles["error-icon"]} />
          {clipError}
        </div>
      )}

      <div className={styles["grid"]}>
        {queue.slice(0, GRID_LIMIT).map((submission) => {
          const grade = scoreOf(submission);
          const isCopied = !!copied[submission.id];
          return (
            <div
              key={submission.id}
              className={`${styles["grid-cell"]} ${isCopied ? styles["grid-cell-copied"] : ""}`}
            >
              <div className={styles["cell-main"]}>
                <span className={styles["cell-name"]}>{studentLabel(submission)}</span>
                <span className={styles["cell-feedback"]}>
                  {submission.feedback || "Sem feedback registrado."}
                </span>
              </div>
              <div className={styles["cell-side"]}>
                <span
                  className={styles["cell-grade"]}
                  style={{ color: scoreColor(grade) }}
                >
                  {grade ?? "—"}
                </span>
                <button
                  className={styles["copy-btn"]}
                  onClick={() => void copyFeedback(submission)}
                  title="Copiar feedback"
                  aria-label={`Copiar feedback de ${studentLabel(submission)}`}
                >
                  <AppIcon
                    name={isCopied ? "check" : "clipboard"}
                    className={styles["copy-icon"]}
                  />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className={styles["grid-footer"]}>
        <span className={styles["hint"]}>Copie o feedback e cole no Classroom.</span>
        <button className={styles["close-btn"]} onClick={onClose}>
          Fechar
        </button>
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
