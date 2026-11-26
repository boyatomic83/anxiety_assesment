import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import _session_factory
from app.models import User
from app.routers import admin, auth, clinician, health, me, questionnaires, results, sessions
from app.services.jobs import run_periodically

log = logging.getLogger(__name__)


def bootstrap_admin() -> None:
    s = get_settings()
    if not s.admin_password:
        return
    try:
        with _session_factory()() as db:
            email = s.admin_email.lower()
            if db.scalar(select(User).where(func.lower(User.email) == email)) is None:
                db.add(
                    User(
                        email=email,
                        role="admin",
                        password_hash=hash_password(s.admin_password.get_secret_value()),
                    )
                )
                db.commit()
                log.info("created bootstrap admin account")
    except Exception:  # DB may not be migrated yet (e.g. tests); never block startup
        log.warning("admin bootstrap skipped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_admin()
    task = None
    if get_settings().background_jobs_enabled:
        task = asyncio.create_task(run_periodically(_session_factory()))
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    docs = not settings.is_production  # OpenAPI docs disabled in production (SPEC section 7)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Session-Token"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith(settings.api_prefix):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response

    for r in (health, questionnaires, sessions, results, auth, me, clinician, admin):
        app.include_router(r.router, prefix=settings.api_prefix)
    return app


app = create_app()
