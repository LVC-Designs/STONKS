from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ticker_service import get_ticker_by_symbol
from app.services.ohlcv_service import get_ohlcv_bars
from app.services.indicator_service import get_indicators_for_ticker
from app.services.signal_service import get_signals_for_ticker
from app.services.news_service import get_news_for_ticker

router = APIRouter()


@router.get("/{symbol}")
async def get_ticker(symbol: str, db: AsyncSession = Depends(get_db)):
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    signals = await get_signals_for_ticker(db, ticker.id, limit=1)
    indicators = await get_indicators_for_ticker(db, ticker.id, limit=1)

    return {
        "ticker": ticker,
        "latest_signal": signals[0] if signals else None,
        "latest_indicators": indicators[0] if indicators else None,
    }


@router.get("/{symbol}/ohlcv")
async def get_ticker_ohlcv(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    if not start:
        start = date.today() - timedelta(days=365)
    if not end:
        end = date.today()

    bars = await get_ohlcv_bars(db, ticker.id, start, end)
    return {"bars": bars, "ticker": symbol.upper()}


@router.get("/{symbol}/indicators")
async def get_ticker_indicators(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(1, ge=1, le=252),
    db: AsyncSession = Depends(get_db),
):
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    indicators = await get_indicators_for_ticker(db, ticker.id, limit=limit, start=start, end=end)
    return indicators


@router.get("/{symbol}/signals")
async def get_ticker_signals(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(1, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    signals = await get_signals_for_ticker(db, ticker.id, limit=limit, start=start, end=end)
    return signals


@router.get("/{symbol}/news")
async def get_ticker_news(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    news = await get_news_for_ticker(db, ticker.id, limit=limit, start=start, end=end)
    return news
