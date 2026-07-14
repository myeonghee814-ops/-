import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import make_asgi_app

from api.router import api_router
from api.routes import search as search_routes
from core.config import get_settings
from core.http_clients import aclose_all
from core.logging import setup_logging
from core.middleware import RequestContextMiddleware

settings = get_settings()
setup_logging(settings.LOG_LEVEL, settings.LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s [%s]", settings.APP_NAME, settings.APP_ENV)
    yield
    await aclose_all()
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Middleware order matters: Starlette applies them outside-in on the way
# in and inside-out on the way out, so RequestContextMiddleware (added
# last) wraps everything else and its request ID + duration cover the
# whole stack, including CORS/GZip handling.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Compresses responses over 500 bytes (the default) -- meaningfully shrinks
# the larger JSON payloads (search results, AI analysis/comparison) this
# API returns, at negligible CPU cost.
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Search is exposed unversioned at /api/search (rather than /api/v1/search)
# per its spec; every other resource stays under the versioned prefix above.
app.include_router(search_routes.router, prefix="/api")

# Prometheus scrape target. Mounted as a plain ASGI app (not a router) so it
# has no coupling to FastAPI/Starlette's request/response cycle beyond the
# raw ASGI interface -- see core/metrics.py for why that matters here.
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": f"{settings.APP_NAME} is running"}
