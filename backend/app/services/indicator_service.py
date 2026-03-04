import logging
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator import ComputedIndicator
from app.indicators.compute_all import compute_all_indicators
from app.services.ohlcv_service import get_ohlcv_dataframe

logger = logging.getLogger(__name__)


async def get_indicators_for_ticker(
    db: AsyncSession,
    ticker_id: int,
    limit: int = 1,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Get computed indicators from database."""
    query = select(ComputedIndicator).where(ComputedIndicator.ticker_id == ticker_id)
    if start:
        query = query.where(ComputedIndicator.trade_date >= start)
    if end:
        query = query.where(ComputedIndicator.trade_date <= end)
    query = query.order_by(ComputedIndicator.trade_date.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    indicators_list = []
    for r in rows:
        d = {c.name: getattr(r, c.name) for c in ComputedIndicator.__table__.columns}
        # Convert Decimal to float for JSON serialization
        for k, v in d.items():
            if hasattr(v, "is_finite"):
                d[k] = float(v) if v is not None else None
        del d["id"]
        del d["ticker_id"]
        del d["computed_at"]
        if d.get("trade_date"):
            d["trade_date"] = d["trade_date"].isoformat()
        indicators_list.append(d)

    return indicators_list


async def compute_and_store_indicators(
    db: AsyncSession, ticker_id: int, trade_date: date
) -> dict | None:
    """Compute all indicators for a ticker and store in the database."""
    df = await get_ohlcv_dataframe(db, ticker_id)

    if df.empty or len(df) < 50:
        logger.warning(f"Insufficient data for ticker_id={ticker_id} ({len(df)} bars)")
        return None

    indicators = compute_all_indicators(df)

    if not indicators:
        return None

    # Build values dict, filtering None keys
    values = {}
    for key, val in indicators.items():
        if val is not None:
            values[key] = val

    # SQLite-compatible upsert: check if row exists, then update or insert
    existing = await db.execute(
        select(ComputedIndicator.id).where(
            ComputedIndicator.ticker_id == ticker_id,
            ComputedIndicator.trade_date == trade_date,
        )
    )
    row_id = existing.scalar_one_or_none()

    if row_id is not None:
        await db.execute(
            update(ComputedIndicator)
            .where(ComputedIndicator.id == row_id)
            .values(**values)
        )
    else:
        db.add(ComputedIndicator(ticker_id=ticker_id, trade_date=trade_date, **values))

    await db.commit()

    logger.info(f"Computed indicators for ticker_id={ticker_id} on {trade_date}")
    return indicators
