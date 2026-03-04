import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticker import Ticker, TickerUniverseSnapshot
from app.adapters.registry import get_market_adapter

logger = logging.getLogger(__name__)


async def get_ticker_by_symbol(db: AsyncSession, symbol: str) -> Ticker | None:
    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol, Ticker.active == True))
    return result.scalar_one_or_none()


async def get_all_active_tickers(db: AsyncSession) -> list[Ticker]:
    result = await db.execute(select(Ticker).where(Ticker.active == True).order_by(Ticker.symbol))
    return list(result.scalars().all())


async def refresh_ticker_universe(db: AsyncSession, exchange_group: str) -> int:
    """Fetch tickers from the market adapter and upsert into the database."""
    adapter = get_market_adapter()
    tickers = await adapter.list_tickers(exchange_group)

    count = 0
    for t in tickers:
        existing = await db.execute(
            select(Ticker).where(Ticker.symbol == t.symbol, Ticker.exchange == t.exchange)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.name = t.name
            row.active = t.active
            row.country = t.country
            row.currency = t.currency
        else:
            db.add(Ticker(
                symbol=t.symbol, name=t.name, exchange=t.exchange,
                exchange_group=t.exchange_group, country=t.country,
                currency=t.currency, asset_type=t.asset_type,
                is_otc=t.is_otc, is_neo=t.is_neo, active=t.active,
                polygon_ticker=t.symbol, finnhub_ticker=t.symbol,
            ))
        count += 1

    await db.commit()
    logger.info(f"Upserted {count} tickers for {exchange_group}")
    return count


async def snapshot_universe(db: AsyncSession, snapshot_date: date) -> int:
    """Create a snapshot of the current active ticker universe."""
    tickers = await get_all_active_tickers(db)
    count = 0

    for t in tickers:
        existing = await db.execute(
            select(TickerUniverseSnapshot).where(
                TickerUniverseSnapshot.snapshot_date == snapshot_date,
                TickerUniverseSnapshot.ticker_id == t.id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(TickerUniverseSnapshot(
                snapshot_date=snapshot_date, ticker_id=t.id,
                symbol=t.symbol, exchange=t.exchange, active=t.active,
            ))
            count += 1

    await db.commit()
    logger.info(f"Snapshot {count} tickers for {snapshot_date}")
    return count
