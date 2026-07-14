import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

from api.deps import DBSession
from core.config import get_settings
from schemas.common import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe: is the process up and serving requests at all?
    Deliberately has no dependencies (no DB, no external calls) so it can't
    report unhealthy for reasons outside the process's own control."""
    return HealthResponse(status="ok", app_name=settings.APP_NAME, environment=settings.APP_ENV)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(db: DBSession, response: Response) -> ReadinessResponse:
    """Readiness probe: can this instance actually serve traffic right now?
    Checks DB connectivity, since that's the one dependency every request
    that touches persistence needs. Used by orchestrators (Docker Compose
    healthcheck, Kubernetes readinessProbe) to gate traffic/restarts —
    distinct from /health, which should stay up even if the DB is briefly
    unreachable."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        response.status_code = 503
        return ReadinessResponse(status="unavailable", database="unreachable")

    return ReadinessResponse(status="ok", database="reachable")
