from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.paper import Paper


class PaperService:
    """Encapsulates paper-related business logic.

    Routes stay thin and only handle HTTP concerns; services own the actual
    logic and are the layer that will grow to include literature search,
    summarization, and comparison once those features are built.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_papers(self) -> list[Paper]:
        result = await self.db.execute(select(Paper))
        return list(result.scalars().all())
