from fastapi import APIRouter

from api.routes import analysis, comparison, export, health, papers

# Single aggregation point for all versioned routes. main.py mounts this
# once under settings.API_V1_PREFIX, so adding a new resource only means
# adding a router here rather than touching main.py.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(papers.router)
api_router.include_router(analysis.router)
api_router.include_router(comparison.router)
api_router.include_router(export.router)
