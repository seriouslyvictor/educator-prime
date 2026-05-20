from collections.abc import Generator

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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
