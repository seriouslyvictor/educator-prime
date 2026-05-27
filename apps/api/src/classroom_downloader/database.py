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
    _ensure_grading_ai_attempt_columns(target_engine)


def _ensure_grading_ai_attempt_columns(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "gradingaiattempt" not in inspector.get_table_names():
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns("gradingaiattempt")
    }
    required_columns = {
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "latency_ms": "INTEGER",
    }
    with target_engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE gradingaiattempt "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
