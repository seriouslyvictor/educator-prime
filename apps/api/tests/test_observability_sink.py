import json
import logging
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from classroom_downloader.database import engine, init_db
from classroom_downloader.models import AppEvent
from classroom_downloader.observability import (
    DbEventHandler,
    _format_event,
    current_request_id,
    current_user_email,
    log_event,
    log_warning,
    purge_expired_observability_rows,
)
from classroom_downloader.settings import get_settings


def _clear_events() -> None:
    init_db()
    with Session(engine) as session:
        for row in session.exec(select(AppEvent)).all():
            session.delete(row)
        session.commit()


def _events() -> list[AppEvent]:
    with Session(engine) as session:
        return list(session.exec(select(AppEvent)).all())


def test_warning_log_persists_redacted_event() -> None:
    _clear_events()
    request_token = current_request_id.set("req-123")
    user_token = current_user_email.set("teacher@example.edu")
    try:
        log_warning(
            logging.getLogger("test.observability.sink.warning"),
            "grading.warning",
            email="student@example.edu",
            kept="ok",
        )
    finally:
        current_user_email.reset(user_token)
        current_request_id.reset(request_token)

    [event] = _events()
    fields = json.loads(event.fields_json)
    assert event.level == "WARNING"
    assert event.event == "grading.warning"
    assert event.user_email == "teacher@example.edu"
    assert event.request_id == "req-123"
    assert fields["email"] == "<redacted>"
    assert fields["kept"] == "ok"


def test_auth_info_persists_but_grading_info_does_not() -> None:
    _clear_events()
    logger = logging.getLogger("test.observability.sink.info")

    log_event(logger, "auth.google.callback.invalid_state", email="teacher@example.edu")
    log_event(logger, "grading.submission.engine_call.start", job_id="job-1")

    events = _events()
    assert [event.event for event in events] == ["auth.google.callback.invalid_state"]
    fields = json.loads(events[0].fields_json)
    assert fields["email"] == "<redacted>"


def test_plain_third_party_error_persists_with_exception_text() -> None:
    _clear_events()
    logger = logging.getLogger("third.party.failure")

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("plain failure")

    [event] = _events()
    assert event.level == "ERROR"
    assert event.event == "third.party.failure"
    assert "RuntimeError: boom" in (event.exc_text or "")


def test_db_event_handler_failure_does_not_raise(monkeypatch) -> None:
    import classroom_downloader.database as database

    monkeypatch.setattr(database, "engine", None)
    record = logging.LogRecord(
        name="test.handler.failure",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=None,
    )
    record.cd_event = "auth.failure"
    record.cd_fields = {}

    DbEventHandler().emit(record)


def test_console_formatting_contract_unchanged() -> None:
    assert (
        _format_event("auth.x", {"email": "ana@example.edu", "count": 2})
        == "auth.x email='<redacted>' count=2"
    )


def test_purge_expired_observability_rows_removes_old_events() -> None:
    _clear_events()
    settings = get_settings()
    original_days = settings.app_event_retention_days
    settings.app_event_retention_days = 30
    try:
        with Session(engine) as session:
            session.add(
                AppEvent(
                    id="old",
                    created_at=datetime.now(UTC) - timedelta(days=31),
                    level="WARNING",
                    event="auth.old",
                    logger_name="test",
                )
            )
            session.add(
                AppEvent(
                    id="new",
                    created_at=datetime.now(UTC),
                    level="WARNING",
                    event="auth.new",
                    logger_name="test",
                )
            )
            session.commit()
            purge_expired_observability_rows(session)

        assert [event.id for event in _events()] == ["new"]
    finally:
        settings.app_event_retention_days = original_days
