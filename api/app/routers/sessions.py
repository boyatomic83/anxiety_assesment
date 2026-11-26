from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.encryption import decrypt_json, encrypt_json
from app.core.ratelimit import rate_limit
from app.core.security import hash_secret, new_secret_token
from app.db import get_db
from app.deps import current_user_optional, owned_session
from app.models import AssessmentSession, Response, User
from app.schemas.api import (
    AnswersIn,
    AnswersSaved,
    ContextIn,
    ResultOut,
    SessionCreate,
    SessionCreated,
)
from app.services.assessment import SubmitError, submit
from app.services.questionnaires import QuestionnaireNotFound, get_questionnaire
from app.services.results_view import to_out

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "", response_model=SessionCreated, status_code=201, dependencies=[Depends(rate_limit(30, 60))]
)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_optional),
):
    s = get_settings()
    if body.consent_version != s.consent_version:
        raise HTTPException(409, "Consent text has changed; please review it again")
    token = None if user else new_secret_token()
    sess = AssessmentSession(
        user_id=user.id if user else None,
        guest_token_hash=hash_secret(token) if token else None,
        consent_version=body.consent_version,
        locale=body.locale,
        context_json_encrypted=encrypt_json(body.context.model_dump(exclude_none=True))
        if body.context
        else None,
    )
    db.add(sess)
    db.commit()
    expires = sess.started_at + timedelta(hours=s.guest_retention_hours) if token else None
    return SessionCreated(
        id=sess.id, guest_token=token, consent_version=sess.consent_version, expires_at=expires
    )


def _editable(sess: AssessmentSession) -> None:
    if sess.status == "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Session already submitted")


@router.put("/{session_id}/context", status_code=204)
def update_context(
    body: ContextIn, sess: AssessmentSession = Depends(owned_session), db: Session = Depends(get_db)
):
    _editable(sess)
    current = decrypt_json(sess.context_json_encrypted) or {}
    current.update(body.model_dump(exclude_unset=True))
    sess.context_json_encrypted = encrypt_json(current)
    db.commit()


@router.post("/{session_id}/answers", response_model=AnswersSaved)
def save_answers(
    body: AnswersIn, sess: AssessmentSession = Depends(owned_session), db: Session = Depends(get_db)
):
    """Autosave: partial answers are fine; each call merges into the stored answers."""
    _editable(sess)
    try:
        q = get_questionnaire(body.questionnaire_id)
    except QuestionnaireNotFound:
        raise HTTPException(404, "Questionnaire not found") from None
    items = {i.id: i for i in q.items}
    for item_id, value in body.answers.items():
        if item_id not in items:
            raise HTTPException(422, f"Unknown item {item_id}")
        if value not in {o.value for o in q.options_for(items[item_id])}:
            raise HTTPException(422, f"Invalid answer for {item_id}")
    timings = {k: float(v) for k, v in body.item_timings.items() if k in items and 0 <= v < 3600}

    resp = db.scalar(
        select(Response).where(Response.session_id == sess.id, Response.questionnaire_id == q.id)
    )
    if resp is None:
        resp = Response(
            session_id=sess.id,
            questionnaire_id=q.id,
            questionnaire_version=q.version,
            answers_encrypted=encrypt_json({}),
            item_timings_json={},
        )
        db.add(resp)
    merged = {**(decrypt_json(resp.answers_encrypted) or {}), **body.answers}
    resp.answers_encrypted = encrypt_json(merged)
    resp.item_timings_json = {**(resp.item_timings_json or {}), **timings}
    resp.updated_at = datetime.now(UTC)
    db.commit()
    return AnswersSaved(
        questionnaire_id=q.id, saved_items=len(merged), complete=set(merged) == set(items)
    )


@router.post(
    "/{session_id}/submit", response_model=ResultOut, dependencies=[Depends(rate_limit(20, 60))]
)
def submit_session(sess: AssessmentSession = Depends(owned_session), db: Session = Depends(get_db)):
    """Safety check -> validated scoring -> ML. Returns the result (crisis info if flagged)."""
    try:
        result = submit(db, sess)
    except SubmitError as e:
        raise HTTPException(422, str(e)) from None
    return to_out(result)
