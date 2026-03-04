from datetime import date
from typing import List, Optional

from app.adapters.base_news_adapter import BaseNewsAdapter
from app.schemas.news import NewsItemOut


class NewsAPIAdapter(BaseNewsAdapter):
    """NewsAPI.org adapter (stub)."""

    async def get_company_news(
        self, symbol: str, from_date: date, to_date: date
    ) -> List[NewsItemOut]:
        raise NotImplementedError("NewsAPI adapter is not yet implemented")

    async def get_sentiment(self, symbol: str) -> Optional[float]:
        raise NotImplementedError("NewsAPI adapter is not yet implemented")
