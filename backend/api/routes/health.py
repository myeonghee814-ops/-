from fastapi import APIRouter

from core.config import get_settings
from schemas.common import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe used by Docker/monitoring and the frontend connectivity check."""
    return HealthResponse(status="ok", app_name=settings.APP_NAME, environment=settings.APP_ENV)
