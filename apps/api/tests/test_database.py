from sqlalchemy import create_engine, inspect, text

from classroom_downloader.database import ensure_sqlite_dev_migrations


def test_sqlite_dev_migration_adds_cache_and_grading_metadata_columns(tmp_path) -> None:
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
        connection.execute(
            text(
                """
                CREATE TABLE course (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    section VARCHAR,
                    course_state VARCHAR NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE activity (
                    id VARCHAR PRIMARY KEY,
                    course_id VARCHAR NOT NULL,
                    title VARCHAR NOT NULL,
                    work_type VARCHAR NOT NULL,
                    state VARCHAR NOT NULL,
                    due_label VARCHAR,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE exportfile (
                    id VARCHAR PRIMARY KEY,
                    job_id VARCHAR NOT NULL,
                    course_id VARCHAR NOT NULL,
                    activity_id VARCHAR NOT NULL,
                    activity_name VARCHAR NOT NULL,
                    student_email VARCHAR,
                    student_name VARCHAR,
                    source_file_id VARCHAR NOT NULL,
                    source_name VARCHAR NOT NULL,
                    mime_type VARCHAR NOT NULL,
                    export_mime_type VARCHAR,
                    output_path VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    error VARCHAR
                )
                """
            )
        )

    ensure_sqlite_dev_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("gradingaiattempt")}
    assert {"prompt_tokens", "completion_tokens", "latency_ms"}.issubset(columns)
    course_columns = {column["name"] for column in inspect(engine).get_columns("course")}
    activity_columns = {column["name"] for column in inspect(engine).get_columns("activity")}
    export_columns = {column["name"] for column in inspect(engine).get_columns("exportfile")}
    assert "fetched_at" in course_columns
    assert "fetched_at" in activity_columns
    assert {"cached_path", "content_hash", "byte_size", "cache_expires_at"}.issubset(
        export_columns
    )
