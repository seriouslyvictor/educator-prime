"""Coverage for the resume/preview additions: the global grading-jobs list and
the per-submission preview stream. Written order-independently (assert on the
created job, not global emptiness) to match the shared in-memory DB used by the
rest of the grading suite."""

import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from classroom_downloader.main import app


def _create_job(client, course_id="course-1", activity_id="activity-1"):
    return client.post(
        "/api/grading/jobs",
        json={
            "course_id": course_id,
            "activity_id": activity_id,
            "rubric_mode": "infer",
            "teacher_loop": "approve",
        },
    ).json()


def test_jobs_list_surfaces_created_job() -> None:
    with TestClient(app) as client:
        job = _create_job(client)
        listing = client.get("/api/grading/jobs").json()

    match = [item for item in listing if item["latest_job_id"] == job["id"]]
    assert len(match) == 1
    assert match[0]["course_name"] == "Biology 101"
    assert match[0]["activity_title"] == "Cell Diagram"
    assert match[0]["activity_id"] == "activity-1"


def test_jobs_list_collapses_to_newest_per_activity() -> None:
    with TestClient(app) as client:
        first = _create_job(client, activity_id="activity-2")
        second = _create_job(client, activity_id="activity-2")
        listing = client.get("/api/grading/jobs").json()

    rows = [item for item in listing if item["activity_id"] == "activity-2"]
    assert len(rows) == 1
    assert rows[0]["latest_job_id"] == second["id"]
    assert second["id"] != first["id"]


def test_submission_preview_streams_image_inline() -> None:
    with TestClient(app) as client:
        job = _create_job(client)  # activity-1's first submission is an image/png
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission = drafted["submissions"][0]
        ok = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/preview"
        )
        missing = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/missing/preview"
        )

    assert ok.status_code == 200
    assert ok.content  # cached submission bytes streamed back to the teacher
    assert ok.headers["content-type"].startswith("image/png")
    assert ok.headers["content-disposition"] == "inline"
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert missing.status_code == 404


def test_submission_preview_forces_download_for_unsafe_type() -> None:
    # course-2/activity-3 is a .docx — not on the inline allowlist, so it must be
    # served as an attachment (never rendered as active content on the app origin).
    with TestClient(app) as client:
        job = _create_job(client, course_id="course-2", activity_id="activity-3")
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()
        submission = drafted["submissions"][0]
        response = client.get(
            f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/preview"
        )

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_submission_preview_unknown_job_is_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/grading/jobs/missing/submissions/missing/preview")

    assert response.status_code == 404


def test_draft_resume_does_not_double_run_outlier_review(tmp_path) -> None:
    from uuid import uuid4

    from sqlmodel import Session, select

    from classroom_downloader.database import engine, init_db
    from classroom_downloader.google_provider import MockGoogleProvider, SubmissionFile
    from classroom_downloader.grading import draft_grading_job, ensure_default_criteria
    from classroom_downloader.grading_engine import GradingEngineResult, OutlierFlag
    from classroom_downloader.models import GradingAiAttempt, GradingJob, GradingStatus
    from classroom_downloader.settings import get_settings

    class CountingEngine:
        name = "counting"
        model = None

        def __init__(self):
            self.review_count = 0

        def grade(self, request):
            return GradingEngineResult(
                score=80,
                confidence=0.9,
                feedback="ok",
                flags=[],
                criterion_notes=[],
            )

        def infer_rubric(self, request):
            return []

        def review_outliers(self, request):
            self.review_count += 1
            return [OutlierFlag(id=request.submissions[0].id, reason="Revisar excecao.")]

        def extract_image(self, request):  # pragma: no cover
            raise NotImplementedError

    get_settings().grading_cache_path = str(tmp_path / "grading")
    init_db()
    provider = MockGoogleProvider()
    provider.files = [
        SubmissionFile(
            "file-1",
            "course-resume",
            "activity-resume",
            None,
            "Student One",
            "drive-1",
            "submission.txt",
            "text/plain",
            b"answer text",
        )
    ]
    engine_instance = CountingEngine()
    with Session(engine) as session:
        job = GradingJob(
            id=str(uuid4()),
            course_id="course-resume",
            course_name="Course Resume",
            activity_id="activity-resume",
            activity_title="Activity Resume",
            rubric_mode="brief",
            teacher_loop="approve",
            status=GradingStatus.ready,
        )
        session.add(job)
        ensure_default_criteria(session, job.id, None)
        session.commit()
        session.refresh(job)

        draft_grading_job(session, job, provider, engine_instance)
        draft_grading_job(session, job, provider, engine_instance)
        markers = session.exec(
            select(GradingAiAttempt)
            .where(GradingAiAttempt.job_id == job.id)
            .where(GradingAiAttempt.stage == "outlier_review")
        ).all()

    assert engine_instance.review_count == 1
    assert len(markers) == 1


