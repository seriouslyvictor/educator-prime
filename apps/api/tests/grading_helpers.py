"""Shared plain helpers for grading backend tests.

These are plain functions, not pytest fixtures. Fixtures live in conftest.py.
Imported by test_grading_outliers, test_grading_privacy, test_grading_streams,
and the main test_grading module.
"""

import json


def _sse_payloads(response) -> list[dict]:
    payloads: list[dict] = []
    for line in response.iter_lines():
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        if line.startswith("data: "):
            payloads.append(json.loads(line.removeprefix("data: ")))
    return payloads


def _text_submission_file(idx: int, activity_id: str, content: str):
    from classroom_downloader.google_provider import SubmissionFile

    return SubmissionFile(
        f"file-{idx}",
        "course-infer",
        activity_id,
        None,
        f"Student {idx}",
        f"drive-{idx}",
        f"submission-{idx}.txt",
        "text/plain",
        content.encode("utf-8"),
    )


def _infer_provider(files):
    from classroom_downloader.google_provider import MockGoogleProvider

    provider = MockGoogleProvider()
    provider.files = files
    return provider


def _seed_infer_job(session, *, description, activity_id="activity-infer"):
    from uuid import uuid4

    from classroom_downloader.database import init_db
    from classroom_downloader.grading import ensure_default_criteria
    from classroom_downloader.models import GradingJob, GradingStatus

    init_db()
    job = GradingJob(
        id=str(uuid4()),
        course_id="course-infer",
        course_name="Infer Course",
        activity_id=activity_id,
        activity_title="Infer Activity",
        activity_description=description,
        rubric_mode="infer",
        teacher_loop="approve",
        status=GradingStatus.ready,
    )
    session.add(job)
    ensure_default_criteria(session, job.id, None)
    session.commit()
    session.refresh(job)
    return job
