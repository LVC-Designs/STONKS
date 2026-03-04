import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobRun
from app.schemas.job import JobRunOut, JobStatusOut, JobTriggerResponse

logger = logging.getLogger(__name__)


async def get_job_runs(db: AsyncSession, limit: int = 20) -> list[JobRun]:
    result = await db.execute(
        select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_scheduler_status() -> JobStatusOut:
    from app.jobs.scheduler import scheduler
    running = scheduler.running if scheduler else False
    next_runs = {}
    if scheduler and running:
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            next_runs[job.id] = next_run.isoformat() if next_run else None
    return JobStatusOut(scheduler_running=running, next_runs=next_runs)


async def create_job_run(db: AsyncSession, job_name: str) -> JobRun:
    job_run = JobRun(
        job_name=job_name,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)
    return job_run


async def complete_job_run(
    db: AsyncSession,
    job_run: JobRun,
    status: str = "success",
    tickers_processed: int = 0,
    errors: list | None = None,
    summary: dict | None = None,
):
    job_run.status = status
    job_run.finished_at = datetime.now(timezone.utc)
    job_run.tickers_processed = tickers_processed
    job_run.errors = errors
    job_run.summary = summary
    await db.commit()


async def trigger_job(db: AsyncSession, job_name: str) -> JobTriggerResponse:
    """Trigger a job to run in the background."""
    job_run = await create_job_run(db, job_name)

    # Launch the job in the background
    from app.jobs.daily_refresh import run_daily_refresh
    from app.jobs.hourly_refresh import run_hourly_refresh
    from app.jobs.outcome_tracker import run_outcome_tracker

    job_map = {
        "daily_refresh": run_daily_refresh,
        "hourly_refresh": run_hourly_refresh,
        "outcome_tracker": run_outcome_tracker,
    }

    job_fn = job_map.get(job_name)
    if job_fn:
        asyncio.create_task(job_fn(job_run.id))

    return JobTriggerResponse(job_run_id=job_run.id, status="started")
