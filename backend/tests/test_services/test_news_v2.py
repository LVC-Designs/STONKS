"""Minimal tests for News V2 — spec section H.

Tests:
  1. Dedup: inserting same provider+url twice results in one row.
  2. Ingest state: last_published_at updates correctly.
  3. Sentiment: only processes rows with sentiment_score NULL.
  4. News query: filters by ticker and date range.

Uses a test-specific engine with NullPool to avoid event loop issues.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.news_v2 import (
    NewsArticle,
    NewsArticleTicker,
    NewsIngestState,
)

# Create a test-specific engine with NullPool (no connection reuse between tests)
_test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
_test_session_factory = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


async def _cleanup():
    async with _test_session_factory() as db:
        await db.execute(text(
            "DELETE FROM news_article_tickers WHERE article_id IN "
            "(SELECT id FROM news_articles WHERE provider = 'test')"
        ))
        await db.execute(text("DELETE FROM news_articles WHERE provider = 'test'"))
        await db.execute(text("DELETE FROM news_ingest_state WHERE provider = 'test'"))
        await db.commit()


@pytest.mark.asyncio
async def test_dedup_provider_url():
    """Inserting the same (provider, url) twice should result in only one row."""
    await _cleanup()
    try:
        url = "https://example.com/test-dedup-article"
        now = datetime.now(timezone.utc)

        async with _test_session_factory() as db:
            for _ in range(2):
                stmt = pg_insert(NewsArticle).values(
                    provider="test",
                    url=url,
                    headline="Test dedup headline",
                    published_at=now,
                ).on_conflict_do_nothing(
                    constraint="uq_news_article_provider_url"
                )
                await db.execute(stmt)
            await db.commit()

        async with _test_session_factory() as db:
            count = (await db.execute(
                select(func.count(NewsArticle.id)).where(
                    NewsArticle.provider == "test",
                    NewsArticle.url == url,
                )
            )).scalar()

        assert count == 1, f"Expected 1 article but found {count} (dedup failed)"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_ingest_state_update():
    """Upserting ingest state should update last_published_at."""
    await _cleanup()
    try:
        ticker = "ZZTEST"
        provider = "test"
        ts1 = datetime(2025, 6, 1, tzinfo=timezone.utc)
        ts2 = datetime(2025, 7, 1, tzinfo=timezone.utc)

        async with _test_session_factory() as db:
            stmt = pg_insert(NewsIngestState).values(
                provider=provider,
                ticker=ticker,
                last_published_at=ts1,
                last_fetched_at=datetime.now(timezone.utc),
                status="ok",
            ).on_conflict_do_update(
                constraint="uq_ingest_state_provider_ticker",
                set_={"last_published_at": ts1},
            )
            await db.execute(stmt)
            await db.commit()

        async with _test_session_factory() as db:
            stmt2 = pg_insert(NewsIngestState).values(
                provider=provider,
                ticker=ticker,
                last_published_at=ts2,
                last_fetched_at=datetime.now(timezone.utc),
                status="ok",
            ).on_conflict_do_update(
                constraint="uq_ingest_state_provider_ticker",
                set_={"last_published_at": ts2},
            )
            await db.execute(stmt2)
            await db.commit()

        async with _test_session_factory() as db:
            result = await db.execute(
                select(NewsIngestState.last_published_at).where(
                    NewsIngestState.provider == provider,
                    NewsIngestState.ticker == ticker,
                )
            )
            stored_ts = result.scalar_one()

        assert stored_ts == ts2, f"Expected {ts2}, got {stored_ts}"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_sentiment_null_filter():
    """Articles with existing sentiment should not be re-processed."""
    await _cleanup()
    try:
        now = datetime.now(timezone.utc)

        async with _test_session_factory() as db:
            await db.execute(
                pg_insert(NewsArticle).values(
                    provider="test",
                    url="https://example.com/test-sentiment-skip",
                    headline="Already scored",
                    published_at=now,
                    sentiment_score=0.5,
                    sentiment_label="positive",
                    sentiment_model="vader_v1",
                    sentiment_computed_at=now,
                ).on_conflict_do_nothing(constraint="uq_news_article_provider_url")
            )

            await db.execute(
                pg_insert(NewsArticle).values(
                    provider="test",
                    url="https://example.com/test-sentiment-process",
                    headline="Needs scoring",
                    published_at=now,
                ).on_conflict_do_nothing(constraint="uq_news_article_provider_url")
            )
            await db.commit()

        async with _test_session_factory() as db:
            result = await db.execute(
                select(NewsArticle.id).where(
                    NewsArticle.provider == "test",
                    NewsArticle.sentiment_score.is_(None),
                )
            )
            unscored = result.all()

        assert len(unscored) == 1, f"Expected 1 unscored article but found {len(unscored)}"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_query_ticker_date_filter():
    """Querying with ticker and date filters should return matching articles only."""
    await _cleanup()
    try:
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=30)

        async with _test_session_factory() as db:
            r1 = await db.execute(
                pg_insert(NewsArticle).values(
                    provider="test",
                    url="https://example.com/test-filter-aapl-recent",
                    headline="AAPL recent news",
                    published_at=now,
                ).on_conflict_do_nothing(constraint="uq_news_article_provider_url").returning(NewsArticle.id)
            )
            id1 = r1.scalar_one_or_none()

            r2 = await db.execute(
                pg_insert(NewsArticle).values(
                    provider="test",
                    url="https://example.com/test-filter-aapl-old",
                    headline="AAPL old news",
                    published_at=old,
                ).on_conflict_do_nothing(constraint="uq_news_article_provider_url").returning(NewsArticle.id)
            )
            id2 = r2.scalar_one_or_none()

            r3 = await db.execute(
                pg_insert(NewsArticle).values(
                    provider="test",
                    url="https://example.com/test-filter-msft-recent",
                    headline="MSFT recent news",
                    published_at=now,
                ).on_conflict_do_nothing(constraint="uq_news_article_provider_url").returning(NewsArticle.id)
            )
            id3 = r3.scalar_one_or_none()

            if id1:
                await db.execute(pg_insert(NewsArticleTicker).values(article_id=id1, ticker="AAPL").on_conflict_do_nothing(constraint="uq_article_ticker"))
            if id2:
                await db.execute(pg_insert(NewsArticleTicker).values(article_id=id2, ticker="AAPL").on_conflict_do_nothing(constraint="uq_article_ticker"))
            if id3:
                await db.execute(pg_insert(NewsArticleTicker).values(article_id=id3, ticker="MSFT").on_conflict_do_nothing(constraint="uq_article_ticker"))
            await db.commit()

        async with _test_session_factory() as db:
            week_ago = now - timedelta(days=7)
            q = (
                select(NewsArticle)
                .join(NewsArticleTicker, NewsArticleTicker.article_id == NewsArticle.id)
                .where(
                    NewsArticleTicker.ticker == "AAPL",
                    NewsArticle.published_at >= week_ago,
                    NewsArticle.provider == "test",
                )
            )
            result = await db.execute(q)
            articles = result.scalars().all()

        assert len(articles) == 1, f"Expected 1 article, found {len(articles)}"
        assert articles[0].headline == "AAPL recent news"
    finally:
        await _cleanup()
