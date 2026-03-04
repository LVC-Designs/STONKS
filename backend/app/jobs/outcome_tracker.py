"""Outcome tracker: check pending signals for success/failure."""

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.signal import Signal
from app.models.ohlcv import OHLCVDaily
from app.services.job_service import create_job_run, complete_job_run

logger = logging.getLogger(__name__)


async def run_outcome_tracker(job_run_id: int):
    """Check pending signals and determine if they hit their target."""
    processed = 0
    errors = []

    try:
        async with async_session_factory() as db:
            # Get pending signals that are past their target window
            result = await db.execute(
                select(Signal)
                .where(Signal.outcome == "pending")
                .order_by(Signal.signal_date.asc())
            )
            pending_signals = list(result.scalars().all())

            for signal in pending_signals:
                try:
                    await _evaluate_signal(db, signal)
                    processed += 1
                except Exception as e:
                    errors.append({"signal_id": signal.id, "error": str(e)})

            await db.commit()

            from app.models.job import JobRun
            job_run_db = await db.get(JobRun, job_run_id)
            if job_run_db:
                await complete_job_run(
                    db, job_run_db,
                    status="success",
                    tickers_processed=processed,
                    errors=errors if errors else None,
                )

    except Exception as e:
        logger.error(f"Outcome tracker failed: {str(e)}")


async def _evaluate_signal(db: AsyncSession, signal: Signal):
    """Evaluate a single signal against the prediction target."""
    target_pct = float(signal.target_pct) if signal.target_pct else 5.0
    target_days = signal.target_days or 20
    max_dd_pct = float(signal.max_drawdown_pct) if signal.max_drawdown_pct else -3.0

    today = date.today()
    signal_end = signal.signal_date + timedelta(days=int(target_days * 1.5))

    # Not enough time has passed
    if today < signal.signal_date + timedelta(days=target_days):
        return

    # Get OHLCV from signal date to end of target window
    result = await db.execute(
        select(OHLCVDaily)
        .where(
            OHLCVDaily.ticker_id == signal.ticker_id,
            OHLCVDaily.trade_date > signal.signal_date,
            OHLCVDaily.trade_date <= signal_end,
        )
        .order_by(OHLCVDaily.trade_date.asc())
    )
    bars = list(result.scalars().all())

    if not bars:
        return

    # Get entry price (close on signal date)
    entry_result = await db.execute(
        select(OHLCVDaily)
        .where(
            OHLCVDaily.ticker_id == signal.ticker_id,
            OHLCVDaily.trade_date == signal.signal_date,
        )
    )
    entry_bar = entry_result.scalar_one_or_none()
    if not entry_bar or not entry_bar.close:
        return

    entry_price = float(entry_bar.close)

    # Track max drawdown and returns
    max_drawdown = 0.0
    peak = entry_price
    target_hit = False
    days_to_target = None

    for i, bar in enumerate(bars):
        if not bar.close:
            continue
        price = float(bar.close)
        low = float(bar.low) if bar.low else price

        # Update peak and drawdown
        if price > peak:
            peak = price
        dd = (low - peak) / peak * 100
        if dd < max_drawdown:
            max_drawdown = dd

        # Check if target hit
        return_pct = (price - entry_price) / entry_price * 100
        if return_pct >= target_pct and max_drawdown >= max_dd_pct:
            target_hit = True
            days_to_target = i + 1
            break

    # Final return (at end of window if target not hit)
    final_price = float(bars[-1].close) if bars[-1].close else entry_price
    actual_return = (final_price - entry_price) / entry_price * 100

    # Determine outcome
    if target_hit:
        signal.outcome = "success"
    elif max_drawdown < max_dd_pct:
        signal.outcome = "failure"  # Stopped out by drawdown
    else:
        signal.outcome = "expired"  # Time expired without hitting target

    signal.actual_return = round(actual_return, 4)
    signal.actual_max_dd = round(max_drawdown, 4)
    signal.days_to_target = days_to_target
    signal.outcome_date = today

    logger.info(
        f"Signal {signal.id}: {signal.outcome} "
        f"(return={actual_return:.2f}%, drawdown={max_drawdown:.2f}%)"
    )
