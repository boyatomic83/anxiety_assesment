from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db import check_database
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    db_ok = await run_in_threadpool(check_database)
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
        database="ok" if db_ok else "unavailable",
    )
