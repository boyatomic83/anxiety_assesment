import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response as RawResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import audit, require_role
from app.models import AssessmentSession, Result, Share, User
from app.schemas.api import PatientResult, RedeemIn, ResultOut
from app.services.results_view import to_out

router = APIRouter(prefix="/clinician", tags=["clinician"])
clinician = require_role("clinician", "admin")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _shared_results(db: Session, user: User, flagged_only: bool = False) -> list[Result]:
    q = (
        select(Result)
        .join(Share, Share.result_id == Result.id)
        .join(AssessmentSession, AssessmentSession.id == Result.session_id)
        .where(Share.clinician_id == user.id, Share.expires_at > datetime.now(UTC))
    )
    if flagged_only:
        q = q.where(AssessmentSession.flagged.is_(True))
    rows = db.scalars(q.distinct()).all()
    # Flagged first, then newest first (SPEC.md section 5)
    return sorted(rows, key=lambda r: (not r.session.flagged, -_aware(r.created_at).timestamp()))


def _row(r: Result) -> PatientResult:
    owner = r.session.user_id
    return PatientResult(
        result_id=r.id,
        patient_ref=str(owner)[:8] if owner else "guest",
        created_at=r.created_at,
        flagged=r.session.flagged,
        scores=r.scores_json["questionnaires"],
        ml_composite=(r.ml_json or {}).get("composite_label"),
    )


@router.post("/shares/redeem", response_model=PatientResult)
def redeem(
    body: RedeemIn, request: Request, user: User = Depends(clinician), db: Session = Depends(get_db)
):
    share = db.scalar(select(Share).where(Share.code == body.code.strip().upper()))
    if (
        share is None
        or _aware(share.expires_at) <= datetime.now(UTC)
        or (share.clinician_id not in (None, user.id))
    ):
        raise HTTPException(404, "Share code not found or expired")
    share.clinician_id = user.id
    audit(db, request, user, "share.redeem", str(share.result_id))
    db.commit()
    return _row(share.result)


@router.get("/patients", response_model=list[PatientResult])
def patients(request: Request, user: User = Depends(clinician), db: Session = Depends(get_db)):
    audit(db, request, user, "clinician.list_patients", None)
    db.commit()
    return [_row(r) for r in _shared_results(db, user)]


@router.get("/flagged", response_model=list[PatientResult])
def flagged(request: Request, user: User = Depends(clinician), db: Session = Depends(get_db)):
    audit(db, request, user, "clinician.list_flagged", None)
    db.commit()
    return [_row(r) for r in _shared_results(db, user, flagged_only=True)]


@router.get("/results/{result_id}", response_model=ResultOut)
def view_result(
    result_id: str, request: Request, user: User = Depends(clinician), db: Session = Depends(get_db)
):
    match = next((r for r in _shared_results(db, user) if str(r.id) == result_id), None)
    if match is None:
        raise HTTPException(404, "Result not found")
    audit(db, request, user, "clinician.view_result", result_id)
    db.commit()
    return to_out(match)


@router.get("/export.csv")
def export_csv(request: Request, user: User = Depends(clinician), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "result_id",
            "patient_ref",
            "created_at",
            "flagged",
            "questionnaire",
            "total",
            "band",
            "subscales",
            "ml_composite",
        ]
    )
    for r in _shared_results(db, user):
        row = _row(r)
        for qid, s in row.scores.items():
            subs = ";".join(
                f"{k}={v['score']}:{v['band']}" for k, v in s.get("subscales", {}).items()
            )
            w.writerow(
                [
                    row.result_id,
                    row.patient_ref,
                    row.created_at.isoformat(),
                    row.flagged,
                    qid,
                    s["total"],
                    s["band"] or "",
                    subs,
                    row.ml_composite or "",
                ]
            )
    audit(db, request, user, "clinician.export", None)
    db.commit()
    return RawResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="calma-shared-results.csv"',
            "Cache-Control": "no-store",
        },
    )
