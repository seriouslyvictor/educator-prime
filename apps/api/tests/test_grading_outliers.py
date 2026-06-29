"""Outlier-review behavior tests for the grading pipeline.

Tests that the outlier review pass (pass-2) applies, skips, and fails gracefully.
"""

import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from sqlmodel import Session, select

from classroom_downloader.database import engine
from classroom_downloader.grading_engine import (
    GradingEngine,
    GradingEngineRequest,
    GradingEngineResult,
    OutlierFlag,
)
from classroom_downloader.models import GradingStatus, GradingSubmission
from classroom_downloader.settings import get_settings

from grading_helpers import _infer_provider, _seed_infer_job, _text_submission_file


class _OutlierEngine(GradingEngine):
    name = "outlier-test"
    model = None

    def __init__(self, flags: list[OutlierFlag] | None = None):
        self.flags = flags or []
        self.review_requests = []

    def grade(self, request: GradingEngineRequest) -> GradingEngineResult:
        score = 40 if "wrong exercise" in request.content.lower() else 90
        return GradingEngineResult(
            score=score,
            confidence=0.9,
            feedback="Rascunho gerado.",
            flags=["generic_review_noise"],
            criterion_notes=[],
        )

    def infer_rubric(self, request):
        return []

    def review_outliers(self, request):
        self.review_requests.append(request)
        if self.flags:
            return self.flags
        return [
            OutlierFlag(id=row.id, reason="Entrega de outro exercicio.")
            for row in request.submissions
            if "wrong exercise" in row.content.lower()
        ]

    def extract_image(self, request):  # pragma: no cover - not used here
        raise NotImplementedError


class _RaisingOutlierEngine(_OutlierEngine):
    def review_outliers(self, request):
        raise RuntimeError("simulated outlier-pass failure")


def test_outlier_review_applies_only_returned_flags_and_clears_pass1_noise(tmp_path) -> None:
    from classroom_downloader.grading import draft_grading_job

    get_settings().grading_cache_path = str(tmp_path / "grading")
    provider = _infer_provider(
        [
            _text_submission_file(1, "activity-infer", "completed the requested exercise"),
            _text_submission_file(2, "activity-infer", "wrong exercise entirely"),
            _text_submission_file(3, "activity-infer", "also completed the requested exercise"),
        ]
    )
    engine_instance = _OutlierEngine()
    with Session(engine) as session:
        job = _seed_infer_job(session, description="Long enough description for drafting.")
        drafted = draft_grading_job(session, job, provider, engine_instance)
        submissions = session.exec(select(GradingSubmission).where(GradingSubmission.job_id == drafted.id)).all()

    flags = {row.source_name: row.flag for row in submissions}
    assert list(flags.values()).count("Entrega de outro exercicio.") == 1
    assert all(flag != "generic_review_noise" for flag in flags.values())
    assert engine_instance.review_requests
    assert len(engine_instance.review_requests[0].submissions) == 3


def test_outlier_review_gate_off_keeps_drafting_free_of_outlier_flags(tmp_path) -> None:
    from classroom_downloader.grading import draft_grading_job

    settings = get_settings()
    settings.grading_cache_path = str(tmp_path / "grading")
    settings.grading_outlier_review = "off"
    provider = _infer_provider([_text_submission_file(1, "activity-infer", "wrong exercise entirely")])
    engine_instance = _OutlierEngine(flags=[OutlierFlag(id="never", reason="should not run")])
    with Session(engine) as session:
        job = _seed_infer_job(session, description="Long enough description for drafting.")
        drafted = draft_grading_job(session, job, provider, engine_instance)
        submissions = session.exec(select(GradingSubmission).where(GradingSubmission.job_id == drafted.id)).all()

    assert engine_instance.review_requests == []
    assert [row.flag for row in submissions] == [None]


def test_outlier_review_excludes_blocked_rows(tmp_path) -> None:
    from classroom_downloader.google_provider import SubmissionFile
    from classroom_downloader.grading import draft_grading_job

    get_settings().grading_cache_path = str(tmp_path / "grading")
    files = [
        _text_submission_file(1, "activity-infer", "completed the requested exercise"),
        SubmissionFile(
            "file-bad",
            "course-infer",
            "activity-infer",
            None,
            "Student Bad",
            "drive-bad",
            "bad.bin",
            "application/octet-stream",
            b"\xff\x00\x00",
        ),
    ]
    provider = _infer_provider(files)
    engine_instance = _OutlierEngine()
    with Session(engine) as session:
        job = _seed_infer_job(session, description="Long enough description for drafting.")
        draft_grading_job(session, job, provider, engine_instance)

    assert engine_instance.review_requests
    assert len(engine_instance.review_requests[0].submissions) == 1


def test_outlier_review_failure_does_not_fail_drafting(tmp_path) -> None:
    from classroom_downloader.grading import draft_grading_job
    from classroom_downloader.grading.drafting import _outlier_review_already_completed

    get_settings().grading_cache_path = str(tmp_path / "grading")
    provider = _infer_provider(
        [
            _text_submission_file(1, "activity-infer", "completed the requested exercise"),
            _text_submission_file(2, "activity-infer", "another completed exercise"),
        ]
    )
    engine_instance = _RaisingOutlierEngine()
    with Session(engine) as session:
        job = _seed_infer_job(session, description="Long enough description for drafting.")
        # Must not raise even though review_outliers raises.
        drafted = draft_grading_job(session, job, provider, engine_instance)
        submissions = session.exec(select(GradingSubmission).where(GradingSubmission.job_id == drafted.id)).all()
        already_completed = _outlier_review_already_completed(session, drafted.id)

    # Job must be in a reviewable/completed state, not failed.
    assert drafted.status in {GradingStatus.reviewing, GradingStatus.completed}
    # Pass-1 drafts are intact — every submission still has score and feedback.
    assert all(sub.ai_score is not None for sub in submissions)
    assert all(sub.feedback for sub in submissions)
    # No outlier flag was applied (fell back to mechanical/None).
    assert all(sub.flag is None for sub in submissions)
    # Marker was recorded with status="failed" so a future re-draft can retry.
    assert already_completed is False
