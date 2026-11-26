from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import audit, require_role
from app.models import AuditLog, User
from app.schemas.api import AuditOut, RoleIn, UserOut
from app.services.ml import model_info
from app.services.questionnaires import load_all

router = APIRouter(prefix="/admin", tags=["admin"])
admin = require_role("admin")


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    request: Request,
    limit: int = Query(100, le=1000),
    user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    audit(db, request, user, "admin.view_audit", None)
    db.commit()
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()


@router.get("/models")
def models(user: User = Depends(admin)):
    return {"active": model_info()}


@router.get("/questionnaires")
def questionnaires(user: User = Depends(admin)):
    return [
        {"id": q.id, "name": q.name, "version": q.version, "source": q.source, "licence": q.licence}
        for q in load_all().values()
    ]


@router.post("/users/role", response_model=UserOut)
def set_role(
    body: RoleIn, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)
):
    target = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if target is None:
        raise HTTPException(404, "User not found")
    target.role = body.role
    audit(db, request, user, "admin.set_role", f"{target.id}:{body.role}")
    db.commit()
    return target
