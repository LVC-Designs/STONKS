from datetime import date
from typing import List

from app.adapters.base_market_adapter import BaseMarketAdapter
from app.schemas.ohlcv import OHLCVBar
from app.schemas.ticker import TickerOut


class AlphaVantageAdapter(BaseMarketAdapter):
    """Alpha Vantage adapter (stub)."""

    async def list_tickers(
        self, exchange_group: str, active_only: bool = True
    ) -> List[TickerOut]:
        raise NotImplementedError("Alpha Vantage adapter is not yet implemented")

    async def get_ohlcv(
        self, ticker: str, timeframe: str, start: date, end: date, adjusted: bool = True
    ) -> List[OHLCVBar]:
        raise NotImplementedError("Alpha Vantage adapter is not yet implemented")

    async def get_corporate_events(
        self, ticker: str, start: date, end: date
    ) -> List[dict]:
        raise NotImplementedError("Alpha Vantage adapter is not yet implemented")
