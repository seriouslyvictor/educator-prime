/**
 * Low-level EventSource transport for grading progress streams.
 *
 * This module owns the EventSource lifecycle (construction, JSON parsing,
 * reconnect delays, close) and exposes a simple callback-based API. React
 * state management stays in the hook layer — this module has no React imports.
 *
 * The `EventSourceCtor` parameter exists solely for dependency injection in
 * tests; production callers omit it and get the browser's native EventSource.
 */

import type { GradingStreamPayload } from "../hooks/gradingProgress";

export interface GradingStreamCallbacks {
  /** Called for every valid, non-error payload received from the stream. */
  onPayload?: (payload: GradingStreamPayload) => void;
  /**
   * Called when the EventSource connection drops and a reconnect attempt is
   * about to start. `attempt` is 1-based (1 = first retry).
   */
  onReconnecting?: (attempt: number) => void;
  /**
   * Called when all reconnect attempts have been exhausted and the stream is
   * permanently closed. The `message` is the user-facing pt-BR resume prompt.
   */
  onExhausted?: (message: string) => void;
}

/** Reconnect delay ladder in milliseconds — matches the original hook. */
const RECONNECT_DELAYS = [2_000, 5_000, 10_000] as const;

export const RESUME_MESSAGE =
  "O processamento foi interrompido, mas pode continuar de onde parou. Use Retomar na fila.";

type EventSourceCtor = new (url: string) => EventSource;

/**
 * Open an EventSource at `url` and return a Promise that:
 * - resolves with the final payload when `payload.done` is true
 * - rejects with an Error when a JSON parse failure, server-sent error, or
 *   reconnect exhaustion occurs
 *
 * Connection errors trigger automatic reconnects via `RECONNECT_DELAYS`; when
 * the ladder is exhausted the promise rejects and `callbacks.onExhausted` is
 * called before the rejection.
 *
 * The `callbacks` parameter receives intermediate events so the caller can
 * update UI state without managing the underlying EventSource themselves.
 *
 * @param url          SSE endpoint URL.
 * @param fallbackError Human-readable error used when no server error message
 *                     is available (e.g. JSON parse failure).
 * @param callbacks    Optional lifecycle hooks — all are optional.
 * @param EventSourceCtor EventSource constructor; defaults to the global
 *                     `EventSource`. Pass a fake in tests.
 */
export function openGradingStream(
  url: string,
  fallbackError: string,
  callbacks: GradingStreamCallbacks = {},
  EventSourceCtor: EventSourceCtor = EventSource,
): Promise<GradingStreamPayload> {
  return new Promise((resolve, reject) => {
    let source: EventSource | null = null;
    let settled = false;
    let reconnectAttempt = 0;

    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      source?.close();
      callback();
    };

    const connect = () => {
      source?.close();
      source = new EventSourceCtor(url);

      source.onmessage = (event: MessageEvent) => {
        // Guard: in real browsers EventSource stops firing after close(), but a
        // stale reference or test fake may still deliver messages. Bail early.
        if (settled) return;

        let payload: GradingStreamPayload;
        try {
          payload = JSON.parse(event.data as string) as GradingStreamPayload;
        } catch {
          finish(() => reject(new Error(fallbackError)));
          return;
        }

        if (payload.error) {
          callbacks.onPayload?.(payload);
          finish(() => reject(new Error(payload.error)));
          return;
        }

        callbacks.onPayload?.(payload);

        if (payload.done) {
          finish(() => resolve(payload));
        }
      };

      source.onerror = () => {
        source?.close();
        const delay = RECONNECT_DELAYS[reconnectAttempt];
        if (delay !== undefined) {
          reconnectAttempt += 1;
          callbacks.onReconnecting?.(reconnectAttempt);
          window.setTimeout(() => {
            if (!settled) connect();
          }, delay);
          return;
        }
        callbacks.onExhausted?.(RESUME_MESSAGE);
        finish(() => reject(new Error(RESUME_MESSAGE)));
      };
    };

    connect();
  });
}
