from abc import ABC, abstractmethod
from datetime import date
from typing import List

from app.schemas.ohlcv import OHLCVBar
from app.schemas.ticker import TickerOut


class BaseMarketAdapter(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    async def list_tickers(
        self, exchange_group: str, active_only: bool = True
    ) -> List[TickerOut]:
        """Return all tickers for a given exchange group (US, CA)."""
        ...

    @abstractmethod
    async def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start: date,
        end: date,
        adjusted: bool = True,
    ) -> List[OHLCVBar]:
        """Return OHLCV bars for a ticker in a date range."""
        ...

    @abstractmethod
    async def get_corporate_events(
        self, ticker: str, start: date, end: date
    ) -> List[dict]:
        """Return corporate events (splits, dividends). Optional for MVP."""
        ...

    async def close(self):
        """Clean up resources (HTTP clients, etc.)."""
        pass
