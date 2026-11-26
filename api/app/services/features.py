"""Feature pipeline shared by training (ml/src) and inference (services/ml.py).

Pure Python + math only: no app config, so ml/ can import it directly.
Missing values are float('nan'); XGBoost handles them natively, logistic regression imputes.
"""

import math
from collections.abc import Mapping
from statistics import median

ITEM_FEATURES = (
    [f"gad7_{i}" for i in range(1, 8)]
    + [f"phq9_{i}" for i in range(1, 10)]
    + [f"oasis_{i}" for i in range(1, 6)]
)
CONTEXT_FEATURES = [
    "age_band",
    "sleep_hours",
    "symptom_duration",
    "stressful_event",
    "caffeine_cups",
    "mean_item_seconds",
    "fast_item_ratio",
]
FEATURES = ITEM_FEATURES + CONTEXT_FEATURES
REQUIRED_QUESTIONNAIRES = ("gad7", "phq9", "oasis")
CLASSES = ["minimal", "mild", "moderate", "severe"]

AGE_BANDS = {"18-24": 0, "25-34": 1, "35-44": 2, "45-54": 3, "55-64": 4, "65+": 5}
DURATIONS = {"<2w": 0, "2w-1m": 1, "1-6m": 2, "6m+": 3}
FAST_SECONDS = 1.5

_NAMES = {"gad7": "GAD-7", "phq9": "PHQ-9", "oasis": "OASIS"}
FEATURE_LABELS = {
    **{f: f"{_NAMES[f.split('_')[0]]} item {f.split('_')[1]}" for f in ITEM_FEATURES},
    "age_band": "Age group",
    "sleep_hours": "Sleep hours",
    "symptom_duration": "How long symptoms have lasted",
    "stressful_event": "Recent stressful event",
    "caffeine_cups": "Caffeine per day",
    "mean_item_seconds": "Time spent per question",
    "fast_item_ratio": "Share of very quick answers",
}

NAN = float("nan")


def _num(v: object) -> float:
    if v is None or isinstance(v, bool):
        return float(v) if isinstance(v, bool) else NAN
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return NAN


def has_required(answers: Mapping[str, Mapping[str, int]]) -> bool:
    return all(q in answers for q in REQUIRED_QUESTIONNAIRES)


def build_features(
    answers: Mapping[str, Mapping[str, int]],
    context: Mapping[str, object] | None,
    timings: Mapping[str, float] | None,
) -> list[float]:
    """answers: {questionnaire_id: {item_id: value}}; timings: {item_id: seconds}."""
    flat: dict[str, int] = {}
    for qid in REQUIRED_QUESTIONNAIRES:
        flat.update(answers.get(qid, {}))
    ctx = context or {}
    secs = [float(t) for t in (timings or {}).values() if t is not None and t >= 0]
    row = {f: _num(flat.get(f)) for f in ITEM_FEATURES}
    row["age_band"] = _num(AGE_BANDS.get(str(ctx.get("age_band"))))
    sleep = _num(ctx.get("sleep_hours"))
    row["sleep_hours"] = min(max(sleep, 0.0), 14.0) if not math.isnan(sleep) else NAN
    row["symptom_duration"] = _num(DURATIONS.get(str(ctx.get("symptom_duration"))))
    row["stressful_event"] = _num(ctx.get("stressful_event"))
    cups = _num(ctx.get("caffeine_cups"))
    row["caffeine_cups"] = min(cups, 10.0) if not math.isnan(cups) else NAN
    row["mean_item_seconds"] = min(sum(secs) / len(secs), 60.0) if secs else NAN
    row["fast_item_ratio"] = sum(s < FAST_SECONDS for s in secs) / len(secs) if secs else NAN
    return [row[f] for f in FEATURES]


def response_quality(
    answers: Mapping[str, Mapping[str, int]], timings: Mapping[str, float] | None
) -> dict:
    """Rule-based careless-responding checks (SPEC.md section 6.2)."""
    flags: list[str] = []
    values = [v for q in REQUIRED_QUESTIONNAIRES for v in answers.get(q, {}).values()]
    if len(values) >= 7 and len(set(values)) == 1:
        flags.append("identical_answers")
    secs = [float(t) for t in (timings or {}).values() if t is not None and t >= 0]
    if len(secs) >= 5 and median(secs) < FAST_SECONDS:
        flags.append("very_fast")
    gad7 = sum(answers.get("gad7", {}).values()) if "gad7" in answers else None
    oasis = sum(answers.get("oasis", {}).values()) if "oasis" in answers else None
    if (
        gad7 is not None
        and oasis is not None
        and ((gad7 >= 15 and oasis <= 3) or (gad7 <= 2 and oasis >= 14))
    ):
        flags.append("contradictory")
    return {"ok": not flags, "flags": flags}
