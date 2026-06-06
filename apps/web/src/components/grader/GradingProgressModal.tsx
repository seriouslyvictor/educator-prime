import { AppIcon } from "../icons";
import graderStyles from "./Grader.module.css";

export type GradingProgressPhase = "audit" | "criteria" | "draft";

export type GradingProgressState = {
  phase: GradingProgressPhase;
  processed: number;
  total: number;
  current: string;
  done: boolean;
  error: string | null;
};

const phaseCopy: Record<GradingProgressPhase, { title: string; eyebrow: string }> = {
  audit: {
    title: "Auditoria de privacidade",
    eyebrow: "Preparando entregas",
  },
  criteria: {
    title: "Definindo critérios",
    eyebrow: "Lendo a descrição e as entregas",
  },
  draft: {
    title: "Avaliação da IA",
    eyebrow: "Gerando rascunhos",
  },
};

export function GradingProgressModal({
  state,
  onClose,
}: {
  state: GradingProgressState;
  onClose: () => void;
}) {
  const copy = phaseCopy[state.phase];
  const total = Math.max(0, state.total);
  const processed = total > 0 ? Math.min(state.processed, total) : Math.max(0, state.processed);
  const percent = total > 0 ? Math.round((processed / total) * 100) : 0;
  const terminal = state.done || Boolean(state.error);

  return (
    <div className={graderStyles["grading-progress-modal"]} role="dialog" aria-modal="true" aria-live="polite">
      <section className={graderStyles["grading-progress-dialog"]}>
        <div className={graderStyles["grading-progress-head"]}>
          <span>{copy.eyebrow}</span>
          {terminal ? (
            <button className="btn btn-secondary" onClick={onClose}>
              Fechar
            </button>
          ) : null}
        </div>

        <div className={graderStyles["grading-progress-title"]}>
          <AppIcon name={state.error ? "triangleAlert" : state.done ? "checkCircle" : "loader"} className={state.error || state.done ? "ico" : "ico spin"} />
          <h2>{state.error ? "Processo interrompido" : state.done ? "Processo concluído" : copy.title}</h2>
        </div>

        <p className={graderStyles["grading-progress-current"]}>
          {state.error ?? state.current ?? "Iniciando..."}
        </p>

        <div className={graderStyles["grading-progress-meter-row"]}>
          <strong>
            {total > 0 ? `${processed}/${total}` : processed > 0 ? `${processed}` : "0"}
          </strong>
          <span>{total > 0 ? `${percent}%` : "calculando total"}</span>
        </div>

        <div className={graderStyles["grading-progress-meter"]} aria-hidden="true">
          <span style={{ width: `${percent}%` }} />
        </div>

        <p className={graderStyles["grading-progress-note"]}>
          Esta janela fica aberta enquanto a rodada está em execução.
        </p>
      </section>
    </div>
  );
}
