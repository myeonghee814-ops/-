import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from core.config import get_settings
from core.logging import setup_logging

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s [%s]", settings.APP_NAME, settings.APP_ENV)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# Origins are read from the CORS_ORIGINS env var so the frontend's dev/prod
# URL never needs a code change to be allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": f"{settings.APP_NAME} is running"}
