import zipfile
from datetime import UTC, datetime
from pathlib import Path

from classroom_downloader.content_extraction import extract_submission_content
from classroom_downloader.models import GradingFileCache
from classroom_downloader.zip_extraction import (
    MAX_ENTRY_COUNT,
    MAX_ENTRY_TEXT_BYTES,
    extract_zip_submission,
    render_zip_submission_text,
)


def _write_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _cache_file(path: Path, *, mime_type: str = "application/zip") -> GradingFileCache:
    return GradingFileCache(
        id="cache-1",
        job_id="job-1",
        submission_id="submission-1",
        source_file_id="drive-1",
        source_name="entrega.zip",
        mime_type=mime_type,
        cached_path=str(path),
        content_hash="not-used",
        byte_size=path.stat().st_size,
        expires_at=datetime.now(UTC),
    )


def test_extracts_allowlisted_text_entries(tmp_path: Path) -> None:
    path = _write_zip(
        tmp_path / "ok.zip",
        {
            "src/main.py": b"print('ola')\n",
            "README.md": b"# Projeto\n",
        },
    )

    result = extract_zip_submission(path)

    assert result.error is None
    assert result.skipped == []
    assert result.truncated is False
    assert [entry.name for entry in result.entries] == ["src/main.py", "README.md"]
    text = render_zip_submission_text(result)
    assert "[arquivo: src/main.py]" in text
    assert "print('ola')" in text
    assert "[arquivos ignorados]" not in text


def test_skips_disallowed_extensions_with_reason(tmp_path: Path) -> None:
    path = _write_zip(
        tmp_path / "mixed.zip",
        {
            "trabalho.txt": b"resposta",
            "virus.exe": b"MZ\x90\x00",
            "setup.bat": b"@echo off",
        },
    )

    result = extract_zip_submission(path)

    assert result.error is None
    assert [entry.name for entry in result.entries] == ["trabalho.txt"]
    skipped_names = {entry.name for entry in result.skipped}
    assert skipped_names == {"virus.exe", "setup.bat"}
    assert all(entry.reason == "extensão não permitida" for entry in result.skipped)
    text = render_zip_submission_text(result)
    assert "[arquivos ignorados]" in text
    assert "virus.exe (extensão não permitida)" in text


def test_excluded_directories_are_noise_not_degradation(tmp_path: Path) -> None:
    path = _write_zip(
        tmp_path / "project.zip",
        {
            "app/index.js": b"console.log(1)",
            "node_modules/lib/index.js": b"junk",
            "__MACOSX/._index.js": b"junk",
            ".git/config": b"junk",
        },
    )

    result = extract_zip_submission(path)

    assert result.error is None
    assert [entry.name for entry in result.entries] == ["app/index.js"]
    assert result.skipped == []
    assert result.noise_count == 3


def test_skips_nested_archives_traversal_names_and_binary_content(tmp_path: Path) -> None:
    path = tmp_path / "weird.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("inner.zip", b"PK\x03\x04")
        archive.writestr("../escape.txt", b"fora")
        archive.writestr("/absolute.txt", b"fora")
        archive.writestr("fake.py", b"\xff" * 7)
        link = zipfile.ZipInfo("link.txt")
        link.external_attr = 0o120777 << 16
        archive.writestr(link, b"alvo")
        archive.writestr("ok.txt", b"valido")

    result = extract_zip_submission(path)

    assert result.error is None
    assert [entry.name for entry in result.entries] == ["ok.txt"]
    reasons = {entry.name: entry.reason for entry in result.skipped}
    assert reasons["inner.zip"] == "arquivo compactado aninhado"
    assert reasons["../escape.txt"] == "nome de arquivo inválido"
    assert reasons["/absolute.txt"] == "nome de arquivo inválido"
    assert reasons["fake.py"] == "conteúdo binário"
    assert reasons["link.txt"] == "link simbólico"


