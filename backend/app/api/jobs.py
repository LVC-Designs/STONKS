from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.job import JobRunOut, JobStatusOut, JobTriggerResponse
from app.services.job_service import get_job_runs, get_scheduler_status, trigger_job

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
