"""Crisis detection. Runs FIRST on every submit, before scoring and ML (SPEC.md section 5).

Flags when any questionnaire safety item meets its threshold (PHQ-9 item 9 > 0) or the
free text contains a crisis keyword. Never blocks the user from seeing their results.
"""

import json
import re
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.services.questionnaires import get_questionnaire

CORE = Path(__file__).resolve().parent.parent / "core"


class SafetyResult(BaseModel):
    flagged: bool
    reasons: list[str]  # machine codes only, e.g. "item:phq9_9", "free_text"


@lru_cache
def _keyword_patterns() -> list[re.Pattern[str]]:
    data = json.loads((CORE / "crisis_keywords.json").read_text(encoding="utf-8"))
    words = [w for lang, ws in data.items() if not lang.startswith("_") for w in ws]
    return [re.compile(rf"(?<!\w){re.escape(_normalise(w))}(?!\w)") for w in words]


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text)


def free_text_has_crisis_language(text: str | None) -> bool:
    if not text:
        return False
    t = _normalise(text)
    return any(p.search(t) for p in _keyword_patterns())


def check(answers: Mapping[str, Mapping[str, int]], free_text: str | None) -> SafetyResult:
    """answers: {questionnaire_id: {item_id: value}}"""
    reasons: list[str] = []
    for qid, item_answers in answers.items():
        for rule in get_questionnaire(qid).safety_items:
            value = item_answers.get(rule.item_id)
            if isinstance(value, int) and value >= rule.min_value:
                reasons.append(f"item:{rule.item_id}")
    if free_text_has_crisis_language(free_text):
        reasons.append("free_text")
    return SafetyResult(flagged=bool(reasons), reasons=reasons)


@lru_cache
def _helplines() -> dict:
    return json.loads((CORE / "helplines.json").read_text(encoding="utf-8"))


def helplines_for(country: str | None) -> dict:
    """Helplines for an ISO country code. India is the default market (SPEC.md section 5)."""
    data = _helplines()
    return data.get((country or "IN").upper(), data["default"])
