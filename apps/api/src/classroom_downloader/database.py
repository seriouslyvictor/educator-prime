from collections.abc import Generator

from sqlalchemy import Engine, inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from .settings import get_settings


settings = get_settings()
engine_kwargs = {}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
if settings.database_url == "sqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    ensure_sqlite_dev_migrations(engine)


def ensure_sqlite_dev_migrations(target_engine: Engine) -> None:
    if target_engine.dialect.name != "sqlite":
        return
    _ensure_activity_columns(target_engine)
    _ensure_grading_job_columns(target_engine)
    _ensure_grading_submission_columns(target_engine)
    _ensure_grading_criterion_columns(target_engine)
    _ensure_grading_ai_attempt_columns(target_engine)
    _ensure_privacy_columns(target_engine)
    _ensure_cache_columns(target_engine)


def _ensure_activity_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "activity",
        {
            "description": "VARCHAR",
        },
    )


def _ensure_grading_job_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "gradingjob",
        {
            "rubric_text": "VARCHAR",
            "activity_description": "VARCHAR",
            "batch_mode": "VARCHAR DEFAULT 'per_submission'",
            "total_prompt_tokens": "INTEGER",
            "total_completion_tokens": "INTEGER",
            "total_cached_tokens": "INTEGER",
            "total_cost_cents": "FLOAT",
            "wall_clock_ms": "INTEGER",
            "submissions_graded": "INTEGER DEFAULT 0",
            "ai_engine": "VARCHAR",
            "ai_mode": "VARCHAR",
            "ai_model": "VARCHAR",
        },
    )


def _ensure_grading_submission_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "gradingsubmission",
        {
            "group_key": "VARCHAR",
            "classroom_submission_id": "VARCHAR",
            "alternate_link": "VARCHAR",
            "posted_to_classroom": "BOOLEAN DEFAULT 0",
            "posted_at": "DATETIME",
        },
    )


def _ensure_grading_criterion_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "gradingcriterion",
        {
            "latest_ai_note": "VARCHAR",
        },
    )


def _ensure_grading_ai_attempt_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "gradingaiattempt",
        {
            "prompt_tokens": "INTEGER",
            "completion_tokens": "INTEGER",
            "cached_prompt_tokens": "INTEGER",
            "cache_write_tokens": "INTEGER",
            "latency_ms": "INTEGER",
            "privacy_flags_json": "VARCHAR DEFAULT '[]'",
        },
    )


def _ensure_privacy_columns(target_engine: Engine) -> None:
    _ensure_columns(
        target_engine,
        "gradingscrubcache",
        {
            "redaction_counts_json": "VARCHAR DEFAULT '{}'",
        },
    )
    _ensure_columns(
        target_engine,
        "privacyauditrow",
        {
            "redaction_counts_json": "VARCHAR DEFAULT '{}'",
        },
    )


def _ensure_columns(
    target_engine: Engine,
    table_name: str,
    required_columns: dict[str, str],
) -> None:
    inspector = inspect(target_engine)
    if table_name not in inspector.get_table_names():
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    with target_engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def _ensure_cache_columns(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    table_names = set(inspector.get_table_names())
    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in table_names
    }
    required_columns = {
        "course": {
            "fetched_at": "DATETIME",
        },
        "activity": {
            "fetched_at": "DATETIME",
        },
        "exportfile": {
            "cached_path": "VARCHAR",
            "content_hash": "VARCHAR",
            "byte_size": "INTEGER",
            "cache_expires_at": "DATETIME",
        },
    }
    with target_engine.begin() as connection:
        for table_name, columns in required_columns.items():
            if table_name not in table_names:
                continue
            existing_columns = table_columns[table_name]
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
