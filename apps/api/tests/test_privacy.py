"""Unit tests for the pt-BR privacy scrubber (`classroom_downloader.privacy`).

These exercise `scrub_submission` end-to-end through a throwaway in-memory DB so the
pseudonym lookup works, but the assertions are all about the detection behaviour:
which categories are redacted, which legitimate content is left intact, and the
per-category counts surfaced to the audit report.
"""

from sqlmodel import Session, SQLModel, create_engine

from classroom_downloader.content_extraction import ExtractedSubmissionContent
from classroom_downloader.models import GradingJob, GradingSubmission
from classroom_downloader.privacy import is_valid_cpf, scrub_submission

# A real, checksum-valid CPF (commonly used as a test value).
VALID_CPF = "529.982.247-25"
VALID_CPF_BARE = "52998224725"


def _scrub(text, *, student_name="João da Silva", student_email="joao@example.edu"):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        job = GradingJob(
            id="job-1",
            course_id="c1",
            course_name="Turma",
            activity_id="a1",
            activity_title="Atividade",
            rubric_mode="infer",
            teacher_loop="approve",
        )
        submission = GradingSubmission(
            id="sub-1",
            job_id="job-1",
            student_email=student_email,
            student_name=student_name,
            source_file_id="f1",
            source_name="entrega.txt",
            mime_type="text/plain",
        )
        session.add(job)
        session.add(submission)
        session.commit()
        extracted = ExtractedSubmissionContent(
            status="supported", text=text, safe_source_label="submission_001"
        )
        return scrub_submission(session, job, submission, extracted)


# --- CPF -------------------------------------------------------------------


def test_is_valid_cpf_accepts_valid_and_rejects_invalid():
    assert is_valid_cpf(VALID_CPF) is True
    assert is_valid_cpf(VALID_CPF_BARE) is True
    assert is_valid_cpf("123.456.789-00") is False
    assert is_valid_cpf("111.111.111-11") is False  # repeated digits
    assert is_valid_cpf("52998224720") is False  # wrong check digit


def test_valid_cpf_redacted_formatted_and_bare():
    result = _scrub(f"Meu CPF é {VALID_CPF}.")
    assert "[cpf]" in result.content
    assert "529" not in result.content
    assert result.report.counts.get("cpf") == 1

    bare = _scrub(f"CPF {VALID_CPF_BARE} para cadastro.")
    assert "[cpf]" in bare.content
    assert bare.report.counts.get("cpf") == 1


def test_invalid_cpf_not_redacted():
    # 11 digits but fails the checksum and is not a pt-BR mobile -> left alone.
    result = _scrub("Protocolo 12345678901 registrado.")
    assert "[cpf]" not in result.content
    assert "[phone]" not in result.content
    assert "12345678901" in result.content
    assert result.report.status == "clean"


# --- Phone (pt-BR mobile) --------------------------------------------------


def test_pt_br_phones_redacted():
    for raw in ["955550000", "11955550000", "(11) 95555-0000", "+55 11 95555-0000"]:
        result = _scrub(f"Telefone: {raw}")
        assert "[phone]" in result.content, raw
        assert result.report.counts.get("phone") == 1, raw


def test_numbers_dates_and_decimals_not_treated_as_phone():
    result = _scrub("O valor de pi é 3.14159265 e os anos foram 2024, 2025 e 2026.")
    assert "[phone]" not in result.content
    assert "3.14159265" in result.content
    assert result.report.status == "clean"


# --- URLs / social ---------------------------------------------------------


def test_non_social_urls_preserved():
    text = (
        "Consulte https://api.github.com/users/octocat e "
        "https://docs.python.org/3/library/re.html para a tarefa."
    )
    result = _scrub(text)
    assert "[social]" not in result.content
    assert "api.github.com/users/octocat" in result.content
    assert "docs.python.org" in result.content
    assert result.report.status == "clean"


def test_social_urls_redacted():
    text = "Me segue no https://instagram.com/joaosilva e no discord.gg/xyz123."
    result = _scrub(text)
    assert "[social]" in result.content
    assert "instagram" not in result.content
    assert "discord.gg" not in result.content
    assert result.report.counts.get("social") == 2


# --- Names -----------------------------------------------------------------


def test_full_name_redacted_lone_first_name_preserved():
    result = _scrub(
        "João da Silva escreveu sobre a vitória. Depois, João revisou o texto.",
        student_name="João da Silva",
    )
    assert "[student]" in result.content
    assert "João da Silva" not in result.content
    assert "João revisou" in result.content  # lone first name survives
    assert "vitória" in result.content  # common-noun word untouched
    assert result.report.counts.get("name") == 1


def test_single_token_roster_name_not_redacted():
    result = _scrub(
        "O sol brilha. Sol entregou o trabalho hoje.",
        student_name="Sol",
    )
    assert "[student]" not in result.content
    assert "Sol entregou" in result.content
    assert "name" not in result.report.counts


# --- Email, counts, status -------------------------------------------------


def test_email_redacted():
    result = _scrub("Contato: aluno@escola.edu.br para dúvidas.")
    assert "[email]" in result.content
    assert "aluno@escola.edu.br" not in result.content
    assert result.report.counts.get("email") == 1


def test_clean_text_has_no_counts():
    result = _scrub("Este é um ensaio sobre fotossíntese e o ciclo da água.")
    assert result.report.status == "clean"
    assert result.report.counts == {}


def test_combined_redactions_report_all_categories():
    text = (
        f"João da Silva, CPF {VALID_CPF}, tel 11955550000, "
        "email joao@escola.br, insta instagram.com/joao."
    )
    result = _scrub(text, student_name="João da Silva")
    assert result.report.status == "redacted"
    assert set(result.report.counts) == {"name", "cpf", "phone", "email", "social"}
    # Placeholders must not be re-matched into other categories.
    assert "[student]" in result.content
    assert "[cpf]" in result.content


def test_unsupported_extraction_marked_failed():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        job = GradingJob(
            id="job-1",
            course_id="c1",
            course_name="Turma",
            activity_id="a1",
            activity_title="Atividade",
            rubric_mode="infer",
            teacher_loop="approve",
        )
        submission = GradingSubmission(
            id="sub-1",
            job_id="job-1",
            student_email="x@y.z",
            student_name="João da Silva",
            source_file_id="f1",
            source_name="entrega.png",
            mime_type="image/png",
        )
        session.add(job)
        session.add(submission)
        session.commit()
        extracted = ExtractedSubmissionContent(
            status="unsupported",
            text="",
            safe_source_label="submission_001",
            error="unsupported_visual_submission",
        )
        result = scrub_submission(session, job, submission, extracted)
    assert result.report.status == "failed"
    assert result.content == ""
    assert result.report.counts == {}
