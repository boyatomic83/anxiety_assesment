"""Shared FastAPI dependencies: DB session, current user, session access, audit."""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_token, hash_secret
from app.db import get_db
from app.models import AssessmentSession, AuditLog, User

_bearer = HTTPBearer(auto_error=False)


def current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials, "access")
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (TokenError, ValueError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        return user

    return dep


def owned_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(current_user_optional),
    x_session_token: str | None = Header(default=None),
) -> AssessmentSession:
    s = db.get(AssessmentSession, session_id)
    if s is None or not can_access_session(s, user, x_session_token):
        # Same 404 for "missing" and "not yours" so ids can't be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return s


def can_access_session(s: AssessmentSession, user: User | None, guest_token: str | None) -> bool:
    if user is not None and s.user_id == user.id:
        return True
    return bool(
        s.user_id is None
        and s.guest_token_hash
        and guest_token
        and hash_secret(guest_token) == s.guest_token_hash
    )


def audit(db: Session, request: Request, actor: User | None, action: str, target: str | None):
    ip = request.client.host if request.client else None
    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action=action,
            target=target,
            ip_hash=hash_secret(ip) if ip else None,
        )
    )
