from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for the liveness/health check endpoint."""

    status: str
    app_name: str
    environment: str
