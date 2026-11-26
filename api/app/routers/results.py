import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response as RawResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.encryption import decrypt_json
from app.db import get_db
from app.deps import can_access_session, current_user, current_user_optional
from app.models import Result, Share, User
from app.schemas.api import ResultOut, ShareOut
from app.services.report import build_pdf
from app.services.results_view import to_out
from app.services.safety import helplines_for

router = APIRouter(prefix="/results", tags=["results"])
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def accessible_result(
    result_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_optional),
    x_session_token: str | None = Header(default=None),
) -> Result:
    r = db.get(Result, result_id)
    if r is None or not can_access_session(r.session, user, x_session_token):
        raise HTTPException(404, "Result not found")
    return r


@router.get("/{result_id}", response_model=ResultOut)
def get_result(r: Result = Depends(accessible_result)):
    return to_out(r)


@router.get("/{result_id}/pdf")
def result_pdf(r: Result = Depends(accessible_result)):
    ctx = decrypt_json(r.session.context_json_encrypted) or {}
    pdf = build_pdf(
        r.scores_json["questionnaires"],
        r.ml_json,
        r.session.flagged,
        helplines_for(ctx.get("country")),
        r.created_at,
    )
    return RawResponse(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="calma-report-{r.created_at:%Y-%m-%d}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.post("/{result_id}/share", response_model=ShareOut, status_code=201)
def share_result(
    r: Result = Depends(accessible_result),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Signed-in users only: a guest's data is deleted after 24h, so sharing needs an account."""
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    share = Share(
        result_id=r.id,
        code=code,
        expires_at=datetime.now(UTC) + timedelta(days=get_settings().share_code_ttl_days),
    )
    db.add(share)
    db.commit()
    return ShareOut(code=code, expires_at=share.expires_at)