def test_draft_resume_keeps_one_criterion_score_row_per_criterion(tmp_path) -> None:
    from uuid import uuid4

    from sqlmodel import Session, select

    from classroom_downloader.database import engine, init_db
    from classroom_downloader.google_provider import MockGoogleProvider, SubmissionFile
    from classroom_downloader.grading import draft_grading_job, ensure_default_criteria
    from classroom_downloader.grading_engine import GradingEngineResult
    from classroom_downloader.models import (
        GradingJob,
        GradingStatus,
        GradingSubmission,
        GradingSubmissionCriterionScore,
    )
    from classroom_downloader.schemas import GradingCriterionInput
    from classroom_downloader.settings import get_settings

    class ScoringEngine:
        name = "scoring"
        model = None

        def grade(self, request):
            return GradingEngineResult(
                score=80,
                confidence=0.9,
                feedback="ok",
                flags=[],
                criterion_notes=[],
                criterion_scores=[
                    {"criterion": "Lógica", "earned": 56.0},
                    {"criterion": "Estilo", "earned": 24.0},
                ],
            )

        def infer_rubric(self, request):  # pragma: no cover
            return []

    get_settings().grading_cache_path = str(tmp_path / "grading")
    init_db()
    provider = MockGoogleProvider()
    provider.files = [
        SubmissionFile(
            "file-cs",
            "course-cs",
            "activity-cs",
            None,
            "Student One",
            "drive-cs",
            "submission.txt",
            "text/plain",
            b"answer text",
        )
    ]
    with Session(engine) as session:
        job = GradingJob(
            id=str(uuid4()),
            course_id="course-cs",
            course_name="Course CS",
            activity_id="activity-cs",
            activity_title="Activity CS",
            rubric_mode="structured",
            teacher_loop="approve",
            status=GradingStatus.ready,
        )
        session.add(job)
        ensure_default_criteria(
            session,
            job.id,
            [
                GradingCriterionInput(name="Lógica", weight=70, description=None),
                GradingCriterionInput(name="Estilo", weight=30, description=None),
            ],
        )
        session.commit()
        session.refresh(job)

        # Drafting twice exercises the resume path; criterion-score rows must not
        # accumulate (the persistence helper clears stale rows before inserting).
        draft_grading_job(session, job, provider, ScoringEngine())
        draft_grading_job(session, job, provider, ScoringEngine())

        submission = session.exec(
            select(GradingSubmission).where(GradingSubmission.job_id == job.id)
        ).first()
        rows = session.exec(
            select(GradingSubmissionCriterionScore).where(
                GradingSubmissionCriterionScore.submission_id == submission.id
            )
        ).all()

    assert len(rows) == 2  # exactly one row per criterion, no duplicates after resume
    assert round(sum(r.earned for r in rows), 1) == 80.0


def test_draft_derives_score_from_whole_point_parts_not_holistic(tmp_path) -> None:
    """Regression (append-bar bug): per-criterion points are the source of truth.

    When the engine's parts disagree with its separate holistic score, the overall
    score is the SUM of the parts — stored as WHOLE points clamped to each
    criterion's weight. A correctly graded criterion is never scaled down to fit a
    lower holistic number, and no fractional granularity leaks into the bars."""
    from uuid import uuid4

    from sqlmodel import Session, select

    from classroom_downloader.database import engine, init_db
    from classroom_downloader.google_provider import MockGoogleProvider, SubmissionFile
    from classroom_downloader.grading import draft_grading_job, ensure_default_criteria
    from classroom_downloader.grading_engine import GradingEngineResult
    from classroom_downloader.models import (
        GradingJob,
        GradingStatus,
        GradingSubmission,
        GradingSubmissionCriterionScore,
    )
    from classroom_downloader.schemas import GradingCriterionInput
    from classroom_downloader.settings import get_settings

    class DisagreeingEngine:
        name = "disagree"
        model = None

        def grade(self, request):
            return GradingEngineResult(
                score=75,  # holistic, lower than the sum of the parts (70+15 = 85)
                confidence=0.9,
                feedback="ok",
                flags=[],
                criterion_notes=[],
                criterion_scores=[
                    {"criterion": "Lógica", "earned": 80.0},  # over weight 70 -> clamps to 70
                    {"criterion": "Estilo", "earned": 15.4},  # fractional -> 15
                ],
            )

        def infer_rubric(self, request):  # pragma: no cover
            return []

    get_settings().grading_cache_path = str(tmp_path / "grading")
    init_db()
    provider = MockGoogleProvider()
    provider.files = [
        SubmissionFile("file-d", "course-d", "activity-d", None, "Stu", "drive-d", "s.txt", "text/plain", b"code")
    ]
    with Session(engine) as session:
        job = GradingJob(
            id=str(uuid4()),
            course_id="course-d",
            course_name="C",
            activity_id="activity-d",
            activity_title="A",
            rubric_mode="structured",
            teacher_loop="approve",
            status=GradingStatus.ready,
        )
        session.add(job)
        ensure_default_criteria(
            session,
            job.id,
            [
                GradingCriterionInput(name="Lógica", weight=70, description=None),
                GradingCriterionInput(name="Estilo", weight=30, description=None),
            ],
        )
        session.commit()
        session.refresh(job)
        draft_grading_job(session, job, provider, DisagreeingEngine())
        sub = session.exec(select(GradingSubmission).where(GradingSubmission.job_id == job.id)).first()
        rows = session.exec(
            select(GradingSubmissionCriterionScore).where(
                GradingSubmissionCriterionScore.submission_id == sub.id
            )
        ).all()

    assert sorted(r.earned for r in rows) == [15.0, 70.0]  # whole points, clamped to weight
    assert all(r.earned == int(r.earned) for r in rows)  # integers only
    assert sub.ai_score == 85.0  # derived from sum of parts, NOT the holistic 75


