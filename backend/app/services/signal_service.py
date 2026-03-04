import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.scoring.scorer import compute_signal
from app.services.ohlcv_service import get_ohlcv_dataframe
from app.services.indicator_service import get_indicators_for_ticker
from app.config import settings

logger = logging.getLogger(__name__)


async def get_signals_for_ticker(
    db: AsyncSession,
    ticker_id: int,
    limit: int = 1,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Get signals from database."""
    query = select(Signal).where(Signal.ticker_id == ticker_id)
    if start:
        query = query.where(Signal.signal_date >= start)
    if end:
        query = query.where(Signal.signal_date <= end)
    query = query.order_by(Signal.signal_date.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    signals = []
    for r in rows:
        d = {c.name: getattr(r, c.name) for c in Signal.__table__.columns}
        for k, v in d.items():
            if hasattr(v, "is_finite"):
                d[k] = float(v) if v is not None else None
        del d["id"]
        del d["ticker_id"]
        del d["computed_at"]
        if d.get("signal_date"):
            d["signal_date"] = d["signal_date"].isoformat()
        if d.get("outcome_date"):
            d["outcome_date"] = d["outcome_date"].isoformat()
        signals.append(d)

    return signals


async def compute_and_store_signal(
    db: AsyncSession, ticker_id: int, signal_date: date
) -> dict | None:
    """Compute signal score for a ticker and store in the database."""
    # Get indicators
    indicators_list = await get_indicators_for_ticker(db, ticker_id, limit=1)
    if not indicators_list:
        logger.warning(f"No indicators for ticker_id={ticker_id}")
        return None

    indicators = indicators_list[0]

    # Get OHLCV dataframe for structure analysis
    df = await get_ohlcv_dataframe(db, ticker_id)
    if df.empty or len(df) < 20:
        logger.warning(f"Insufficient OHLCV data for ticker_id={ticker_id}")
        return None

    # Compute signal
    result = compute_signal(indicators, df)

    # Build values for storage
    store_values = {
        "score": result.score,
        "regime": result.regime,
        "trend_score": result.trend_score,
        "momentum_score": result.momentum_score,
        "volume_score": result.volume_score,
        "volatility_score": result.volatility_score,
        "structure_score": result.structure_score,
        "reasons": result.reasons,
        "invalidation": result.invalidation,
        "target_pct": settings.SIGNAL_TARGET_PCT,
        "target_days": settings.SIGNAL_TARGET_DAYS,
        "max_drawdown_pct": settings.SIGNAL_MAX_DRAWDOWN_PCT,
        "outcome": "pending",
    }

    # SQLite-compatible upsert: check if row exists, then update or insert
    existing = await db.execute(
        select(Signal.id).where(
            Signal.ticker_id == ticker_id,
            Signal.signal_date == signal_date,
        )
    )
    row_id = existing.scalar_one_or_none()

    if row_id is not None:
        await db.execute(
            update(Signal).where(Signal.id == row_id).values(**store_values)
        )
    else:
        db.add(Signal(ticker_id=ticker_id, signal_date=signal_date, **store_values))

    await db.commit()

    logger.info(f"Signal for ticker_id={ticker_id}: score={result.score}, regime={result.regime}")
    return {**store_values, "ticker_id": ticker_id, "signal_date": signal_date}
