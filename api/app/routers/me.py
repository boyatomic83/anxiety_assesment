from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_json
from app.core.security import hash_secret
from app.db import get_db
from app.deps import current_user
from app.models import AssessmentSession, Result, User
from app.routers.auth import REFRESH_COOKIE
from app.schemas.api import ClaimIn, HistoryItem, SettingsIn, UserOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("", response_model=UserOut)
def update_settings(
    body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    if body.locale:
        user.locale = body.locale
    if body.clear_reminder:
        user.reminder_days = None
    elif body.reminder_days:
        user.reminder_days = body.reminder_days
    db.commit()
    return user


@router.get("/history", response_model=list[HistoryItem])
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Result)
        .join(AssessmentSession)
        .where(AssessmentSession.user_id == user.id)
        .order_by(Result.created_at)
    ).all()
    return [
        HistoryItem(
            result_id=r.id,
            created_at=r.created_at,
            flagged=r.session.flagged,
            scores=r.scores_json["questionnaires"],
        )
        for r in rows
    ]


@router.post("/sessions/claim", status_code=204)
def claim_session(body: ClaimIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Attach a guest session to the account (so it is kept beyond 24h)."""
    s = db.get(AssessmentSession, body.session_id)
    if (
        s is None
        or s.user_id is not None
        or not s.guest_token_hash
        or s.guest_token_hash != hash_secret(body.guest_token)
    ):
        raise HTTPException(404, "Session not found")
    s.user_id = user.id
    s.guest_token_hash = None
    db.commit()


@router.get("/export")
def export_data(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything we hold about the user, decrypted (DPDP Act / GDPR-style access right)."""
    sessions = db.scalars(
        select(AssessmentSession).where(AssessmentSession.user_id == user.id)
    ).all()
    return {
        "account": {
            "email": user.email,
            "role": user.role,
            "locale": user.locale,
            "created_at": user.created_at.isoformat(),
            "reminder_days": user.reminder_days,
        },
        "sessions": [
            {
                "id": str(s.id),
                "started_at": s.started_at.isoformat(),
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "consent_version": s.consent_version,
                "flagged": s.flagged,
                "context": decrypt_json(s.context_json_encrypted),
                "responses": {
                    r.questionnaire_id: decrypt_json(r.answers_encrypted) for r in s.responses
                },
                "result": {"scores": s.result.scores_json, "ml": s.result.ml_json}
                if s.result
                else None,
            }
            for s in sessions
        ],
    }


@router.delete("", status_code=204)
def delete_me(
    response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    """Delete the account and all its sessions, answers, results and shares."""
    db.delete(user)
    db.commit()
    response.delete_cookie(REFRESH_COOKIE)
