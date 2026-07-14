import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from schemas.export import ExportRequest
from services.export_service import generate_export

router = APIRouter(prefix="/export", tags=["export"])


@router.post("")
async def export_papers(request: ExportRequest) -> StreamingResponse:
    workbook_bytes = await generate_export(request.papers)
    return StreamingResponse(
        io.BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="blip-papers-export.xlsx"'},
    )
