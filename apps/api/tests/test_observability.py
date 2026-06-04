import io
import json
import logging

from classroom_downloader.google_provider import SubmissionFile
from classroom_downloader.observability import (
    JsonEventFormatter,
    log_cache_hit,
    log_cache_miss,
    log_event,
    safe_fields,
)
from classroom_downloader.settings import get_settings


def test_safe_fields_redacts_student_identity_and_bounds_values() -> None:
    settings = get_settings()
    settings.log_preview_chars = 20
    file = SubmissionFile(
        id="file-1",
        course_id="course-1",
        activity_id="activity-1",
        student_email="ana.silva@example.edu",
        student_name="Ana Silva",
        source_file_id="drive-file-1",
        source_name="very-long-submission-name.txt",
        mime_type="text/plain",
        content=b"not logged",
    )

    fields = safe_fields(file)
    rendered = repr(fields)

    assert fields["student_email"] == "<redacted>"
    assert fields["student_name"] == "<redacted>"
    assert "ana.silva@example.edu" not in rendered
    assert "Ana Silva" not in rendered
    assert "truncated" in rendered


def test_log_event_redacts_sensitive_field_names(caplog) -> None:
    logger = logging.getLogger("test.observability.redaction")

    with caplog.at_level(logging.INFO):
        log_event(
            logger,
            "submission.logged",
            student_email="ana.silva@example.edu",
            student_name="Ana Silva",
        )

    line = caplog.records[-1].message
    assert "student_email='<redacted>'" in line
    assert "student_name='<redacted>'" in line
    assert "ana.silva@example.edu" not in line
    assert "Ana Silva" not in line


def test_json_event_formatter_serializes_event_and_fields() -> None:
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="cache.hit cache='courses' key='all'",
        args=(),
        exc_info=None,
    )
    payload = json.loads(JsonEventFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "cache.hit cache='courses' key='all'"
    assert payload["timestamp"]


def test_cache_helpers_emit_standard_pair() -> None:
    logger = logging.getLogger("test.observability.cache")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        log_cache_hit(logger, "courses", "all", stored_count=2)
        log_cache_miss(logger, "courses", "all")
    finally:
        logger.handlers = []
        logger.propagate = True

    output = stream.getvalue()
    assert "cache.hit cache='courses' key='all' stored_count=2" in output
    assert "cache.miss cache='courses' key='all'" in output
