import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RESUME_MESSAGE, openGradingStream } from "./gradingEventSource";
import type { GradingStreamCallbacks } from "./gradingEventSource";

// ---------------------------------------------------------------------------
// Fake EventSource
// ---------------------------------------------------------------------------

/**
 * Minimal EventSource fake that lets tests drive messages and errors
 * synchronously without a real server or browser.
 */
class FakeEventSource {
  readonly url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  private _closed = false;

  static instances: FakeEventSource[] = [];

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  /** Simulate the server emitting a text message. */
  emit(data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent;
    this.onmessage?.(event);
  }

  /** Simulate a malformed (non-JSON) message. */
  emitRaw(raw: string) {
    const event = { data: raw } as MessageEvent;
    this.onmessage?.(event);
  }

  /** Simulate a connection drop / error event. */
  triggerError() {
    this.onerror?.();
  }

  close() {
    this._closed = true;
  }

  get closed() {
    return this._closed;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function latestSource(): FakeEventSource {
  const src = FakeEventSource.instances.at(-1);
  if (!src) throw new Error("No FakeEventSource was created");
  return src;
}

// ---------------------------------------------------------------------------
// Test setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  FakeEventSource.instances = [];
  // Make setTimeout resolve immediately so reconnect tests don't stall.
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("openGradingStream", () => {
  it("resolves with the final payload when done:true is received", async () => {
    const promise = openGradingStream(
      "/stream",
      "fallback error",
      {},
      FakeEventSource as unknown as typeof EventSource,
    );

    latestSource().emit({ processed: 5, total: 5, done: true, job: { id: "job-1" } });

    const result = await promise;
    expect(result).toMatchObject({ done: true, job: { id: "job-1" } });
  });

  it("calls onPayload for each valid message", async () => {
    const received: unknown[] = [];
    const callbacks: GradingStreamCallbacks = {
      onPayload: (p) => received.push(p),
    };

    const promise = openGradingStream(
      "/stream",
      "fallback",
      callbacks,
      FakeEventSource as unknown as typeof EventSource,
    );

    const src = latestSource();
    src.emit({ processed: 1, total: 5 });
    src.emit({ processed: 2, total: 5 });
    src.emit({ processed: 5, total: 5, done: true });

    await promise;
    expect(received).toHaveLength(3);
    expect(received[0]).toMatchObject({ processed: 1 });
    expect(received[1]).toMatchObject({ processed: 2 });
    expect(received[2]).toMatchObject({ done: true });
  });

  it("rejects with fallback error on malformed JSON", async () => {
    const promise = openGradingStream(
      "/stream",
      "parse failed",
      {},
      FakeEventSource as unknown as typeof EventSource,
    );

    latestSource().emitRaw("not-valid-json{{{");

    await expect(promise).rejects.toThrow("parse failed");
  });

  it("rejects with the server error message when payload.error is set", async () => {
    const callbacks: GradingStreamCallbacks = {
      onPayload: vi.fn(),
    };

    const promise = openGradingStream(
      "/stream",
      "fallback",
      callbacks,
      FakeEventSource as unknown as typeof EventSource,
    );

    latestSource().emit({ error: "Erro do servidor" });

    await expect(promise).rejects.toThrow("Erro do servidor");
    // onPayload is still called so the hook can update progress with the error
    expect(callbacks.onPayload).toHaveBeenCalledWith(
      expect.objectContaining({ error: "Erro do servidor" }),
    );
  });

  it("calls close on the EventSource after resolution", async () => {
    const promise = openGradingStream(
      "/stream",
      "fallback",
      {},
      FakeEventSource as unknown as typeof EventSource,
    );

    const src = latestSource();
    src.emit({ done: true });

    await promise;
    expect(src.closed).toBe(true);
  });

  it("calls close on the EventSource after rejection", async () => {
    const promise = openGradingStream(
      "/stream",
      "fallback error",
      {},
      FakeEventSource as unknown as typeof EventSource,
    );

    const src = latestSource();
    src.emitRaw("bad json");

    await expect(promise).rejects.toThrow();
    expect(src.closed).toBe(true);
  });

  it("reconnects up to 3 times before exhausting", async () => {
    const onReconnecting = vi.fn();
    const onExhausted = vi.fn();

    const promise = openGradingStream(
      "/stream",
      "fallback",
      { onReconnecting, onExhausted },
      FakeEventSource as unknown as typeof EventSource,
    );

    // Trigger all 3 reconnect attempts
    for (let i = 0; i < 3; i++) {
      latestSource().triggerError();
      // Advance past the reconnect delay so the next connect() fires
      await vi.runAllTimersAsync();
    }

    // Fourth error — no more delays, promise should reject
    latestSource().triggerError();

    await expect(promise).rejects.toThrow(RESUME_MESSAGE);

    expect(onReconnecting).toHaveBeenCalledTimes(3);
    expect(onReconnecting).toHaveBeenNthCalledWith(1, 1);
    expect(onReconnecting).toHaveBeenNthCalledWith(2, 2);
    expect(onReconnecting).toHaveBeenNthCalledWith(3, 3);

    expect(onExhausted).toHaveBeenCalledOnce();
    expect(onExhausted).toHaveBeenCalledWith(RESUME_MESSAGE);
  });

  it("creates a new EventSource on each reconnect attempt", async () => {
    const promise = openGradingStream(
      "/stream",
      "fallback",
      {},
      FakeEventSource as unknown as typeof EventSource,
    );

    // First error -> reconnect
    latestSource().triggerError();
    await vi.runAllTimersAsync();

    // Resolve on the second connection
    latestSource().emit({ done: true });

    await promise;
    // One original + one reconnect
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("ignores further messages after the stream has settled", async () => {
    const onPayload = vi.fn();

    const promise = openGradingStream(
      "/stream",
      "fallback",
      { onPayload },
      FakeEventSource as unknown as typeof EventSource,
    );

    const src = latestSource();
    // First message settles the stream
    src.emit({ done: true });
    await promise;

    // Late message should be ignored (settled flag prevents re-entry)
    src.emit({ processed: 999 });
    expect(onPayload).toHaveBeenCalledTimes(1); // only the done message
  });
});
