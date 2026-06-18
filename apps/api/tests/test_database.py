from sqlalchemy import create_engine, inspect, text

from classroom_downloader.database import ensure_sqlite_dev_migrations


def test_sqlite_dev_migration_adds_cache_and_grading_metadata_columns(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE gradingjob (
                    id VARCHAR PRIMARY KEY,
                    course_id VARCHAR NOT NULL,
                    course_name VARCHAR NOT NULL,
                    activity_id VARCHAR NOT NULL,
                    user_email VARCHAR NOT NULL DEFAULT '',
                    activity_title VARCHAR NOT NULL,
                    rubric_mode VARCHAR NOT NULL,
                    teacher_loop VARCHAR NOT NULL,
                    batch_mode VARCHAR NOT NULL DEFAULT 'per_submission',
                    include_visual_submissions BOOLEAN NOT NULL DEFAULT 0,
                    status VARCHAR NOT NULL,
                    total_submissions INTEGER NOT NULL DEFAULT 0,
                    reviewed_submissions INTEGER NOT NULL DEFAULT 0,
                    flagged_submissions INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE gradingsubmission (
                    id VARCHAR PRIMARY KEY,
                    job_id VARCHAR NOT NULL,
                    student_email VARCHAR,
                    student_name VARCHAR,
                    source_file_id VARCHAR NOT NULL,
                    source_name VARCHAR NOT NULL,
                    mime_type VARCHAR NOT NULL,
                    ai_score FLOAT,
                    confidence FLOAT,
                    final_score FLOAT,
                    feedback VARCHAR,
                    reviewed BOOLEAN NOT NULL DEFAULT 0,
                    flag VARCHAR,
                    error VARCHAR,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
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
        connection.execute(
            text(
                """
                CREATE TABLE oauthstate (
                    id VARCHAR PRIMARY KEY,
                    scopes_json VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE usersession (
                    id VARCHAR PRIMARY KEY,
                    user_email VARCHAR NOT NULL,
                    google_credentials_json VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    last_seen_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE gradingscrubcache (
                    id VARCHAR PRIMARY KEY,
                    job_id VARCHAR NOT NULL,
                    submission_id VARCHAR NOT NULL,
                    content_hash VARCHAR NOT NULL,
                    identity_hash VARCHAR NOT NULL,
                    student_label VARCHAR NOT NULL,
                    source_label VARCHAR NOT NULL,
                    safe_source_label VARCHAR NOT NULL,
                    scrubbed_content VARCHAR NOT NULL,
                    extraction_status VARCHAR NOT NULL,
                    extraction_error VARCHAR,
                    privacy_status VARCHAR NOT NULL,
                    privacy_flags_json VARCHAR NOT NULL DEFAULT '[]',
                    byte_size INTEGER NOT NULL,
                    expires_at DATETIME NOT NULL,
                    deleted_at DATETIME,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE privacyauditrow (
                    id VARCHAR PRIMARY KEY,
                    audit_id VARCHAR NOT NULL,
                    job_id VARCHAR NOT NULL,
                    submission_id VARCHAR NOT NULL,
                    student_label VARCHAR NOT NULL,
                    redacted_source_name VARCHAR NOT NULL,
                    mime_type VARCHAR NOT NULL,
                    byte_size INTEGER NOT NULL,
                    extraction_status VARCHAR NOT NULL,
                    extraction_error VARCHAR,
                    privacy_status VARCHAR NOT NULL,
                    privacy_flags_json VARCHAR NOT NULL DEFAULT '[]',
                    remaining_direct_identifier_hits_json VARCHAR NOT NULL DEFAULT '[]',
                    audit_pass BOOLEAN NOT NULL DEFAULT 0,
                    blocked_reason VARCHAR,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    ensure_sqlite_dev_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("gradingaiattempt")}
    assert {"prompt_tokens", "completion_tokens", "latency_ms", "privacy_flags_json"}.issubset(columns)
    course_columns = {column["name"] for column in inspect(engine).get_columns("course")}
    activity_columns = {column["name"] for column in inspect(engine).get_columns("activity")}
    export_columns = {column["name"] for column in inspect(engine).get_columns("exportfile")}
    submission_columns = {
        column["name"] for column in inspect(engine).get_columns("gradingsubmission")
    }
    assert "fetched_at" in course_columns
    assert "fetched_at" in activity_columns
    assert {"cached_path", "content_hash", "byte_size", "cache_expires_at"}.issubset(
        export_columns
    )
    assert {
        "classroom_submission_id",
        "alternate_link",
        "posted_to_classroom",
        "posted_at",
    }.issubset(submission_columns)
    job_columns = {
        column["name"] for column in inspect(engine).get_columns("gradingjob")
    }
    assert "queue_state" in job_columns
    session_columns = {
        column["name"] for column in inspect(engine).get_columns("usersession")
    }
    assert {
        "google_granted_scopes_json",
        "google_last_scope_update_at",
    }.issubset(session_columns)
    oauth_state_columns = {
        column["name"] for column in inspect(engine).get_columns("oauthstate")
    }
    assert {"capability", "reason"}.issubset(oauth_state_columns)
    scrub_columns = {
        column["name"] for column in inspect(engine).get_columns("gradingscrubcache")
    }
    audit_row_columns = {
        column["name"] for column in inspect(engine).get_columns("privacyauditrow")
    }
    assert "redaction_counts_json" in scrub_columns
    assert "redaction_counts_json" in audit_row_columns
