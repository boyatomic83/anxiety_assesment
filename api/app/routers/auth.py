import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.core.security import TokenError, create_token, decode_token, hash_password, verify_password
from app.db import get_db
from app.models import User
from app.schemas.api import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "calma_refresh"
_limit = [Depends(rate_limit(10, 60))]
# Constant-time-ish login: verify against a dummy hash when the email is unknown.
_DUMMY_HASH = hash_password("not-a-real-password-xxxxxxxx")


def _issue(user: User, response: Response) -> TokenOut:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        create_token(user.id, user.role, "refresh"),
        max_age=s.refresh_token_expire_days * 86400,
        httponly=True,
        secure=s.is_production,
        # Web and API live on different sites in production (Vercel + Render), so the
        # refresh cookie must be SameSite=None (which requires Secure).
        samesite="none" if s.is_production else "lax",
        path=f"{s.api_prefix}/auth",
    )
    return TokenOut(
        access_token=create_token(user.id, user.role, "access"), user=UserOut.model_validate(user)
    )


@router.post("/register", response_model=TokenOut, status_code=201, dependencies=_limit)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password), locale=body.locale)
    db.add(user)
    db.commit()
    return _issue(user, response)


@router.post("/login", response_model=TokenOut, dependencies=_limit)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise HTTPException(401, "Email or password is incorrect")
    return _issue(user, response)


@router.post("/refresh", response_model=TokenOut, dependencies=_limit)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    calma_refresh: str | None = Cookie(default=None),
):
    if not calma_refresh:
        raise HTTPException(401, "Not signed in")
    try:
        payload = decode_token(calma_refresh, "refresh")
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (TokenError, ValueError, KeyError):
        raise HTTPException(401, "Session expired, please sign in again") from None
    if user is None:
        raise HTTPException(401, "Session expired, please sign in again")
    return _issue(user, response)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE, path=f"{get_settings().api_prefix}/auth")