def test_draft_matches_criterion_scores_by_position_when_names_garbled(tmp_path) -> None:
    """Regression (Gemini mojibake / empty bars): when the echoed criterion names
    are corrupted but the order and count are intact, scores are matched to the
    rubric BY POSITION — bars still populate against the right criteria."""
    from uuid import uuid4

    from sqlmodel import Session, select

    from classroom_downloader.database import engine, init_db
    from classroom_downloader.google_provider import MockGoogleProvider, SubmissionFile
    from classroom_downloader.grading import draft_grading_job, ensure_default_criteria
    from classroom_downloader.grading_engine import GradingEngineResult
    from classroom_downloader.models import (
        GradingCriterion,
        GradingJob,
        GradingStatus,
        GradingSubmission,
        GradingSubmissionCriterionScore,
    )
    from classroom_downloader.schemas import GradingCriterionInput
    from classroom_downloader.settings import get_settings

    class GarbledNamesEngine:
        name = "garbled"
        model = None

        def grade(self, request):
            # Names mojibake'd (won't match the rubric), but order/count preserved.
            return GradingEngineResult(
                score=90,
                confidence=0.9,
                feedback="ok",
                flags=[],
                criterion_notes=[],
                criterion_scores=[
                    {"criterion": "L3gica", "earned": 70.0},
                    {"criterion": "Estil3", "earned": 20.0},
                ],
            )

        def infer_rubric(self, request):  # pragma: no cover
            return []

    get_settings().grading_cache_path = str(tmp_path / "grading")
    init_db()
    provider = MockGoogleProvider()
    provider.files = [
        SubmissionFile("file-g", "course-g", "activity-g", None, "Stu", "drive-g", "s.txt", "text/plain", b"code")
    ]
    with Session(engine) as session:
        job = GradingJob(
            id=str(uuid4()),
            course_id="course-g",
            course_name="C",
            activity_id="activity-g",
            activity_title="A",
            rubric_mode="structured",
            teacher_loop="approve",
            status=GradingStatus.ready,
        )
        session.add(job)
        ensure_default_criteria(
            session,
            job.id,
            [
                GradingCriterionInput(name="Lógica", weight=70, description=None),
                GradingCriterionInput(name="Estilo", weight=30, description=None),
            ],
        )
        session.commit()
        session.refresh(job)
        draft_grading_job(session, job, provider, GarbledNamesEngine())
        sub = session.exec(select(GradingSubmission).where(GradingSubmission.job_id == job.id)).first()
        criteria = session.exec(select(GradingCriterion).where(GradingCriterion.job_id == job.id)).all()
        by_id = {c.id: c.name for c in criteria}
        rows = session.exec(
            select(GradingSubmissionCriterionScore).where(
                GradingSubmissionCriterionScore.submission_id == sub.id
            )
        ).all()

    # Despite garbled names, both bars stored, mapped to the right rubric criteria.
    earned_by_name = {by_id[r.criterion_id]: r.earned for r in rows}
    assert earned_by_name == {"Lógica": 70.0, "Estilo": 20.0}
    assert sub.ai_score == 90.0
