"""Criterion scoring and review-mutation tests for the grading pipeline.

Tests that mock engine emits criterion scores correctly, that per-criterion
points are persisted after a draft, and that teacher review derives the
final score from the criterion breakdown (not from the final_score field).
"""

import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from classroom_downloader.main import app
from classroom_downloader.grading_engine import (
    GradingEngineRequest,
    MockGradingEngine,
)
from classroom_downloader.settings import get_settings


def _grade_request(criteria, *, teacher_loop="approve") -> GradingEngineRequest:
    return GradingEngineRequest(
        job_id="job-cs",
        submission_id="sub-cs",
        activity_title="Mitose",
        rubric_mode="structured",
        teacher_loop=teacher_loop,
        rubric_text=None,
        criteria=criteria,
        student_label="Aluno 1",
        source_label="lab.pdf",
        mime_type="text/plain",
        content="x = 1\n",
    )


def test_mock_engine_criterion_scores_sum_to_overall_score() -> None:
    result = MockGradingEngine().grade(
        _grade_request(
            [
                {"name": "Lógica", "weight": 70, "description": None},
                {"name": "Estilo", "weight": 30, "description": None},
            ]
        )
    )
    assert result.criterion_scores is not None
    assert [c["criterion"] for c in result.criterion_scores] == ["Lógica", "Estilo"]
    # Overall score is DERIVED from the parts: sum(earned) == score (rounding aside).
    assert round(sum(c["earned"] for c in result.criterion_scores), 1) == round(
        result.score, 1
    )


def test_mock_engine_omits_criterion_scores_without_criteria() -> None:
    assert MockGradingEngine().grade(_grade_request([])).criterion_scores is None


def test_mock_engine_omits_criterion_scores_when_no_score() -> None:
    # cowrite mode produces no overall score, so there is nothing to distribute.
    result = MockGradingEngine().grade(
        _grade_request(
            [{"name": "Original", "weight": 100, "description": None}],
            teacher_loop="cowrite",
        )
    )
    assert result.score is None
    assert result.criterion_scores is None


def test_draft_persists_criterion_scores_and_review_derives_final_score(tmp_path) -> None:
    # Uses course-real/activity-real which has real gradeable corpus files
    # (docx, html) so the mock engine will assign scores and emit criterion_scores.
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-real",
                "activity_id": "activity-real",
                "rubric_mode": "structured",
                "teacher_loop": "approve",
                "criteria": [
                    {"name": "Lógica", "weight": 70, "description": None},
                    {"name": "Estilo", "weight": 30, "description": None},
                ],
            },
        ).json()
        drafted = client.post(f"/api/grading/jobs/{job['id']}/draft").json()

        # Select the first submission that actually received an AI score (docx/html
        # lane; PDF is vision-gated and will be blocked without visual consent).
        scored = [s for s in drafted["submissions"] if s.get("ai_score") is not None]
        assert scored, (
            "Expected at least one submission with an AI score from course-real; "
            "check that the corpus docx/html files were committed and are extractable."
        )
        submission = scored[0]

        # The mock emitted per-criterion points, persisted and exposed in the snapshot,
        # summing to the AI's overall score.
        scores = submission["criterion_scores"]
        assert len(scores) == 2
        assert round(sum(c["earned"] for c in scores), 1) == round(
            submission["ai_score"], 1
        )
        crit_ids = [c["criterion_id"] for c in scores]

        # Teacher edits the per-criterion points. final_score must be DERIVED from
        # the parts (sum), so the deliberately-wrong final_score below is ignored.
        client.post(
            f"/api/grading/jobs/{job['id']}/submissions/{submission['id']}/review",
            json={
                "final_score": 1,
                "feedback": "ok",
                "reviewed": True,
                "criterion_scores": [
                    {"criterion_id": crit_ids[0], "earned": 60},
                    {"criterion_id": crit_ids[1], "earned": 25},
                ],
            },
        )
        reread = client.get(f"/api/grading/jobs/{job['id']}").json()

    edited = next(s for s in reread["submissions"] if s["id"] == submission["id"])
    assert edited["final_score"] == 85
    assert {(c["criterion_id"], c["earned"]) for c in edited["criterion_scores"]} == {
        (crit_ids[0], 60.0),
        (crit_ids[1], 25.0),
    }
