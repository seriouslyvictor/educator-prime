"""SSE / draft-stream and criteria-stream tests for the grading pipeline.

Tests the Server-Sent Events endpoints: draft/stream, criteria/stream,
and related event sequencing, queue ordering, and phase labeling.
"""

import os

os.environ["CD_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CD_GOOGLE_PROVIDER"] = "mock"

from fastapi.testclient import TestClient

from classroom_downloader.main import app
from classroom_downloader.settings import get_settings

from grading_helpers import _sse_payloads


def test_draft_stream_emits_per_submission_progress(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-2",
                "activity_id": "activity-3",
                "rubric_mode": "brief",
                "teacher_loop": "approve",
            },
        ).json()
        client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/draft/stream") as response:
            assert response.status_code == 200
            payloads = _sse_payloads(response)

    progress = [payload for payload in payloads if payload.get("processed")]
    terminal = payloads[-1]
    assert progress
    assert terminal["phase"] == "draft"
    assert terminal["done"] is True
    assert terminal["job"]["id"] == job["id"]
    assert terminal["job"]["status"] in {"reviewing", "completed"}
    assert terminal["job"]["total_submissions"] == progress[-1]["total"]


def test_criteria_stream_infers_before_audit(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        # activity-3 carries a substantial description -> description-first inference.
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-2",
                "activity_id": "activity-3",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/criteria/stream") as response:
            assert response.status_code == 200
            payloads = _sse_payloads(response)

    progress = [payload for payload in payloads if payload.get("phase") == "criteria" and payload.get("processed") is not None]
    terminal = payloads[-1]
    assert progress
    assert terminal["phase"] == "criteria"
    assert terminal["done"] is True
    assert terminal["job"]["id"] == job["id"]
    names = [row["name"] for row in terminal["job"]["criteria"]]
    weights = [row["weight"] for row in terminal["job"]["criteria"]]
    assert names == ["Tese", "Evidências", "Raciocínio", "Organização"]
    assert sum(weights) == 100


def test_update_criteria_replaces_and_survives_reinference(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-2",
                "activity_id": "activity-3",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        updated = client.patch(
            f"/api/grading/jobs/{job['id']}/criteria",
            json={
                "criteria": [
                    {"name": "Lógica", "weight": 70, "description": "Corretude do algoritmo."},
                    {"name": "Estilo", "weight": 30, "description": "Legibilidade."},
                ]
            },
        )
        assert updated.status_code == 200
        assert [c["name"] for c in updated.json()["criteria"]] == ["Lógica", "Estilo"]

        # A later inference pass must keep the teacher's edited rubric, not overwrite it.
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/criteria/stream") as response:
            payloads = _sse_payloads(response)

    terminal = payloads[-1]
    assert [c["name"] for c in terminal["job"]["criteria"]] == ["Lógica", "Estilo"]


def test_draft_stream_seeds_full_queue_in_stable_order(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-1",
                "activity_id": "activity-1",
                "rubric_mode": "brief",
                "teacher_loop": "approve",
            },
        ).json()
        client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/draft/stream") as response:
            assert response.status_code == 200
            payloads = _sse_payloads(response)

    queued_events = [payload for payload in payloads if payload.get("queued")]
    # The queue is seeded as the very first event (from the audit's submissions,
    # before the slow file listing), then re-published authoritatively. Every
    # seed lists all students, alphabetical by name (not cache-warmth order).
    assert queued_events
    assert payloads[0].get("queued"), "queue must be seeded before any drafting work"
    for event in queued_events:
        assert [row["student_name"] for row in event["queued"]] == ["Ana Silva", "Bruno Costa"]
    # Each submission is announced when its drafting starts.
    queued = queued_events[-1]["queued"]
    drafting_ids = [payload["drafting_id"] for payload in payloads if payload.get("drafting_id")]
    assert set(drafting_ids) == {row["id"] for row in queued}


def test_draft_stream_emits_incremental_submissions_without_criteria_phase(tmp_path) -> None:
    get_settings().grading_cache_path = str(tmp_path / "grading")
    with TestClient(app) as client:
        job = client.post(
            "/api/grading/jobs",
            json={
                "course_id": "course-2",
                "activity_id": "activity-3",
                "rubric_mode": "infer",
                "teacher_loop": "approve",
            },
        ).json()
        client.post(f"/api/grading/jobs/{job['id']}/privacy-audit")
        with client.stream("GET", f"/api/grading/jobs/{job['id']}/draft/stream") as response:
            assert response.status_code == 200
            payloads = _sse_payloads(response)

    phases = [payload.get("phase") for payload in payloads]
    assert "criteria" not in phases
    assert "draft" in phases
    submission_events = [payload for payload in payloads if payload.get("submission")]
    assert submission_events
    assert all(payload["submission"]["id"] for payload in submission_events)
    assert all(payload["submission"]["ai_attempt_status"] for payload in submission_events)
    terminal = [p for p in payloads if p.get("done")]
    assert len(terminal) == 1
    assert terminal[0]["phase"] == "draft"
    assert terminal[0]["job"]["total_submissions"] == len(submission_events)
