from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from classroom_downloader.grading_engine import GradingEngineRequest, get_grading_engine


def main() -> None:
    engine = get_grading_engine()
    result = engine.grade(
        GradingEngineRequest(
            job_id="smoke-job",
            submission_id="smoke-submission",
            activity_title="Smoke Test Assignment",
            rubric_mode="brief",
            teacher_loop="approve",
            student_label="student_001",
            source_label="submission_001",
            mime_type="text/plain",
            content=(
                "This is a scrubbed local smoke test submission. "
                "It contains no real student data."
            ),
        )
    )
    print(result)


if __name__ == "__main__":
    main()
