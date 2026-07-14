from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings

settings = get_settings()

# `echo=settings.DEBUG` surfaces generated SQL in logs during local development
# without needing a code change before shipping to production.
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped async database session."""
    async with AsyncSessionLocal() as session:
        yield session
