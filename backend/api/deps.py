from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db

# Shared dependency alias so route signatures stay short:
# async def handler(db: DBSession): ...
DBSession = Annotated[AsyncSession, Depends(get_db)]
