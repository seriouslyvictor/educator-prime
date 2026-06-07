from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
import re
from uuid import uuid4

from sqlmodel import Session, select

from .content_extraction import ExtractedSubmissionContent
from .models import GradingJob, GradingPseudonym, GradingSubmission
from .observability import get_logger, log_event, text_preview


logger = get_logger(__name__)


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

# pt-BR mobile only: optional +55, optional DDD (2 digits, maybe parenthesised),
# then the 9-prefixed 9-digit mobile number with optional separators. Matches
# 955550000, 11955550000, (11) 95555-0000, +55 11 95555-0000. The required "9"
# prefix + fixed length keeps it from eating decimals/dates/math like 3.14159265.
PHONE_PATTERN = re.compile(
    r"\b(?:\+?55[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?9\d{4}[\s.-]?\d{4}\b"
)

# CPF: 000.000.000-00 or bare 00000000000. The match is only redacted if it
# passes the mod-11 checksum (see is_valid_cpf), so real CPFs are caught while
# phone numbers / arbitrary 11-digit runs are not.
CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")

# RG: only formatted (12.345.678-9 / 12.345.678-X) or label-prefixed (RG: 12345678-9)
# RGs are redacted. A bare unformatted RG is indistinguishable from any other
# number, so it is intentionally left alone to avoid over-redaction.
RG_PATTERN = re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-?[\dxX]\b")
RG_LABEL_PATTERN = re.compile(r"\bRG\s*:?\s*\d[\d.\-]{5,11}[\dxX]\b", re.IGNORECASE)

