"""News V2 ingestion service — incremental, memory-safe, bounded concurrency.

Design decisions:
  - Each ticker is processed independently; no giant article list in memory.
  - Writes to DB immediately per ticker (flush + commit per batch).
  - asyncio.Semaphore limits concurrent Finnhub API calls.
  - Ingest state tracked per (provider, ticker) for incremental fetching.
  - Sentiment is computed in a separate pipeline after ingestion.
  - Price context is computed in a separate pipeline after ingestion.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.news_v2 import (
    NewsArticle,
    NewsArticleTicker,
    NewsArticleTickerContext,
    NewsIngestState,
)
from app.models.ohlcv import OHLCVDaily
from app.models.ticker import Ticker
from app.models.signal import Signal
from app.adapters.registry import get_news_adapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

async def ingest_news(
    provider: str = "finnhub",
    mode: str = "incremental",
    tickers: list[str] | None = None,
    lookback_days: int | None = None,
    max_articles_per_ticker: int | None = None,
    concurrency: int | None = None,
) -> dict:
    """Ingest news articles for given tickers from the specified provider.

    Args:
        provider: news provider name (e.g. "finnhub")
        mode: "incremental" (default, uses ingest state) or "full" (ignores state)
        tickers: list of ticker symbols. If None, uses all active tickers.
        lookback_days: how far back to fetch if no ingest state exists
        max_articles_per_ticker: cap articles per ticker per fetch
        concurrency: max simultaneous API calls

    Returns:
        dict with tickers_processed, articles_stored, errors
    """
    lookback_days = lookback_days or settings.NEWS_LOOKBACK_DAYS
    max_articles_per_ticker = max_articles_per_ticker or settings.NEWS_MAX_ARTICLES_PER_TICKER
    concurrency = concurrency or settings.NEWS_CONCURRENCY

    semaphore = asyncio.Semaphore(concurrency)
    adapter = get_news_adapter(provider)

    # Resolve ticker list
    if tickers is None:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Ticker.symbol).where(Ticker.active == True)  # noqa: E712
            )
            tickers = [row[0] for row in result.all()]

    total_stored = 0
    errors: list[str] = []
    processed = 0

    for ticker_symbol in tickers:
        try:
            count = await _ingest_ticker(
                adapter=adapter,
                provider=provider,
                ticker_symbol=ticker_symbol,
                lookback_days=lookback_days,
                max_articles=max_articles_per_ticker,
                semaphore=semaphore,
                incremental=(mode == "incremental"),
            )
            total_stored += count
            processed += 1
        except Exception as e:
            errors.append(f"{ticker_symbol}: {str(e)}")
            logger.warning(f"News ingest failed for {ticker_symbol}: {e}")
            # Record error in ingest state
            try:
                async with async_session_factory() as db:
                    await _update_ingest_state(
                        db, provider, ticker_symbol, error=str(e)
                    )
                    await db.commit()
            except Exception:
                pass

        # Yield control to event loop every ticker
        await asyncio.sleep(0)

    return {
        "tickers_processed": processed,
        "articles_stored": total_stored,
        "errors": errors,
    }


async def _ingest_ticker(
    adapter,
    provider: str,
    ticker_symbol: str,
    lookback_days: int,
    max_articles: int,
    semaphore: asyncio.Semaphore,
    incremental: bool = True,
) -> int:
    """Fetch and store articles for a single ticker. Memory-safe: writes immediately."""

    async with async_session_factory() as db:
        # Determine date range
        from_date = date.today() - timedelta(days=lookback_days)
        if incremental:
            state = await _get_ingest_state(db, provider, ticker_symbol)
            if state and state.last_published_at:
                # Buffer of 1 day to catch late-arriving articles
                incremental_from = (state.last_published_at - timedelta(days=1)).date()
                from_date = max(from_date, incremental_from)

        to_date = date.today()

        # Fetch from provider with rate limiting via semaphore
        async with semaphore:
            articles = await adapter.get_company_news(ticker_symbol, from_date, to_date)

        # Cap articles to avoid memory issues
        if len(articles) > max_articles:
            # Keep the most recent ones
            articles = sorted(articles, key=lambda a: a.published_at, reverse=True)[:max_articles]

        count = 0
        max_published = None

        for article in articles:
            url = article.url
            if not url:
                continue

            # Upsert article (dedup by provider+url)
            stmt = pg_insert(NewsArticle).values(
                provider=provider,
                provider_id=getattr(article, 'source_id', None),
                url=url,
                source=article.source or provider,
                headline=article.headline or "",
                summary=article.summary,
                image_url=article.image_url,
                published_at=article.published_at,
                raw_payload=None,  # Could store raw data if desired
            ).on_conflict_do_nothing(
                constraint="uq_news_article_provider_url"
            ).returning(NewsArticle.id)

            result = await db.execute(stmt)
            row = result.fetchone()

            if row is not None:
                article_id = row[0]
                count += 1

                # Insert ticker mapping
                ticker_stmt = pg_insert(NewsArticleTicker).values(
                    article_id=article_id,
                    ticker=ticker_symbol,
                ).on_conflict_do_nothing(
                    constraint="uq_article_ticker"
                )
                await db.execute(ticker_stmt)

                # Also map related tickers if available
                related = getattr(article, 'related_tickers', None)
                if related and isinstance(related, str):
                    for rt in related.split(","):
                        rt = rt.strip().upper()
                        if rt and rt != ticker_symbol:
                            rt_stmt = pg_insert(NewsArticleTicker).values(
                                article_id=article_id,
                                ticker=rt,
                            ).on_conflict_do_nothing(
                                constraint="uq_article_ticker"
                            )
                            await db.execute(rt_stmt)
            else:
                # Article already existed — still add ticker mapping if not present
                existing = await db.execute(
                    select(NewsArticle.id).where(
                        NewsArticle.provider == provider,
                        NewsArticle.url == url,
                    )
                )
                existing_id = existing.scalar_one_or_none()
                if existing_id:
                    ticker_stmt = pg_insert(NewsArticleTicker).values(
                        article_id=existing_id,
                        ticker=ticker_symbol,
                    ).on_conflict_do_nothing(
                        constraint="uq_article_ticker"
                    )
                    await db.execute(ticker_stmt)

            # Track max published_at for ingest state
            if article.published_at:
                pa = article.published_at
                if not pa.tzinfo:
                    pa = pa.replace(tzinfo=timezone.utc)
                if max_published is None or pa > max_published:
                    max_published = pa

        # Update ingest state
        await _update_ingest_state(
            db, provider, ticker_symbol,
            last_published_at=max_published,
        )

        await db.commit()

    logger.info(f"Ingested {count} new articles for {ticker_symbol}")
    return count


async def _get_ingest_state(
    db: AsyncSession, provider: str, ticker: str
) -> Optional[NewsIngestState]:
    result = await db.execute(
        select(NewsIngestState).where(
            NewsIngestState.provider == provider,
            NewsIngestState.ticker == ticker,
        )
    )
    return result.scalar_one_or_none()


async def _update_ingest_state(
    db: AsyncSession,
    provider: str,
    ticker: str,
    last_published_at: Optional[datetime] = None,
    error: Optional[str] = None,
):
    """Upsert ingest state for a ticker."""
    now = datetime.now(timezone.utc)
    values = {
        "provider": provider,
        "ticker": ticker,
        "last_fetched_at": now,
        "status": "error" if error else "ok",
        "last_error": error,
    }
    if last_published_at:
        values["last_published_at"] = last_published_at

    stmt = pg_insert(NewsIngestState).values(**values).on_conflict_do_update(
        constraint="uq_ingest_state_provider_ticker",
        set_={
            "last_fetched_at": now,
            "status": "error" if error else "ok",
            "last_error": error,
            **({"last_published_at": last_published_at} if last_published_at else {}),
        },
    )
    await db.execute(stmt)


# ---------------------------------------------------------------------------
# Quick refresh vs full ingest helpers
# ---------------------------------------------------------------------------

async def quick_refresh(
    limit_tickers: int | None = None,
    max_articles_per_ticker: int | None = None,
    lookback_days: int | None = None,
) -> dict:
    """Quick refresh: fetch news for top-scoring tickers only."""
    limit_tickers = limit_tickers or settings.NEWS_QUICK_REFRESH_TICKERS
    max_articles = max_articles_per_ticker or settings.NEWS_MAX_ARTICLES_PER_TICKER
    lookback = lookback_days or settings.NEWS_LOOKBACK_DAYS

    # Get top tickers by signal score
    async with async_session_factory() as db:
        # Subquery for latest signal per ticker
        latest_signal = (
            select(
                Signal.ticker_id,
                func.max(Signal.signal_date).label("max_date"),
            )
            .group_by(Signal.ticker_id)
            .subquery()
        )

        q = (
            select(Ticker.symbol)
            .join(latest_signal, Ticker.id == latest_signal.c.ticker_id)
            .join(
                Signal,
                and_(
                    Signal.ticker_id == latest_signal.c.ticker_id,
                    Signal.signal_date == latest_signal.c.max_date,
                ),
            )
            .where(Ticker.active == True)  # noqa: E712
            .order_by(Signal.score.desc())
            .limit(limit_tickers)
        )
        result = await db.execute(q)
        tickers = [row[0] for row in result.all()]

    if not tickers:
        # Fallback: just take first N active tickers
        async with async_session_factory() as db:
            result = await db.execute(
                select(Ticker.symbol)
                .where(Ticker.active == True)  # noqa: E712
                .limit(limit_tickers)
            )
            tickers = [row[0] for row in result.all()]

    # Ingest from Finnhub (recent, fast)
    finnhub_result = await ingest_news(
        provider="finnhub",
        mode="incremental",
        tickers=tickers,
        lookback_days=lookback,
        max_articles_per_ticker=max_articles,
    )

    # Also ingest from Polygon (deeper historical coverage, slower due to rate limit)
    try:
        polygon_result = await ingest_news(
            provider="polygon_news",
            mode="incremental",
            tickers=tickers[:20],  # Cap for rate limit (5 req/min)
            lookback_days=max(lookback, 30),
            max_articles_per_ticker=max_articles,
            concurrency=2,
        )
        finnhub_result["articles_stored"] += polygon_result["articles_stored"]
    except Exception as e:
        logger.warning(f"Polygon news ingest skipped: {e}")

    return finnhub_result


async def full_ingest_batch(
    batch_size: int | None = None,
    max_articles_per_ticker: int | None = None,
    lookback_days: int | None = None,
) -> dict:
    """Full ingest: process next batch of tickers that haven't been fetched recently.

    Designed to be called repeatedly (e.g. by a scheduled job) to walk through
    the entire ticker universe over time without processing everything at once.
    """
    batch_size = batch_size or settings.NEWS_FULL_INGEST_BATCH_TICKERS
    max_articles = max_articles_per_ticker or settings.NEWS_MAX_ARTICLES_PER_TICKER
    lookback = lookback_days or settings.NEWS_LOOKBACK_DAYS

    async with async_session_factory() as db:
        # Find tickers that haven't been fetched recently or at all
        # Order by last_fetched_at ASC NULLS FIRST so unfetched tickers come first
        ingest_sub = (
            select(
                NewsIngestState.ticker,
                NewsIngestState.last_fetched_at,
            )
            .where(NewsIngestState.provider == "finnhub")
            .subquery()
        )

        q = (
            select(Ticker.symbol)
            .outerjoin(ingest_sub, Ticker.symbol == ingest_sub.c.ticker)
            .where(Ticker.active == True)  # noqa: E712
            .order_by(ingest_sub.c.last_fetched_at.asc().nulls_first())
            .limit(batch_size)
        )
        result = await db.execute(q)
        tickers = [row[0] for row in result.all()]

    if not tickers:
        return {"tickers_processed": 0, "articles_stored": 0, "errors": []}

    # Ingest from Finnhub (recent)
    finnhub_result = await ingest_news(
        provider="finnhub",
        mode="incremental",
        tickers=tickers,
        lookback_days=lookback,
        max_articles_per_ticker=max_articles,
    )

    # Also ingest from Polygon (historical depth)
    try:
        polygon_result = await ingest_news(
            provider="polygon_news",
            mode="incremental",
            tickers=tickers[:20],
            lookback_days=max(lookback, 30),
            max_articles_per_ticker=max_articles,
            concurrency=2,
        )
        finnhub_result["articles_stored"] += polygon_result["articles_stored"]
    except Exception as e:
        logger.warning(f"Polygon news ingest skipped: {e}")

    return finnhub_result


# ---------------------------------------------------------------------------
# Sentiment pipeline — runs separately from ingestion
# ---------------------------------------------------------------------------

async def compute_sentiment_for_new_articles(
    batch_size: int | None = None,
) -> dict:
    """Compute sentiment for articles that don't have it yet.

    Uses VADER from NLTK on headline + summary. Processes in batches.
    """
    batch_size = batch_size or settings.NEWS_SENTIMENT_BATCH_SIZE
    model_name = "vader_v1"

    from app.adapters.finnhub_news_adapter import _compute_vader_sentiment

    total_processed = 0

    while True:
        async with async_session_factory() as db:
            # Get batch of articles without sentiment
            result = await db.execute(
                select(NewsArticle.id, NewsArticle.headline, NewsArticle.summary)
                .where(NewsArticle.sentiment_score.is_(None))
                .limit(batch_size)
            )
            rows = result.all()

            if not rows:
                break

            now = datetime.now(timezone.utc)

            for article_id, headline, summary in rows:
                text = f"{headline}. {summary}" if summary else (headline or "")
                if not text.strip():
                    continue

                score, label = _compute_vader_sentiment(text)

                await db.execute(
                    update(NewsArticle)
                    .where(NewsArticle.id == article_id)
                    .values(
                        sentiment_score=score,
                        sentiment_label=label,
                        sentiment_model=model_name,
                        sentiment_computed_at=now,
                    )
                )

                total_processed += 1

            await db.commit()

        # Yield control between batches
        await asyncio.sleep(0)

        # If we got fewer than batch_size, we're done
        if len(rows) < batch_size:
            break

    logger.info(f"Computed sentiment for {total_processed} articles")
    return {"articles_processed": total_processed, "model": model_name}


# ---------------------------------------------------------------------------
# Price context computation
# ---------------------------------------------------------------------------

async def compute_news_market_context(batch_size: int = 200) -> dict:
    """Compute price context for article-ticker mappings that don't have it yet.

    For each (article_id, ticker) in news_article_tickers without a matching
    row in news_article_ticker_context, looks up the OHLCV bar at/near
    the article's published_at date and computes forward returns.
    """
    total_processed = 0
    errors = 0

    while True:
        async with async_session_factory() as db:
            # Find article-ticker mappings without context
            context_sub = (
                select(NewsArticleTickerContext.article_id, NewsArticleTickerContext.ticker)
                .subquery()
            )

            q = (
                select(
                    NewsArticleTicker.article_id,
                    NewsArticleTicker.ticker,
                    NewsArticle.published_at,
                )
                .join(NewsArticle, NewsArticle.id == NewsArticleTicker.article_id)
                .outerjoin(
                    context_sub,
                    and_(
                        NewsArticleTicker.article_id == context_sub.c.article_id,
                        NewsArticleTicker.ticker == context_sub.c.ticker,
                    ),
                )
                .where(context_sub.c.article_id.is_(None))
                .limit(batch_size)
            )
            result = await db.execute(q)
            rows = result.all()

            if not rows:
                break

            for article_id, ticker_symbol, published_at in rows:
                try:
                    context = await _compute_single_context(
                        db, article_id, ticker_symbol, published_at
                    )
                    if context:
                        stmt = pg_insert(NewsArticleTickerContext).values(
                            **context
                        ).on_conflict_do_nothing(
                            constraint="uq_context_article_ticker"
                        )
                        await db.execute(stmt)
                        total_processed += 1
                except Exception as e:
                    logger.debug(f"Context computation failed for article {article_id}/{ticker_symbol}: {e}")
                    errors += 1

            await db.commit()

        await asyncio.sleep(0)
        if len(rows) < batch_size:
            break

    logger.info(f"Computed market context for {total_processed} article-ticker pairs ({errors} errors)")
    return {"contexts_computed": total_processed, "errors": errors}


async def _compute_single_context(
    db: AsyncSession,
    article_id: int,
    ticker_symbol: str,
    published_at: datetime,
) -> Optional[dict]:
    """Compute price context for a single article-ticker pair."""

    # Find ticker_id
    ticker_result = await db.execute(
        select(Ticker.id).where(Ticker.symbol == ticker_symbol)
    )
    ticker_id = ticker_result.scalar_one_or_none()
    if not ticker_id:
        return None

    pub_date = published_at.date() if isinstance(published_at, datetime) else published_at

    # Get OHLCV bars around the publish date (the bar on/after publish date, plus 20 forward)
    bars_result = await db.execute(
        select(OHLCVDaily.trade_date, OHLCVDaily.close)
        .where(
            OHLCVDaily.ticker_id == ticker_id,
            OHLCVDaily.trade_date >= pub_date,
        )
        .order_by(OHLCVDaily.trade_date.asc())
        .limit(25)  # enough for 20 trading days forward + buffer
    )
    bars = bars_result.all()

    if not bars:
        return None

    bar_date = bars[0][0]
    close_at_publish = float(bars[0][1]) if bars[0][1] else None

    ret_1d = None
    ret_5d = None
    ret_20d = None

    if close_at_publish and close_at_publish > 0:
        if len(bars) > 1 and bars[1][1]:
            ret_1d = round((float(bars[1][1]) - close_at_publish) / close_at_publish * 100, 4)
        if len(bars) > 5 and bars[5][1]:
            ret_5d = round((float(bars[5][1]) - close_at_publish) / close_at_publish * 100, 4)
        if len(bars) > 20 and bars[20][1]:
            ret_20d = round((float(bars[20][1]) - close_at_publish) / close_at_publish * 100, 4)

    return {
        "article_id": article_id,
        "ticker": ticker_symbol,
        "bar_date": bar_date,
        "close_at_publish": close_at_publish,
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
    }


# ---------------------------------------------------------------------------
# Query helpers for the API
# ---------------------------------------------------------------------------

async def get_news_articles(
    db: AsyncSession,
    ticker: str | None = None,
    start: date | None = None,
    end: date | None = None,
    sentiment: str | None = None,
    min_abs_sentiment: float | None = None,
    sort_by: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Query news articles with filters. Returns (items, total_count)."""

    # Base query
    q = select(NewsArticle)

    # Filter by ticker via join
    if ticker:
        q = q.join(NewsArticleTicker, NewsArticleTicker.article_id == NewsArticle.id)
        q = q.where(NewsArticleTicker.ticker == ticker.upper())

    # Date filters
    if start:
        q = q.where(NewsArticle.published_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc))
    if end:
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        q = q.where(NewsArticle.published_at < end_dt)

    # Sentiment filters
    if sentiment:
        q = q.where(NewsArticle.sentiment_label == sentiment)
    if min_abs_sentiment is not None:
        q = q.where(
            func.abs(NewsArticle.sentiment_score) >= min_abs_sentiment
        )

    # Count total
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Sorting
    if sort_by == "newest":
        q = q.order_by(NewsArticle.published_at.desc())
    elif sort_by == "oldest":
        q = q.order_by(NewsArticle.published_at.asc())
    elif sort_by == "most_positive":
        q = q.order_by(NewsArticle.sentiment_score.desc().nulls_last())
    elif sort_by == "most_negative":
        q = q.order_by(NewsArticle.sentiment_score.asc().nulls_last())
    elif sort_by == "strongest":
        q = q.order_by(func.abs(NewsArticle.sentiment_score).desc().nulls_last())
    else:
        q = q.order_by(NewsArticle.published_at.desc())

    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    articles = result.scalars().all()

    # Build response with tickers + context
    items = []
    for article in articles:
        # Get tickers for this article
        tickers_result = await db.execute(
            select(NewsArticleTicker.ticker).where(
                NewsArticleTicker.article_id == article.id
            )
        )
        article_tickers = [r[0] for r in tickers_result.all()]

        # Get price context
        context_result = await db.execute(
            select(NewsArticleTickerContext).where(
                NewsArticleTickerContext.article_id == article.id
            )
        )
        contexts = context_result.scalars().all()

        items.append({
            "id": article.id,
            "provider": article.provider,
            "url": article.url,
            "source": article.source,
            "headline": article.headline,
            "summary": article.summary,
            "image_url": article.image_url,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
            "tickers": article_tickers,
            "sentiment_label": article.sentiment_label,
            "sentiment_score": article.sentiment_score,
            "sentiment_model": article.sentiment_model,
            "ticker_context": [
                {
                    "ticker": ctx.ticker,
                    "bar_date": ctx.bar_date.isoformat() if ctx.bar_date else None,
                    "close_at_publish": ctx.close_at_publish,
                    "ret_1d": ctx.ret_1d,
                    "ret_5d": ctx.ret_5d,
                    "ret_20d": ctx.ret_20d,
                }
                for ctx in contexts
            ],
        })

    return items, total


