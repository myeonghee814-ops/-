from fastapi import APIRouter

from api.deps import DBSession
from schemas.paper import PaperRead
from services.paper_service import PaperService

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/", response_model=list[PaperRead])
async def list_papers(db: DBSession) -> list[PaperRead]:
    """List stored papers.

    Returns an empty list for now — literature search/ingestion is not
    implemented yet. This endpoint exists to prove out the
    route -> service -> model wiring end to end.
    """
    return await PaperService(db).list_papers()
