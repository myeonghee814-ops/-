import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import to_paper_card
from app.db.database import get_db
from app.db.models import SearchQuery
from app.schemas.search import SearchRequest, SearchResponse
from app.services import battery_term_mapping
from app.services.search_pipeline import run_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def create_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    x_gemini_api_key: str | None = Header(default=None, alias="X-Gemini-Api-Key"),
) -> SearchResponse:
    # Typo correction runs unconditionally, before Gemini is even called -
    # a cleaned-up material name benefits a successful Gemini call too,
    # not just the dictionary fallback in battery_term_mapping.
    material, material_notice, material_notice_level = battery_term_mapping.correct_material_typos(
        request.material
    )
    try:
        search_query, ai_degraded = await run_search(
            db,
            material,
            x_gemini_api_key,
            material_notice=material_notice or "",
            material_notice_level=material_notice_level or "",
            performance=request.performance,
            additive_or_solvent=request.additive_or_solvent,
            sort_by=request.sort_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=502,
                detail="Semantic Scholar 요청 한도 초과. 잠시 후 다시 시도해주세요.",
            ) from exc
        raise HTTPException(
            status_code=502, detail=f"논문 검색 서비스 호출에 실패했습니다: {exc}"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"논문 검색 서비스에 연결할 수 없습니다: {exc}"
        ) from exc

    return SearchResponse(
        search_id=search_query.id,
        keyword=search_query.keyword,
        material=search_query.material,
        material_notice=search_query.material_notice,
        material_notice_level=search_query.material_notice_level or None,
        performance=search_query.performance,
        additive_or_solvent=search_query.additive_or_solvent,
        additive_notice=search_query.additive_notice,
        additive_notice_level=search_query.additive_notice_level or None,
        sort_by=search_query.sort_by,
        expanded_query=search_query.expanded_query,
        results=[to_paper_card(r) for r in search_query.results],
        ai_degraded=ai_degraded,
    )


@router.get("/{search_id}", response_model=SearchResponse)
def get_search(search_id: int, db: Session = Depends(get_db)) -> SearchResponse:
    search_query = db.get(SearchQuery, search_id)
    if search_query is None:
        raise HTTPException(status_code=404, detail="검색 결과를 찾을 수 없습니다.")

    return SearchResponse(
        search_id=search_query.id,
        keyword=search_query.keyword,
        material=search_query.material,
        material_notice=search_query.material_notice,
        material_notice_level=search_query.material_notice_level or None,
        performance=search_query.performance,
        additive_or_solvent=search_query.additive_or_solvent,
        additive_notice=search_query.additive_notice,
        additive_notice_level=search_query.additive_notice_level or None,
        sort_by=search_query.sort_by,
        expanded_query=search_query.expanded_query,
        results=[to_paper_card(r) for r in search_query.results],
        ai_degraded=search_query.ai_degraded,
    )
