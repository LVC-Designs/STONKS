import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCVDaily
from app.adapters.registry import get_market_adapter

logger = logging.getLogger(__name__)


async def get_ohlcv_bars(
    db: AsyncSession, ticker_id: int, start: date, end: date
) -> list[dict]:
    """Get OHLCV bars from database."""
    result = await db.execute(
        select(OHLCVDaily)
        .where(
            OHLCVDaily.ticker_id == ticker_id,
            OHLCVDaily.trade_date >= start,
            OHLCVDaily.trade_date <= end,
        )
        .order_by(OHLCVDaily.trade_date.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "date": r.trade_date.isoformat(),
            "open": float(r.open) if r.open else 0,
            "high": float(r.high) if r.high else 0,
            "low": float(r.low) if r.low else 0,
            "close": float(r.close) if r.close else 0,
            "volume": int(r.volume) if r.volume else 0,
            "vwap": float(r.vwap) if r.vwap else None,
        }
        for r in rows
    ]


async def get_ohlcv_dataframe(
    db: AsyncSession, ticker_id: int, min_bars: int = 300
) -> pd.DataFrame:
    """Get OHLCV data as a pandas DataFrame for indicator computation."""
    result = await db.execute(
        select(OHLCVDaily)
        .where(OHLCVDaily.ticker_id == ticker_id)
        .order_by(OHLCVDaily.trade_date.asc())
    )
    rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    data = [
        {
            "date": r.trade_date,
            "open": float(r.open) if r.open else 0,
            "high": float(r.high) if r.high else 0,
            "low": float(r.low) if r.low else 0,
            "close": float(r.close) if r.close else 0,
            "volume": int(r.volume) if r.volume else 0,
        }
        for r in rows
    ]

    df = pd.DataFrame(data)
    df.set_index("date", inplace=True)
    return df


async def get_last_cached_date(db: AsyncSession, ticker_id: int) -> date | None:
    """Get the most recent cached OHLCV date for a ticker."""
    result = await db.execute(
        select(OHLCVDaily.trade_date)
        .where(OHLCVDaily.ticker_id == ticker_id)
        .order_by(OHLCVDaily.trade_date.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def refresh_ohlcv(db: AsyncSession, ticker_id: int, symbol: str) -> int:
    """Fetch missing OHLCV data from the market adapter and cache it."""
    adapter = get_market_adapter()

    last_date = await get_last_cached_date(db, ticker_id)
    start = last_date + timedelta(days=1) if last_date else date.today() - timedelta(days=365 * 2)
    end = date.today()

    if start > end:
        return 0

    bars = await adapter.get_ohlcv(symbol, "day", start, end)

    count = 0
    for bar in bars:
        # Check if bar already exists (SQLite-compatible upsert)
        existing = await db.execute(
            select(OHLCVDaily.id).where(
                OHLCVDaily.ticker_id == ticker_id,
                OHLCVDaily.trade_date == bar.date,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(OHLCVDaily(
            ticker_id=ticker_id,
            trade_date=bar.date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            vwap=bar.vwap,
            source="polygon",
        ))
        count += 1

    await db.commit()
    logger.info(f"Cached {count} bars for {symbol}")
    return count
