from classroom_downloader.naming import build_output_path, sanitize_segment


def test_sanitize_segment_removes_filesystem_hostile_characters() -> None:
    assert sanitize_segment('Lab: "Cells"/Part*1?') == "Lab- Cells-Part-1"


def test_build_output_path_deduplicates_without_overwrite() -> None:
    used_paths: set[str] = set()

    first = build_output_path(
        "Biology",
        "Cells",
        "diagram.png",
        "student@example.edu",
        None,
        "file-1",
        used_paths,
    )
    second = build_output_path(
        "Biology",
        "Cells",
        "diagram.png",
        "student@example.edu",
        None,
        "file-2",
        used_paths,
    )

    assert first == "Biology/Cells/student@example.edu--diagram.png"
    assert second == "Biology/Cells/student@example.edu--diagram-2.png"
