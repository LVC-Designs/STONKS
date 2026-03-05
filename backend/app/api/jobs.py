import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.job import JobRunOut, JobStatusOut, JobTriggerResponse
from app.services.job_service import get_job_runs, get_scheduler_status, trigger_job

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[JobRunOut])
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await get_job_runs(db, limit)


@router.get("/status", response_model=JobStatusOut)
async def get_status():
    return await get_scheduler_status()


@router.post("/{job_name}/trigger", response_model=JobTriggerResponse)
async def trigger_job_endpoint(
    job_name: str,
    db: AsyncSession = Depends(get_db),
):
    valid_jobs = ["daily_refresh", "hourly_refresh", "outcome_tracker"]
    if job_name not in valid_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid job name. Must be one of: {valid_jobs}",
        )
    return await trigger_job(db, job_name)


@router.post("/backfill-names")
async def backfill_ticker_names(db: AsyncSession = Depends(get_db)):
    """Backfill actual company names from Polygon.io for tickers where name == symbol."""
    from app.adapters.polygon_adapter import PolygonAdapter
    from app.models.ticker import Ticker
    from sqlalchemy import select

    adapter = PolygonAdapter()
    try:
        polygon_tickers = await adapter.list_tickers("US")
    finally:
        await adapter.close()

    name_map = {t.symbol: t.name for t in polygon_tickers if t.name}

    result = await db.execute(
        select(Ticker).where(
            (Ticker.name == Ticker.symbol) | (Ticker.name.is_(None))
        )
    )
    tickers = list(result.scalars().all())

    updated = 0
    for ticker in tickers:
        real_name = name_map.get(ticker.symbol)
        if real_name and real_name != ticker.symbol:
            ticker.name = real_name
            updated += 1

    await db.commit()
    logger.info(f"Backfilled {updated} ticker names from Polygon")
    return {"updated": updated, "total_checked": len(tickers)}