# Social-media hosts only. Generic / API / documentation URLs are intentionally
# left intact so that code submissions are not corrupted before grading.
SOCIAL_DOMAINS = (
    "instagram.com", "instagr.am",
    "twitter.com", "x.com",
    "facebook.com", "m.facebook.com", "fb.com", "fb.me",
    "wa.me", "whatsapp.com", "chat.whatsapp.com",
    "discord.gg", "discord.com", "discordapp.com",
    "tiktok.com",
    "t.me", "telegram.me", "telegram.org",
    "snapchat.com",
    "linkedin.com", "lnkd.in",
    "youtube.com", "youtu.be",
)
SOCIAL_PATTERN = re.compile(
    r"\b(?:https?://)?(?:www\.)?(?:"
    + "|".join(re.escape(domain) for domain in SOCIAL_DOMAINS)
    + r")(?:/\S*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Detector:
    category: str
    pattern: re.Pattern[str]
    replacement: str
    validator: Callable[[str], bool] | None = None


# Order matters: CPF (checksum-validated) runs before phone so a valid 11-digit
# CPF is not mistaken for a phone number.
_STATIC_DETECTORS: tuple[_Detector, ...] = (
    _Detector("cpf", CPF_PATTERN, "[cpf]", validator=lambda value: is_valid_cpf(value)),
    _Detector("rg", RG_PATTERN, "[rg]"),
    _Detector("rg", RG_LABEL_PATTERN, "[rg]"),
    _Detector("email", EMAIL_PATTERN, "[email]"),
    _Detector("phone", PHONE_PATTERN, "[phone]"),
    _Detector("social", SOCIAL_PATTERN, "[social]"),
)


@dataclass(frozen=True)
class PrivacyReport:
    status: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def flags(self) -> list[str]:
        # Back-compat view for readers/logs that still think in terms of flags.
        return sorted(self.counts)


@dataclass(frozen=True)
class ScrubbedSubmission:
    student_label: str
    source_label: str
    content: str
    report: PrivacyReport


def is_valid_cpf(raw: str) -> bool:
    """Validate a Brazilian CPF by its two mod-11 check digits."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    nums = [int(char) for char in digits]
    for length in (9, 10):
        total = sum(nums[i] * ((length + 1) - i) for i in range(length))
        check = (total * 10) % 11
        if check == 10:
            check = 0
        if check != nums[length]:
            return False
    return True


def _name_detector(student_name: str | None) -> _Detector | None:
    """Redact the full roster name as a whole phrase.

    Only fires for multi-token names (a real full name); single-token rosters are
    skipped so a lone first name -- which may collide with a common pt-BR word
    (Vitória, Sol, Graça) -- never mangles surrounding prose.
    """
    if not student_name:
        return None
    tokens = student_name.split()
    if len(tokens) < 2:
        return None
    pattern = re.compile(
        r"\b" + r"\s+".join(re.escape(token) for token in tokens) + r"\b",
        re.IGNORECASE,
    )
    return _Detector("name", pattern, "[student]")


def _apply_detectors(
    content: str, detectors: Iterable[_Detector]
) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for detector in detectors:
        def repl(match: re.Match[str], detector: _Detector = detector) -> str:
            value = match.group(0)
            if detector.validator and not detector.validator(value):
                return value
            counts[detector.category] = counts.get(detector.category, 0) + 1
            return detector.replacement

        content = detector.pattern.sub(repl, content)
    return content, counts


def scrub_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    extracted: ExtractedSubmissionContent,
) -> ScrubbedSubmission:
    pseudonym = pseudonym_for_submission(session, job, submission)
    log_event(
        logger,
        "privacy.scrub.start",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        source_file_id=submission.source_file_id,
        source_name=submission.source_name,
        extracted_status=extracted.status,
        extracted_error=extracted.error,
        extracted_preview=text_preview(extracted.text),
        student_label=pseudonym.student_label,
        source_label=pseudonym.source_label,
    )
    if extracted.status in {"failed", "unsupported"}:
        log_event(
            logger,
            "privacy.scrub.blocked_input",
            job_id=job.id,
            submission_id=submission.id,
            status="failed",
            error=extracted.error or extracted.status,
        )
        return ScrubbedSubmission(
            student_label=pseudonym.student_label,
            source_label=pseudonym.source_label,
            content="",
            report=PrivacyReport(status="failed", counts={}),
        )

    detectors: list[_Detector] = []
    name_detector = _name_detector(submission.student_name)
    if name_detector:
        detectors.append(name_detector)
    detectors.extend(_STATIC_DETECTORS)

    content, counts = _apply_detectors(extracted.text, detectors)
    status = "redacted" if counts else "clean"

    result = ScrubbedSubmission(
        student_label=pseudonym.student_label,
        source_label=pseudonym.source_label,
        content=content,
        report=PrivacyReport(status=status, counts=counts),
    )
    log_event(
        logger,
        "privacy.scrub.complete",
        job_id=job.id,
        submission_id=submission.id,
        student_label=result.student_label,
        source_label=result.source_label,
        status=result.report.status,
        counts=result.report.counts,
        scrubbed_preview=text_preview(result.content),
    )
    return result


def pseudonym_for_submission(
    session: Session,
    job: GradingJob,
    submission: GradingSubmission,
    commit: bool = True,
) -> GradingPseudonym:
    existing = session.exec(
        select(GradingPseudonym)
        .where(GradingPseudonym.job_id == job.id)
        .where(GradingPseudonym.submission_id == submission.id)
    ).first()
    if existing:
        log_event(
            logger,
            "privacy.pseudonym.hit",
            job_id=job.id,
            submission_id=submission.id,
            student_label=existing.student_label,
            source_label=existing.source_label,
        )
        return existing

    count = len(
        session.exec(select(GradingPseudonym).where(GradingPseudonym.job_id == job.id)).all()
    )
    row = GradingPseudonym(
        id=str(uuid4()),
        job_id=job.id,
        submission_id=submission.id,
        student_label=f"student_{count + 1:03d}",
        source_label=f"submission_{count + 1:03d}",
    )
    session.add(row)
    if commit:
        session.commit()
    else:
        session.flush()
    session.refresh(row)
    log_event(
        logger,
        "privacy.pseudonym.create",
        job_id=job.id,
        submission_id=submission.id,
        student_email=submission.student_email,
        student_name=submission.student_name,
        student_label=row.student_label,
        source_label=row.source_label,
    )
    return row
