import logging
from typing import AsyncIterator

from sqlalchemy import select, func, desc, asc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticker import Ticker
from app.models.signal import Signal
from app.models.ohlcv import OHLCVDaily
from app.models.indicator import ComputedIndicator
from app.schemas.ticker import ScreenerResponse, ScreenerRow
from app.utils.csv_export import rows_to_csv_stream

logger = logging.getLogger(__name__)

SORT_COLUMNS = {
    "score": Signal.score,
    "symbol": Ticker.symbol,
    "name": Ticker.name,
    "exchange": Ticker.exchange,
    "trend_score": Signal.trend_score,
    "momentum_score": Signal.momentum_score,
    "volume_score": Signal.volume_score,
    "volatility_score": Signal.volatility_score,
    "structure_score": Signal.structure_score,
}


async def get_screener_data(
    db: AsyncSession,
    exchange_group: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    min_volume: int | None = None,
    regime: str | None = None,
    sort_by: str = "score",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> ScreenerResponse:
    """Build the screener query with filters, sorting, and pagination."""
    # Subquery: get the latest signal date per ticker
    latest_signal_sq = (
        select(Signal.ticker_id, func.max(Signal.signal_date).label("max_date"))
        .group_by(Signal.ticker_id)
        .subquery()
    )

    # Main query joining tickers, their latest signal, and latest OHLCV
    query = (
        select(
            Ticker.symbol,
            Ticker.name,
            Ticker.exchange,
            Ticker.exchange_group,
            Signal.score,
            Signal.regime,
            Signal.signal_date,
            Signal.trend_score,
            Signal.momentum_score,
            Signal.volume_score,
            Signal.volatility_score,
            Signal.structure_score,
        )
        .join(latest_signal_sq, Ticker.id == latest_signal_sq.c.ticker_id)
        .join(
            Signal,
            and_(
                Signal.ticker_id == Ticker.id,
                Signal.signal_date == latest_signal_sq.c.max_date,
            ),
        )
        .where(Ticker.active == True)
    )

    # Apply filters
    if exchange_group:
        query = query.where(Ticker.exchange_group == exchange_group.upper())
    if min_score is not None:
        query = query.where(Signal.score >= min_score)
    if max_score is not None:
        query = query.where(Signal.score <= max_score)
    if regime:
        query = query.where(Signal.regime == regime)

    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting
    sort_col = SORT_COLUMNS.get(sort_by, Signal.score)
    order_fn = desc if sort_dir == "desc" else asc
    query = query.order_by(order_fn(sort_col))

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        items.append(ScreenerRow(
            symbol=row.symbol,
            name=row.name,
            exchange=row.exchange,
            exchange_group=row.exchange_group,
            score=float(row.score) if row.score else None,
            regime=row.regime,
            signal_date=row.signal_date.isoformat() if row.signal_date else None,
            trend_score=float(row.trend_score) if row.trend_score else None,
            momentum_score=float(row.momentum_score) if row.momentum_score else None,
            volume_score=float(row.volume_score) if row.volume_score else None,
            volatility_score=float(row.volatility_score) if row.volatility_score else None,
            structure_score=float(row.structure_score) if row.structure_score else None,
        ))

    return ScreenerResponse(items=items, total=total, page=page, page_size=page_size)


async def export_screener_csv(
    db: AsyncSession,
    exchange_group: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    min_volume: int | None = None,
    regime: str | None = None,
    sort_by: str = "score",
    sort_dir: str = "desc",
) -> AsyncIterator[str]:
    """Export screener data as CSV."""
    # Get all data (no pagination for export)
    response = await get_screener_data(
        db=db,
        exchange_group=exchange_group,
        min_score=min_score,
        max_score=max_score,
        min_volume=min_volume,
        regime=regime,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=1,
        page_size=10000,
    )

    headers = [
        "symbol", "name", "exchange", "exchange_group", "score", "regime",
        "signal_date", "trend_score", "momentum_score", "volume_score",
        "volatility_score", "structure_score",
    ]

    rows = [item.model_dump() for item in response.items]
    return rows_to_csv_stream(headers, rows)
