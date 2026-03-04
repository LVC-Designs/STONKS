"""Daily refresh job: universe snapshot, OHLCV, indicators, signals, news."""

import logging
from datetime import date

from app.database import async_session_factory
from app.services.ticker_service import get_all_active_tickers, snapshot_universe
from app.services.ohlcv_service import refresh_ohlcv
from app.services.indicator_service import compute_and_store_indicators
from app.services.signal_service import compute_and_store_signal
from app.services.news_service import refresh_news
from app.services.job_service import create_job_run, complete_job_run

logger = logging.getLogger(__name__)


async def daily_refresh_job():
    """Entry point for the scheduled daily refresh."""
    async with async_session_factory() as db:
        job_run = await create_job_run(db, "daily_refresh")
    await run_daily_refresh(job_run.id)


async def run_daily_refresh(job_run_id: int):
    """Run the full daily refresh pipeline."""
    errors = []
    tickers_processed = 0

    try:
        async with async_session_factory() as db:
            today = date.today()

            # Step 1: Snapshot universe (survivorship bias prevention)
            logger.info("Step 1: Snapshotting universe...")
            await snapshot_universe(db, today)

            # Step 2-5: Process each ticker
            tickers = await get_all_active_tickers(db)
            logger.info(f"Processing {len(tickers)} active tickers...")

            for ticker in tickers:
                try:
                    # Step 2: Refresh OHLCV
                    await refresh_ohlcv(db, ticker.id, ticker.symbol)

                    # Step 3: Compute indicators
                    indicators = await compute_and_store_indicators(db, ticker.id, today)

                    # Step 4: Compute signal
                    if indicators:
                        await compute_and_store_signal(db, ticker.id, today)

                    # Step 5: Refresh news
                    await refresh_news(db, ticker.id, ticker.symbol)

                    tickers_processed += 1

                except Exception as e:
                    error_msg = f"Error processing {ticker.symbol}: {str(e)}"
                    logger.error(error_msg)
                    errors.append({"ticker": ticker.symbol, "error": str(e)})

            # Complete job run
            from app.models.job import JobRun
            job_run_db = await db.get(JobRun, job_run_id)
            if job_run_db:
                await complete_job_run(
                    db,
                    job_run_db,
                    status="success" if not errors else "completed_with_errors",
                    tickers_processed=tickers_processed,
                    errors=errors if errors else None,
                    summary={"total_tickers": len(tickers), "processed": tickers_processed},
                )

    except Exception as e:
        logger.error(f"Daily refresh failed: {str(e)}")
        try:
            async with async_session_factory() as db:
                from app.models.job import JobRun
                job_run_db = await db.get(JobRun, job_run_id)
                if job_run_db:
                    await complete_job_run(
                        db, job_run_db, status="failed",
                        tickers_processed=tickers_processed,
                        errors=[{"error": str(e)}],
                    )
        except Exception:
            logger.error("Failed to update job run status")

    logger.info(f"Daily refresh complete: {tickers_processed} tickers, {len(errors)} errors")
