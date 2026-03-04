import logging
from datetime import date
from typing import List, Optional

import httpx

from app.adapters.base_news_adapter import BaseNewsAdapter
from app.config import settings
from app.schemas.news import NewsItemOut
from app.utils.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)


def _compute_vader_sentiment(text: str) -> tuple[float, str]:
    """Compute sentiment using NLTK VADER. Returns (score, label)."""
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        compound = sia.polarity_scores(text)["compound"]
        if compound > 0.05:
            label = "positive"
        elif compound < -0.05:
            label = "negative"
        else:
            label = "neutral"
        return compound, label
    except Exception:
        logger.warning("VADER sentiment analysis failed, returning neutral")
        return 0.0, "neutral"


class FinnhubNewsAdapter(BaseNewsAdapter):
    """Finnhub news data adapter."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = settings.FINNHUB_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        # Finnhub free tier: 60 requests/minute
        self.rate_limiter = AsyncRateLimiter(max_calls=60, period=60.0)

    async def close(self):
        await self.client.aclose()

    async def get_company_news(
        self, symbol: str, from_date: date, to_date: date
    ) -> List[NewsItemOut]:
        if not self.api_key:
            logger.warning("Finnhub API key not configured")
            return []

        url = f"{self.BASE_URL}/company-news"
        params = {
            "symbol": symbol,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "token": self.api_key,
        }

        await self.rate_limiter.acquire()
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        articles = resp.json()

        news_items = []
        for article in articles:
            headline = article.get("headline", "")
            summary = article.get("summary", "")
            text_for_sentiment = f"{headline}. {summary}" if summary else headline

            sentiment_score, sentiment_label = _compute_vader_sentiment(text_for_sentiment)

            from datetime import datetime, timezone
            published_ts = article.get("datetime", 0)
            published_at = datetime.fromtimestamp(published_ts, tz=timezone.utc)

            news_items.append(
                NewsItemOut(
                    headline=headline,
                    summary=summary if summary else None,
                    url=article.get("url"),
                    image_url=article.get("image"),
                    source=article.get("source", "finnhub"),
                    published_at=published_at,
                    category=article.get("category"),
                    sentiment_score=sentiment_score,
                    sentiment_label=sentiment_label,
                    related_tickers=article.get("related", ""),
                )
            )

        logger.info(f"Fetched {len(news_items)} news items for {symbol}")
        return news_items

    async def get_sentiment(self, symbol: str) -> Optional[float]:
        """Get aggregate sentiment from recent news."""
        from datetime import timedelta
        today = date.today()
        news = await self.get_company_news(symbol, today - timedelta(days=7), today)
        if not news:
            return None
        scores = [n.sentiment_score for n in news if n.sentiment_score is not None]
        return sum(scores) / len(scores) if scores else None
