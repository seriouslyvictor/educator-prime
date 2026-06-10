from uuid import uuid4

from sqlmodel import Session, select

from ..models import GradingCriterion
from ..observability import get_logger
from ..schemas import GradingCriterionInput
from ..settings import get_settings

logger = get_logger(__name__)


DEFAULT_CRITERIA = [
    GradingCriterionInput(
        name="Understanding",
        weight=30,
        description="Shows command of the core concepts in the assignment.",
    ),
    GradingCriterionInput(
        name="Evidence",
        weight=25,
        description="Uses relevant details, sources, examples, or artifacts.",
    ),
    GradingCriterionInput(
        name="Reasoning",
        weight=30,
        description="Connects evidence to conclusions with clear logic.",
    ),
    GradingCriterionInput(
        name="Clarity",
        weight=15,
        description="Communicates in an organized, readable way.",
    ),
]


def ensure_default_criteria(
    session: Session,
    job_id: str,
    criteria: list[GradingCriterionInput] | None,
) -> None:
    rows = criteria or DEFAULT_CRITERIA
    for criterion in rows:
        session.add(
            GradingCriterion(
                id=str(uuid4()),
                job_id=job_id,
                name=criterion.name,
                weight=criterion.weight,
                description=criterion.description,
            )
        )


def _criteria_match_defaults(criteria: list[GradingCriterion]) -> bool:
    if len(criteria) != len(DEFAULT_CRITERIA):
        return False
    for row, default in zip(criteria, DEFAULT_CRITERIA, strict=True):
        if row.name != default.name or row.weight != default.weight or row.description != default.description:
            return False
    return True


def _normalize_inferred_criteria(
    rows: list[dict[str, str | int | None]] | None,
) -> list[GradingCriterionInput]:
    if not rows:
        return []
    criteria: list[GradingCriterionInput] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        try:
            weight = int(row.get("weight") or 0)
        except (TypeError, ValueError):
            weight = 0
        description_value = row.get("description")
        description = str(description_value).strip() if description_value else None
        if not name or weight <= 0:
            continue
        criteria.append(
            GradingCriterionInput(
                name=name,
                weight=weight,
                description=description,
            )
        )
    return criteria


def _replace_job_criteria(
    session: Session,
    job_id: str,
    criteria: list[GradingCriterionInput],
) -> list[GradingCriterion]:
    existing = session.exec(
        select(GradingCriterion).where(GradingCriterion.job_id == job_id)
    ).all()
    for row in existing:
        session.delete(row)
    session.flush()
    created: list[GradingCriterion] = []
    for criterion in criteria:
        row = GradingCriterion(
            id=str(uuid4()),
            job_id=job_id,
            name=criterion.name,
            weight=criterion.weight,
            description=criterion.description,
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def _is_substantial_description(text: str | None) -> bool:
    settings = get_settings()
    if not text:
        return False
    normalized = " ".join(text.split())
    return (
        len(normalized) >= settings.rubric_description_min_chars
        and len(normalized.split()) >= settings.rubric_description_min_words
    )


def _normalize_weights_to_100(
    criteria: list[GradingCriterionInput],
) -> list[GradingCriterionInput]:
    total = sum(criterion.weight for criterion in criteria)
    if not criteria or total <= 0:
        return []
    scaled: list[GradingCriterionInput] = []
    running = 0
    for index, criterion in enumerate(criteria):
        if index == len(criteria) - 1:
            weight = max(1, 100 - running)
        else:
            weight = max(1, round(criterion.weight * 100 / total))
            running += weight
        scaled.append(
            GradingCriterionInput(
                name=criterion.name,
                weight=weight,
                description=criterion.description,
            )
        )
    return scaled


def _apply_criterion_notes(
    session: Session,
    criteria: list[GradingCriterion],
    criterion_notes: list[dict[str, str]],
) -> None:
    notes_by_name = {
        note["criterion"].strip().lower(): note["note"].strip()
        for note in criterion_notes
        if note.get("criterion") and note.get("note")
    }
    if not notes_by_name:
        return
    for criterion in criteria:
        note = notes_by_name.get(criterion.name.strip().lower())
        if note:
            criterion.latest_ai_note = note
            session.add(criterion)
