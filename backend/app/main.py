import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_papers, routes_search
from app.core.config import settings
from app.db.database import init_db

logger = logging.getLogger(__name__)

# Without an explicit handler, Python's own "handler of last resort" only
# ever surfaces WARNING+ records (regardless of a logger's own level), so
# any app-level logger.info(...) call (e.g. ai_service logging which
# Gemini API key source was used for a call) would silently vanish. This
# configures only the "app" logger namespace - not the root logger - so
# uvicorn's own access/error logs (which already have their own handlers
# and would otherwise double-print if routed through root too) are
# untouched.
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="BLIP - Battery Literature Intelligence Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # "null" is the Origin Chromium sends for file:// pages - i.e. the
    # packaged Electron app's renderer. settings.frontend_origin covers the
    # Vite dev server (http://localhost:5173) instead.
    allow_origins=[settings.frontend_origin, "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_search.router)
app.include_router(routes_papers.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "입력값을 확인해주세요. (소재는 필수 입력 항목입니다.)"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """A raw unhandled exception (e.g. a DB integrity error) would otherwise
    be caught by Starlette's outermost ServerErrorMiddleware, which sits
    OUTSIDE CORSMiddleware - its fallback response never gets a CORS
    header, so the browser blocks reading it and reports a generic "Failed
    to fetch" instead of the actual error. Handling it here, inside
    FastAPI's own exception-handler dispatch, keeps the response subject
    to CORSMiddleware like any normal response. The traceback is still
    logged so the real cause is diagnosable from the server console/log.
    """

    logger.exception("Unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
