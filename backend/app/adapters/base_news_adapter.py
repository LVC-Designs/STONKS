from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from app.schemas.news import NewsItemOut


class BaseNewsAdapter(ABC):
    """Abstract base class for news data providers."""

    @abstractmethod
    async def get_company_news(
        self, symbol: str, from_date: date, to_date: date
    ) -> List[NewsItemOut]:
        """Return news articles for a ticker in a date range."""
        ...

    @abstractmethod
    async def get_sentiment(self, symbol: str) -> Optional[float]:
        """Return aggregate sentiment score -1.0 to 1.0, or None."""
        ...

    async def close(self):
        """Clean up resources."""
        pass
