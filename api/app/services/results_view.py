"""Turn a stored Result into the public ResultOut shape."""

from app.core.encryption import decrypt_json
from app.models import Result
from app.schemas.api import DISCLAIMER, ResultOut
from app.services.safety import helplines_for


def to_out(result: Result) -> ResultOut:
    s = result.session
    ctx = decrypt_json(s.context_json_encrypted) or {}
    scores = result.scores_json
    return ResultOut(
        id=result.id,
        session_id=s.id,
        created_at=result.created_at,
        flagged=s.flagged,
        crisis=helplines_for(ctx.get("country")) if s.flagged else None,
        scores=scores["questionnaires"],
        ml=result.ml_json,
        response_quality=scores.get("response_quality"),
        disclaimer=DISCLAIMER,
    )
