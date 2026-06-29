"""Shared SSE worker runner for grading endpoints.

All three grading stream endpoints (privacy-audit, criteria, draft) share the
same Queue/Thread/event-stream mechanics.  This module factors that boilerplate
into a single helper so each endpoint only needs to supply its worker logic.

Public contract (event names, field names, ordering) lives in the endpoint
definitions in routers/grading.py — nothing here changes it.
"""

from collections.abc import Callable
from queue import Queue
from threading import Thread

from fastapi.responses import StreamingResponse

from ..api.common import _sse_event


def run_sse_worker(
    worker_fn: Callable[[Callable[[dict], None]], None],
    on_error: Callable[[], None],
    error_payload: dict,
) -> StreamingResponse:
    """Run worker_fn in a daemon thread and stream its published events as SSE.

    worker_fn(publish) is called once in a new daemon thread.  It calls
    publish(event_dict) to emit each SSE event and is responsible for emitting
    the terminal {done: True, ...} event when finished.

    If worker_fn raises an unhandled exception, on_error() is invoked and
    error_payload is published as the terminal event.

    The event stream closes after the first event that has done=True or a
    non-empty "error" field.
    """
    events: Queue[dict] = Queue()

    def _wrapped_worker() -> None:
        try:
            worker_fn(events.put)
        except Exception:
            on_error()
            events.put(error_payload)

    def event_stream():
        thread = Thread(target=_wrapped_worker, daemon=True)
        thread.start()
        while True:
            payload = events.get()
            yield _sse_event(payload)
            if payload.get("done") or payload.get("error"):
                break
        thread.join(timeout=1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
