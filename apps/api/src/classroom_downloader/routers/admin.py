"""Read-only admin observability API."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from ..api.deps import require_admin
from ..database import get_session
from ..models import AppEvent, GradingAiAttempt, GradingAiAttemptPayload
from ..observability import purge_expired_observability_rows
from ..schemas import (
    AdminStats,
    AiAttemptAdminRead,
    AiAttemptPayloadRead,
    AppEventRead,
)

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@router.get("/events", response_model=list[AppEventRead])
def list_events(
    level: str | None = None,
    event_prefix: str | None = None,
    user_email: str | None = None,
    q: str | None = None,
    before: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[AppEvent]:
    purge_expired_observability_rows(db)
    statement = select(AppEvent)
    if level:
        statement = statement.where(AppEvent.level == level.upper())
    if event_prefix:
        statement = statement.where(col(AppEvent.event).startswith(event_prefix))
    if user_email:
        statement = statement.where(AppEvent.user_email == user_email)
    if q:
        statement = statement.where(col(AppEvent.fields_json).contains(q))
    if before:
        statement = statement.where(AppEvent.created_at < before)
    statement = statement.order_by(AppEvent.created_at.desc()).limit(limit)
    return list(db.exec(statement).all())


@router.get("/llm/attempts", response_model=list[AiAttemptAdminRead])
def list_llm_attempts(
    job_id: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    retryable: bool | None = None,
    model: str | None = None,
    before: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[AiAttemptAdminRead]:
    statement = select(GradingAiAttempt)
    if job_id:
        statement = statement.where(GradingAiAttempt.job_id == job_id)
    if status:
        statement = statement.where(GradingAiAttempt.status == status)
    if stage:
        statement = statement.where(GradingAiAttempt.stage == stage)
    if retryable is not None:
        statement = statement.where(GradingAiAttempt.retryable == retryable)
    if model:
        statement = statement.where(GradingAiAttempt.model == model)
    if before:
        statement = statement.where(GradingAiAttempt.created_at < before)
    statement = statement.order_by(GradingAiAttempt.created_at.desc()).limit(limit)
    attempts = db.exec(statement).all()
    payload_ids = {
        row.attempt_id
        for row in db.exec(
            select(GradingAiAttemptPayload).where(
                col(GradingAiAttemptPayload.attempt_id).in_(
                    [attempt.id for attempt in attempts]
                )
            )
        ).all()
    } if attempts else set()
    return [
        AiAttemptAdminRead(
            **attempt.model_dump(),
            has_payload=attempt.id in payload_ids,
        )
        for attempt in attempts
    ]


@router.get("/llm/attempts/{attempt_id}/payload", response_model=AiAttemptPayloadRead)
def get_llm_attempt_payload(
    attempt_id: str,
    db: Session = Depends(get_session),
) -> AiAttemptPayloadRead:
    payload = db.get(GradingAiAttemptPayload, attempt_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Payload not found.")
    return AiAttemptPayloadRead(
        attempt_id=payload.attempt_id,
        prompt_text=payload.prompt_text,
        response_text=payload.response_text,
    )


@router.get("/stats", response_model=AdminStats)
def get_admin_stats(db: Session = Depends(get_session)) -> AdminStats:
    now = datetime.now(UTC)
    event_cutoff = now - timedelta(hours=24)
    attempt_cutoff = now - timedelta(days=7)
    events = db.exec(select(AppEvent).where(AppEvent.created_at >= event_cutoff)).all()
    attempts = db.exec(
        select(GradingAiAttempt).where(GradingAiAttempt.created_at >= attempt_cutoff)
    ).all()
    counts: dict[str, int] = {}
    for event in events:
        counts[event.level] = counts.get(event.level, 0) + 1
    return AdminStats(
        events_24h_by_level=counts,
        attempts_7d=len(attempts),
        failures_7d=sum(1 for attempt in attempts if attempt.status == "failed"),
        cost_cents_7d=round(
            sum(attempt.cost_cents or 0 for attempt in attempts),
            4,
        ),
    )
