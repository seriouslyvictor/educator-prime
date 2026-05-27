from sqlalchemy import create_engine, inspect, text

from classroom_downloader.database import ensure_sqlite_dev_migrations


def test_sqlite_dev_migration_adds_grading_attempt_metadata_columns(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE gradingaiattempt (
                    id VARCHAR PRIMARY KEY,
                    job_id VARCHAR NOT NULL,
                    submission_id VARCHAR NOT NULL,
                    engine VARCHAR NOT NULL,
                    model VARCHAR,
                    status VARCHAR NOT NULL,
                    extraction_status VARCHAR NOT NULL,
                    privacy_status VARCHAR NOT NULL,
                    safe_error VARCHAR,
                    flags_json VARCHAR NOT NULL DEFAULT '[]',
                    token_count INTEGER,
                    cost_cents FLOAT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    ensure_sqlite_dev_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("gradingaiattempt")}
    assert {"prompt_tokens", "completion_tokens", "latency_ms"}.issubset(columns)
