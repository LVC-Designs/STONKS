"""Pydantic schemas for News V2 API request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class NewsRefreshRequest(BaseModel):
    mode: str = Field("quick", pattern="^(quick|full)$")
    limit_tickers: int = Field(50, ge=1, le=500)
    max_articles_per_ticker: int = Field(25, ge=1, le=200)
    lookback_days: int = Field(3, ge=1, le=365)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TickerContext(BaseModel):
    ticker: str
    bar_date: Optional[str] = None
    close_at_publish: Optional[float] = None
    ret_1d: Optional[float] = None
    ret_5d: Optional[float] = None
    ret_20d: Optional[float] = None


class NewsArticleOut(BaseModel):
    id: int
    provider: str
    url: str
    source: Optional[str] = None
    headline: str
    summary: Optional[str] = None
    image_url: Optional[str] = None
    published_at: str
    fetched_at: Optional[str] = None
    tickers: list[str] = []
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_model: Optional[str] = None
    # Price context per ticker (included when available)
    ticker_context: list[TickerContext] = []


class NewsSentimentSummary(BaseModel):
    avg_score: Optional[float] = None
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    total: int = 0


class NewsListResponse(BaseModel):
    items: list[NewsArticleOut]
    total: int
    page: int
    page_size: int
    sentiment_summary: NewsSentimentSummary


class NewsRefreshResponse(BaseModel):
    status: str  # "started" | "completed"
    mode: str
    tickers_queued: int = 0
    tickers_processed: int = 0
    articles_stored: int = 0
    errors: list[str] = []


class NewsStatsResponse(BaseModel):
    total_articles: int = 0
    avg_sentiment: Optional[float] = None
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    articles_without_sentiment: int = 0
    tickers_with_news: int = 0
    oldest_article: Optional[str] = None
    newest_article: Optional[str] = None
