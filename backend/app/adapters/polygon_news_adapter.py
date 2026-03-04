import logging
from datetime import date, datetime, timezone
from typing import List, Optional

import httpx

from app.adapters.base_news_adapter import BaseNewsAdapter
from app.config import settings
from app.schemas.news import NewsItemOut
from app.utils.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)


def _compute_vader_sentiment(text: str) -> tuple[float, str]:
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
        return 0.0, "neutral"


class PolygonNewsAdapter(BaseNewsAdapter):
    """Polygon.io news adapter — provides deeper historical news than Finnhub."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self):
        self.api_key = settings.POLYGON_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        # Polygon free tier: 5 requests/minute
        self.rate_limiter = AsyncRateLimiter(max_calls=5, period=60.0)

    async def close(self):
        await self.client.aclose()

    async def get_company_news(
        self, symbol: str, from_date: date, to_date: date
    ) -> List[NewsItemOut]:
        if not self.api_key:
            logger.warning("Polygon API key not configured")
            return []

        url = f"{self.BASE_URL}/v2/reference/news"
        params = {
            "ticker": symbol,
            "published_utc.gte": from_date.isoformat(),
            "published_utc.lte": to_date.isoformat(),
            "order": "desc",
            "limit": 50,
            "sort": "published_utc",
            "apiKey": self.api_key,
        }

        all_items: List[NewsItemOut] = []
        pages_fetched = 0
        max_pages = 3  # Cap to avoid burning rate limit

        while url and pages_fetched < max_pages:
            try:
                await self.rate_limiter.acquire()
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Polygon news fetch failed for {symbol}: {e}")
                break

            for article in data.get("results", []):
                headline = article.get("title", "")
                summary = article.get("description", "")
                text_for_sentiment = f"{headline}. {summary}" if summary else headline
                sentiment_score, sentiment_label = _compute_vader_sentiment(text_for_sentiment)

                pub_str = article.get("published_utc", "")
                try:
                    published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except Exception:
                    published_at = datetime.now(timezone.utc)

                tickers = article.get("tickers", [])
                related = ",".join(tickers) if tickers else symbol

                all_items.append(
                    NewsItemOut(
                        headline=headline,
                        summary=summary if summary else None,
                        url=article.get("article_url"),
                        image_url=article.get("image_url"),
                        source=article.get("publisher", {}).get("name", "polygon"),
                        published_at=published_at,
                        category=None,
                        sentiment_score=sentiment_score,
                        sentiment_label=sentiment_label,
                        related_tickers=related,
                    )
                )

            # Pagination
            next_url = data.get("next_url")
            if next_url:
                url = next_url
                params = {"apiKey": self.api_key}
            else:
                url = None
            pages_fetched += 1

        logger.info(f"Fetched {len(all_items)} Polygon news items for {symbol}")
        return all_items

    async def get_sentiment(self, symbol: str) -> Optional[float]:
        from datetime import timedelta
        today = date.today()
        news = await self.get_company_news(symbol, today - timedelta(days=7), today)
        if not news:
            return None
        scores = [n.sentiment_score for n in news if n.sentiment_score is not None]
        return sum(scores) / len(scores) if scores else None