async def get_news_stats(
    db: AsyncSession,
    start: date | None = None,
    end: date | None = None,
) -> dict:
    """Get aggregate news statistics."""
    q_base = select(NewsArticle)
    if start:
        q_base = q_base.where(
            NewsArticle.published_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
        )
    if end:
        end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
        q_base = q_base.where(NewsArticle.published_at < end_dt)

    sub = q_base.subquery()

    total = (await db.execute(
        select(func.count()).select_from(sub)
    )).scalar() or 0

    avg_sentiment = (await db.execute(
        select(func.avg(sub.c.sentiment_score))
    )).scalar()

    pos = (await db.execute(
        select(func.count()).select_from(sub).where(sub.c.sentiment_label == "positive")
    )).scalar() or 0

    neg = (await db.execute(
        select(func.count()).select_from(sub).where(sub.c.sentiment_label == "negative")
    )).scalar() or 0

    neu = (await db.execute(
        select(func.count()).select_from(sub).where(sub.c.sentiment_label == "neutral")
    )).scalar() or 0

    no_sentiment = (await db.execute(
        select(func.count()).select_from(sub).where(sub.c.sentiment_score.is_(None))
    )).scalar() or 0

    # Distinct tickers with news
    tickers_with_news = (await db.execute(
        select(func.count(func.distinct(NewsArticleTicker.ticker)))
    )).scalar() or 0

    # Date range
    oldest = (await db.execute(
        select(func.min(sub.c.published_at))
    )).scalar()
    newest = (await db.execute(
        select(func.max(sub.c.published_at))
    )).scalar()

    return {
        "total_articles": total,
        "avg_sentiment": round(float(avg_sentiment), 4) if avg_sentiment else None,
        "positive_count": pos,
        "negative_count": neg,
        "neutral_count": neu,
        "articles_without_sentiment": no_sentiment,
        "tickers_with_news": tickers_with_news,
        "oldest_article": oldest.isoformat() if oldest else None,
        "newest_article": newest.isoformat() if newest else None,
    }
