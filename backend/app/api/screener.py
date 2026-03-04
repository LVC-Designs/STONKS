from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ticker import ScreenerResponse
from app.services.screener_service import get_screener_data, export_screener_csv

router = APIRouter()


@router.get("", response_model=ScreenerResponse)
async def get_screener(
    exchange_group: str | None = Query(None, description="US, CA, or omit for all"),
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
    min_volume: int | None = Query(None, ge=0),
    regime: str | None = Query(None),
    sort_by: str = Query("score", description="Column to sort by"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await get_screener_data(
        db=db,
        exchange_group=exchange_group,
        min_score=min_score,
        max_score=max_score,
        min_volume=min_volume,
        regime=regime,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_screener(
    exchange_group: str | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
    min_volume: int | None = Query(None, ge=0),
    regime: str | None = Query(None),
    sort_by: str = Query("score"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    csv_stream = await export_screener_csv(
        db=db,
        exchange_group=exchange_group,
        min_score=min_score,
        max_score=max_score,
        min_volume=min_volume,
        regime=regime,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return StreamingResponse(
        csv_stream,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=screener_export.csv"},
    )
