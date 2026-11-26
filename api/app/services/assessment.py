"""Submit pipeline: SAFETY -> validated SCORING -> ML. Order is fixed (CLAUDE.md rules)."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.encryption import decrypt_json
from app.models import AssessmentSession, Result
from app.services import features as feats
from app.services import ml, safety
from app.services.questionnaires import get_questionnaire
from app.services.scoring import InvalidAnswers, score

# Questionnaire whose band level the ML composite (0-3) is compared against.
ML_REFERENCE = "gad7"


class SubmitError(ValueError):
    pass


def collect(session: AssessmentSession) -> tuple[dict, dict, dict]:
    answers: dict[str, dict[str, int]] = {}
    timings: dict[str, float] = {}
    for r in session.responses:
        answers[r.questionnaire_id] = decrypt_json(r.answers_encrypted)
        timings.update(r.item_timings_json or {})
    context = decrypt_json(session.context_json_encrypted) or {}
    return answers, timings, context


def submit(db: Session, session: AssessmentSession) -> Result:
    if session.status == "submitted" and session.result is not None:
        return session.result
    answers, timings, context = collect(session)
    if not answers:
        raise SubmitError("no answers saved")
    # GAD-2 answers are the first two GAD-7 items; score GAD-7 alone when both are present.
    if "gad7" in answers:
        answers.pop("gad2", None)

    # 1. SAFETY FIRST -- before scoring and ML, on every submit.
    safety_result = safety.check(answers, context.get("free_text"))
    session.flagged = safety_result.flagged

    # 2. Validated scoring (primary result).
    scores: dict[str, dict] = {}
    for qid, a in answers.items():
        try:
            scores[qid] = score(get_questionnaire(qid), a).model_dump()
        except InvalidAnswers as e:
            raise SubmitError(str(e)) from e

    # 3. ML composite (secondary), only with the full GAD-7 + PHQ-9 + OASIS set.
    ml_json = None
    quality = None
    if feats.has_required(answers):
        x = feats.build_features(answers, context, timings)
        ref = scores.get(ML_REFERENCE, {}).get("level")
        ml_json = ml.estimate(x, ref)
        quality = feats.response_quality(answers, timings)

    result = Result(
        session_id=session.id,
        scores_json={
            "questionnaires": scores,
            "safety": safety_result.model_dump(),
            "response_quality": quality,
        },
        ml_json=ml_json,
        model_version=ml_json["model_version"] if ml_json else None,
    )
    session.status = "submitted"
    session.submitted_at = datetime.now(UTC)
    db.add(result)
    db.commit()
    db.refresh(result)
    return result
