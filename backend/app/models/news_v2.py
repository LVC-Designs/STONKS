"""News V2 models — normalized tables for incremental, memory-safe news ingestion.

Replaces the flat news_items table with:
  - news_articles: one row per unique article (deduped by provider+url)
  - news_article_tickers: many-to-many mapping of articles to tickers
  - news_ingest_state: tracks incremental fetch progress per provider+ticker
  - news_article_ticker_context: price context at publish time + forward returns
"""

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(30), nullable=False, default="finnhub")
    provider_id = Column(String(200), nullable=True)
    url = Column(Text, nullable=False)
    source = Column(Text, nullable=True)  # publisher name, e.g. "Reuters"
    headline = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    raw_payload = Column(JSONB, nullable=True)
    # Sentiment fields — populated by a separate pipeline after ingestion
    sentiment_label = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_model = Column(String(50), nullable=True)
    sentiment_computed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "url", name="uq_news_article_provider_url"),
        Index("idx_news_articles_published", "published_at"),
        Index("idx_news_articles_provider", "provider"),
        Index("idx_news_articles_sentiment_null", "sentiment_score"),  # fast lookup for unscored
    )


class NewsArticleTicker(Base):
    """Many-to-many: one article can mention multiple tickers."""
    __tablename__ = "news_article_tickers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("article_id", "ticker", name="uq_article_ticker"),
        Index("idx_article_tickers_ticker", "ticker"),
        Index("idx_article_tickers_article", "article_id"),
    )


class NewsIngestState(Base):
    """Tracks incremental ingestion progress per provider+ticker."""
    __tablename__ = "news_ingest_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(30), nullable=False, default="finnhub")
    ticker = Column(String(20), nullable=False)
    last_published_at = Column(DateTime(timezone=True), nullable=True)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=True, default="ok")  # ok / error
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "ticker", name="uq_ingest_state_provider_ticker"),
    )


class NewsArticleTickerContext(Base):
    """Price context at article publish time + forward returns for each ticker."""
    __tablename__ = "news_article_ticker_context"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(BigInteger, ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    bar_date = Column(Date, nullable=True)
    close_at_publish = Column(Float, nullable=True)
    ret_1d = Column(Float, nullable=True)
    ret_5d = Column(Float, nullable=True)
    ret_20d = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("article_id", "ticker", name="uq_context_article_ticker"),
        Index("idx_context_article", "article_id"),
        Index("idx_context_ticker", "ticker"),
    )