def test_rejects_encrypted_archive(tmp_path: Path) -> None:
    path = _write_zip(tmp_path / "secret.zip", {"hidden.txt": b"segredo"})
    # zipfile cannot write encrypted archives, so flip the encryption bit in
    # the central directory header (offset 8 after the PK\x01\x02 signature).
    data = bytearray(path.read_bytes())
    index = data.find(b"PK\x01\x02")
    data[index + 8] |= 0x1
    path.write_bytes(bytes(data))

    result = extract_zip_submission(path)

    assert result.error == "zip_encrypted"
    assert result.entries == []


def test_rejects_too_many_entries(tmp_path: Path) -> None:
    entries = {f"file{i}.txt": b"x" for i in range(MAX_ENTRY_COUNT + 1)}
    path = _write_zip(tmp_path / "many.zip", entries)

    result = extract_zip_submission(path)

    assert result.error == "zip_too_many_files"


def test_rejects_total_uncompressed_over_limit(tmp_path: Path) -> None:
    payload = b"\x00" * (51 * 1024 * 1024)
    path = _write_zip(tmp_path / "huge.zip", {"big.txt": payload})

    result = extract_zip_submission(path)

    assert result.error == "zip_too_large"


def test_rejects_suspicious_compression_ratio(tmp_path: Path) -> None:
    payload = b"\x00" * (20 * 1024 * 1024)
    path = _write_zip(tmp_path / "bomb.zip", {"bomb.txt": payload})

    result = extract_zip_submission(path)

    assert result.error == "zip_suspicious_compression"


def test_rejects_invalid_zip_bytes(tmp_path: Path) -> None:
    path = tmp_path / "fake.zip"
    path.write_bytes(b"isto nao e um zip")

    result = extract_zip_submission(path)

    assert result.error == "zip_invalid"


def test_skips_entry_over_per_file_cap_and_marks_budget_truncation(tmp_path: Path) -> None:
    big_entry = b"a" * (MAX_ENTRY_TEXT_BYTES + 1)
    budget_filler = b"b" * MAX_ENTRY_TEXT_BYTES
    path = _write_zip(
        tmp_path / "heavy.zip",
        {
            "grande.txt": big_entry,
            "um.txt": budget_filler,
            "dois.txt": budget_filler,
            "tres.txt": budget_filler,
        },
    )

    result = extract_zip_submission(path)

    assert result.error is None
    reasons = {entry.name: entry.reason for entry in result.skipped}
    assert reasons["grande.txt"] == "arquivo grande demais"
    assert reasons["tres.txt"] == "limite total de leitura atingido"
    assert result.truncated is True
    assert [entry.name for entry in result.entries] == ["um.txt", "dois.txt"]


def test_extract_submission_content_routes_zip_to_supported(tmp_path: Path) -> None:
    path = _write_zip(tmp_path / "entrega.zip", {"resposta.txt": b"resposta final"})

    extracted = extract_submission_content(_cache_file(path))

    assert extracted.status == "supported"
    assert "resposta final" in extracted.text
    assert extracted.safe_source_label == "submission.zip"


def test_extract_submission_content_marks_partial_zip_degraded(tmp_path: Path) -> None:
    path = _write_zip(
        tmp_path / "entrega.zip",
        {"resposta.txt": b"resposta", "tool.exe": b"MZ"},
    )

    extracted = extract_submission_content(_cache_file(path))

    assert extracted.status == "degraded"
    assert "tool.exe" in extracted.text


def test_extract_submission_content_rejects_zip_without_gradeable_entries(
    tmp_path: Path,
) -> None:
    path = _write_zip(tmp_path / "entrega.zip", {"app.exe": b"MZ", "data.bin": b"\x00"})

    extracted = extract_submission_content(_cache_file(path))

    assert extracted.status == "unsupported"
    assert extracted.error == "zip_no_gradeable_entries"
    assert extracted.text == ""


def test_extract_submission_content_detects_zip_by_source_name(tmp_path: Path) -> None:
    path = _write_zip(tmp_path / "entrega.zip", {"resposta.txt": b"ok"})

    extracted = extract_submission_content(
        _cache_file(path, mime_type="application/octet-stream")
    )

    assert extracted.status == "supported"
    assert "[arquivo: resposta.txt]" in extracted.text
