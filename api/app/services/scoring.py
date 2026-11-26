"""Deterministic, validated scoring (SPEC.md section 6.1).

This is the PRIMARY result and always takes priority over the ML estimate.
It is pure: (definition, answers) -> score. No I/O, no randomness.
The safety check (services/safety.py) must run before this on every submit.
"""

from collections.abc import Mapping

from pydantic import BaseModel

from app.schemas.questionnaire import Band, QuestionnaireDef


class InvalidAnswers(ValueError):
    pass


class BandScore(BaseModel):
    score: int
    band: str
    level: int


class ScoreResult(BaseModel):
    questionnaire_id: str
    questionnaire_version: str
    total: int
    band: str | None  # None for subscale-only instruments (DASS-21)
    level: int | None
    subscales: dict[str, BandScore]


def _band_for(score: int, bands: list[Band]) -> Band:
    for b in bands:
        if b.min <= score <= b.max:
            return b
    raise InvalidAnswers(f"score {score} is outside every band")  # unreachable for valid defs


def validate_answers(q: QuestionnaireDef, answers: Mapping[str, int]) -> None:
    expected = set(q.item_ids)
    missing = expected - answers.keys()
    unknown = answers.keys() - expected
    if missing:
        raise InvalidAnswers(f"{q.id}: missing answers for {sorted(missing)}")
    if unknown:
        raise InvalidAnswers(f"{q.id}: unknown items {sorted(unknown)}")
    for item in q.items:
        value = answers[item.id]
        # bool is an int subclass; reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidAnswers(f"{item.id}: answer must be an integer")
        allowed = {o.value for o in q.options_for(item)}
        if value not in allowed:
            raise InvalidAnswers(f"{item.id}: {value} is not one of {sorted(allowed)}")


def score(q: QuestionnaireDef, answers: Mapping[str, int]) -> ScoreResult:
    validate_answers(q, answers)
    subscales: dict[str, BandScore] = {}

    if q.scoring.method == "subscales":
        for key, sub in (q.scoring.subscales or {}).items():
            s = sum(answers[i] for i in sub.items) * sub.multiplier
            b = _band_for(s, sub.bands)
            subscales[key] = BandScore(score=s, band=b.label, level=b.level)
        total = sum(v.score for v in subscales.values())
        band_label, level = None, None
    else:
        raw = sum(answers[i] for i in q.item_ids)
        total = raw * 2 if q.scoring.method == "sum_x2" else raw
        b = _band_for(total, q.bands)
        band_label, level = b.label, b.level

    return ScoreResult(
        questionnaire_id=q.id,
        questionnaire_version=q.version,
        total=total,
        band=band_label,
        level=level,
        subscales=subscales,
    )
