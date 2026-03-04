"""Hourly refresh job: refresh top liquid tickers only."""

import logging
from datetime import date

from sqlalchemy import select, desc

from app.database import async_session_factory
from app.models.signal import Signal
from app.models.ticker import Ticker
from app.services.ohlcv_service import refresh_ohlcv
from app.services.indicator_service import compute_and_store_indicators
from app.services.signal_service import compute_and_store_signal
from app.services.job_service import create_job_run, complete_job_run

logger = logging.getLogger(__name__)

TOP_N = 100  # Refresh top 100 tickers by score


async def hourly_refresh_job():
    """Entry point for the scheduled hourly refresh."""
    async with async_session_factory() as db:
        job_run = await create_job_run(db, "hourly_refresh")
    await run_hourly_refresh(job_run.id)


async def run_hourly_refresh(job_run_id: int):
    """Refresh OHLCV and recompute signals for top-scoring tickers."""
    errors = []
    tickers_processed = 0

    try:
        async with async_session_factory() as db:
            today = date.today()

            # Get top N tickers by latest signal score
            result = await db.execute(
                select(Ticker)
                .join(Signal, Signal.ticker_id == Ticker.id)
                .where(Ticker.active == True)
                .order_by(desc(Signal.score))
                .limit(TOP_N)
            )
            tickers = list(result.scalars().all())
            logger.info(f"Hourly refresh: {len(tickers)} tickers")

            for ticker in tickers:
                try:
                    await refresh_ohlcv(db, ticker.id, ticker.symbol)
                    indicators = await compute_and_store_indicators(db, ticker.id, today)
                    if indicators:
                        await compute_and_store_signal(db, ticker.id, today)
                    tickers_processed += 1
                except Exception as e:
                    errors.append({"ticker": ticker.symbol, "error": str(e)})

            from app.models.job import JobRun
            job_run_db = await db.get(JobRun, job_run_id)
            if job_run_db:
                await complete_job_run(
                    db, job_run_db,
                    status="success" if not errors else "completed_with_errors",
                    tickers_processed=tickers_processed,
                    errors=errors if errors else None,
                )

    except Exception as e:
        logger.error(f"Hourly refresh failed: {str(e)}")

    logger.info(f"Hourly refresh complete: {tickers_processed} tickers")
