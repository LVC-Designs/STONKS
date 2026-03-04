import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def start_scheduler():
    """Start the APScheduler with configured jobs."""
    from app.jobs.daily_refresh import daily_refresh_job
    from app.jobs.hourly_refresh import hourly_refresh_job

    # Daily refresh: weekdays at 6 PM ET (after market close)
    scheduler.add_job(
        daily_refresh_job,
        CronTrigger.from_crontab("0 18 * * 1-5"),
        id="daily_refresh",
        replace_existing=True,
    )

    # Hourly refresh for liquid tickers
    scheduler.add_job(
        hourly_refresh_job,
        IntervalTrigger(hours=1),
        id="hourly_refresh",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with daily and hourly jobs")


async def stop_scheduler():
    """Shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
