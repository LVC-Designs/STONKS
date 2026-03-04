"""News V2 API endpoints.

Endpoints:
  GET  /news         — List articles with filters (ticker, date range, sentiment, sort)
  GET  /news/market  — Backward-compatible market news endpoint
  POST /news/refresh — Trigger quick or full news ingestion
  GET  /news/stats   — Aggregate statistics
  GET  /news/{symbol} — Backward-compatible per-ticker news endpoint
"""

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.news_v2 import (
    NewsRefreshRequest,
    NewsRefreshResponse,
    NewsStatsResponse,
)
from app.services.news_v2_service import (
    compute_news_market_context,
    compute_sentiment_for_new_articles,
    full_ingest_batch,
    get_news_articles,
    get_news_stats,
    quick_refresh,
)
from app.services.ticker_service import get_ticker_by_symbol

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_news(
    ticker: str | None = Query(None, description="Filter by ticker symbol"),
    start: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="End date (YYYY-MM-DD)"),
    sentiment: str | None = Query(None, description="Filter: positive, negative, neutral"),
    min_abs_sentiment: float | None = Query(None, ge=0, le=1, description="Minimum |sentiment_score|"),
    sort: str = Query("newest", description="Sort: newest, oldest, most_positive, most_negative, strongest"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """List news articles with filters, pagination, and sentiment summary."""
    if not start:
        start = date.today() - timedelta(days=7)
    if not end:
        end = date.today()

    offset = (page - 1) * limit
    items, total = await get_news_articles(
        db,
        ticker=ticker,
        start=start,
        end=end,
        sentiment=sentiment,
        min_abs_sentiment=min_abs_sentiment,
        sort_by=sort,
        limit=limit,
        offset=offset,
    )

    # Compute sentiment summary for the filtered set
    stats = await get_news_stats(db, start=start, end=end)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": limit,
        "sentiment_summary": {
            "avg_score": stats.get("avg_sentiment"),
            "positive_count": stats.get("positive_count", 0),
            "negative_count": stats.get("negative_count", 0),
            "neutral_count": stats.get("neutral_count", 0),
        },
    }


# Backward-compatible endpoint — maps to the same query as list_news
@router.get("/market")
async def get_market_news(
    start: date | None = Query(None),
    end: date | None = Query(None),
    sentiment: str | None = Query(None, description="Filter: positive, negative, neutral"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Backward-compatible market news endpoint. Delegates to list_news."""
    if not start:
        start = date.today() - timedelta(days=7)
    if not end:
        end = date.today()

    offset = (page - 1) * limit
    items, total = await get_news_articles(
        db,
        start=start,
        end=end,
        sentiment=sentiment,
        limit=limit,
        offset=offset,
    )

    stats = await get_news_stats(db, start=start, end=end)

    # Transform items to match old response shape (ticker_symbol, ticker_name fields)
    compat_items = []
    for item in items:
        tickers = item.get("tickers", [])
        compat_items.append({
            "id": item["id"],
            "ticker_symbol": tickers[0] if tickers else "",
            "ticker_name": "",
            "headline": item["headline"],
            "summary": item["summary"],
            "url": item["url"],
            "image_url": item["image_url"],
            "source": item["source"],
            "published_at": item["published_at"],
            "category": None,
            "sentiment_score": item["sentiment_score"],
            "sentiment_label": item["sentiment_label"],
        })

    return {
        "items": compat_items,
        "total": total,
        "page": page,
        "page_size": limit,
        "sentiment_summary": {
            "avg_score": stats.get("avg_sentiment"),
            "positive_count": stats.get("positive_count", 0),
            "negative_count": stats.get("negative_count", 0),
            "neutral_count": stats.get("neutral_count", 0),
        },
    }


@router.post("/refresh")
async def refresh_news(
    body: NewsRefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger news ingestion.

    - mode="quick" (default): fetches for top-scoring tickers only, runs inline.
    - mode="full": queues a background job to walk the full universe in batches.
    """
    if body is None:
        body = NewsRefreshRequest()

    if body.mode == "quick":
        result = await quick_refresh(
            limit_tickers=body.limit_tickers,
            max_articles_per_ticker=body.max_articles_per_ticker,
            lookback_days=body.lookback_days,
        )

        # Run sentiment + context computation inline for quick refresh
        await compute_sentiment_for_new_articles()
        await compute_news_market_context()

        return NewsRefreshResponse(
            status="completed",
            mode="quick",
            tickers_processed=result["tickers_processed"],
            articles_stored=result["articles_stored"],
            errors=result["errors"],
        )
    else:
        # Full mode: run in background to avoid HTTP timeout
        async def _background_full_ingest():
            try:
                result = await full_ingest_batch(
                    batch_size=body.limit_tickers,
                    max_articles_per_ticker=body.max_articles_per_ticker,
                    lookback_days=body.lookback_days,
                )
                await compute_sentiment_for_new_articles()
                await compute_news_market_context()
                logger.info(f"Full ingest batch completed: {result}")
            except Exception as e:
                logger.error(f"Full ingest batch failed: {e}")

        asyncio.create_task(_background_full_ingest())

        return NewsRefreshResponse(
            status="started",
            mode="full",
            tickers_queued=body.limit_tickers,
        )


@router.get("/stats")
async def news_stats(
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate news statistics."""
    stats = await get_news_stats(db, start=start, end=end)
    return NewsStatsResponse(**stats)


# Backward-compatible endpoint for ticker detail page
@router.get("/{symbol}")
async def get_ticker_news(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get news for a specific ticker."""
    ticker = await get_ticker_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    if not start:
        start = date.today() - timedelta(days=30)

    items, total = await get_news_articles(
        db,
        ticker=symbol.upper(),
        start=start,
        end=end,
        limit=limit,
        offset=0,
    )

    return items
