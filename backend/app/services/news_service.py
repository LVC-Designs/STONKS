import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsItem
from app.models.ticker import Ticker
from app.adapters.registry import get_news_adapter

logger = logging.getLogger(__name__)


async def get_news_for_ticker(
    db: AsyncSession,
    ticker_id: int,
    limit: int = 20,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """Get news items from database."""
    query = select(NewsItem).where(NewsItem.ticker_id == ticker_id)
    if start:
        query = query.where(NewsItem.published_at >= start)
    if end:
        query = query.where(NewsItem.published_at <= end)
    query = query.order_by(NewsItem.published_at.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.scalars().all()

    news = []
    for r in rows:
        news.append({
            "id": r.id,
            "headline": r.headline,
            "summary": r.summary,
            "url": r.url,
            "image_url": r.image_url,
            "source": r.source,
            "published_at": r.published_at.isoformat() if r.published_at else None,
            "category": r.category,
            "sentiment_score": float(r.sentiment_score) if r.sentiment_score else None,
            "sentiment_label": r.sentiment_label,
        })

    return news


async def refresh_news(db: AsyncSession, ticker_id: int, symbol: str) -> int:
    """Fetch recent news from the news adapter and store."""
    adapter = get_news_adapter()

    today = date.today()
    from_date = today - timedelta(days=7)

    articles = await adapter.get_company_news(symbol, from_date, today)

    count = 0
    for article in articles:
        source_id = f"{article.source}_{article.published_at.timestamp()}"

        # Check if this news item already exists (SQLite-compatible)
        existing = await db.execute(
            select(NewsItem.id).where(
                NewsItem.source == (article.source or "finnhub"),
                NewsItem.source_id == source_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(NewsItem(
            ticker_id=ticker_id,
            symbol=symbol,
            source_id=source_id,
            source=article.source or "finnhub",
            headline=article.headline,
            summary=article.summary,
            url=article.url,
            image_url=article.image_url,
            published_at=article.published_at,
            category=article.category,
            sentiment_score=article.sentiment_score,
            sentiment_label=article.sentiment_label,
            related_tickers=article.related_tickers,
        ))
        count += 1

    await db.commit()
    logger.info(f"Stored {count} news items for {symbol}")
    return count


async def fetch_market_news(db: AsyncSession, ticker_limit: int = 10) -> dict:
    """Fetch news for top tracked tickers from Finnhub and store in DB.

    Fetches for up to `ticker_limit` active tickers. Returns summary stats.
    """
    # Get active tickers
    tickers = list((await db.execute(
        select(Ticker).where(Ticker.active == True).limit(ticker_limit)  # noqa: E712
    )).scalars().all())

    if not tickers:
        return {"tickers_processed": 0, "articles_stored": 0, "errors": []}

    total_stored = 0
    errors = []

    for t in tickers:
        try:
            count = await refresh_news(db, t.id, t.symbol)
            total_stored += count
        except Exception as e:
            errors.append(f"{t.symbol}: {str(e)}")
            logger.warning(f"Failed to fetch news for {t.symbol}: {e}")

    return {
        "tickers_processed": len(tickers),
        "articles_stored": total_stored,
        "errors": errors,
    }
