import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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


def _frontend_dist_dir() -> Path | None:
    """Locate the built frontend (frontend/dist), if present.

    Only ever set in the desktop-packaged build (see desktop-app/). In
    normal dev/prod deployments (uvicorn from source, or the
    nginx-fronted Docker image) this is always None and the plain JSON
    root route below is used instead, unchanged.

    Resolution order:
    1. BLIP_FRONTEND_DIST env var -- what desktop-app/src-tauri/src/main.rs
       actually sets when it spawns this as a sidecar, pointing at
       wherever Tauri's bundler placed the resource files. Explicit and
       correct regardless of the installer format (MSI/NSIS/portable).
    2. <this binary's directory>/frontend_dist -- convenience fallback
       for manually testing the frozen exe outside Tauri (see
       desktop-app/README.md), not used by the packaged app itself.
    3. frontend/dist relative to this source file -- lets a locally
       built frontend be served by `uvicorn main:app` from source too,
       without needing a frozen build at all.
    """
    candidates = []
    env_override = os.environ.get("BLIP_FRONTEND_DIST")
    if env_override:
        candidates.append(Path(env_override))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "frontend_dist")
    candidates.append(Path(__file__).resolve().parent.parent / "frontend" / "dist")

    return next((c for c in candidates if c.is_dir()), None)


_frontend_dist = _frontend_dist_dir()

if _frontend_dist is not None:
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")

    # Registered after every API router above, so it only ever catches
    # paths none of them matched: static files from dist/ (e.g.
    # favicon.ico) and client-side React Router routes (e.g. /paper/123),
    # which all resolve to the same index.html for the SPA to handle.
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str) -> FileResponse:
        candidate = _frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")
else:

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"message": f"{settings.APP_NAME} is running"}
