import logging
from datetime import date
from typing import List

import httpx

from app.adapters.base_market_adapter import BaseMarketAdapter
from app.config import settings
from app.schemas.ohlcv import OHLCVBar
from app.schemas.ticker import TickerOut
from app.utils.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)

# MIC code mapping for Polygon.io
EXCHANGE_GROUP_MICS = {
    "US": ["XNYS", "XNAS", "XASE", "ARCX", "BATS"],
    "CA": ["XTSE", "XTSX", "XNEO", "XCNQ"],
}

MIC_TO_EXCHANGE = {
    "XNYS": "NYSE",
    "XNAS": "NASDAQ",
    "XASE": "AMEX",
    "ARCX": "ARCA",
    "BATS": "BATS",
    "XTSE": "TSX",
    "XTSX": "TSXV",
    "XNEO": "NEO",
    "XCNQ": "CSE",
}

MIC_TO_COUNTRY = {
    "XNYS": "US", "XNAS": "US", "XASE": "US", "ARCX": "US", "BATS": "US",
    "XTSE": "CA", "XTSX": "CA", "XNEO": "CA", "XCNQ": "CA",
}


class PolygonAdapter(BaseMarketAdapter):
    """Polygon.io market data adapter."""

    BASE_URL = "https://api.polygon.io"

    def __init__(self):
        self.api_key = settings.POLYGON_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
        # Polygon free tier: 5 requests/minute
        self.rate_limiter = AsyncRateLimiter(max_calls=5, period=60.0)

    async def close(self):
        await self.client.aclose()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def list_tickers(
        self, exchange_group: str, active_only: bool = True
    ) -> List[TickerOut]:
        if not self.api_key:
            logger.warning("Polygon API key not configured")
            return []

        mics = EXCHANGE_GROUP_MICS.get(exchange_group.upper(), [])
        all_tickers = []

        for mic in mics:
            url = f"{self.BASE_URL}/v3/reference/tickers"
            params = {
                "market": "stocks",
                "exchange": mic,
                "active": "true" if active_only else "false",
                "limit": 1000,
                "apiKey": self.api_key,
            }

            while url:
                await self.rate_limiter.acquire()
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                for t in data.get("results", []):
                    is_otc = t.get("market", "") == "otc"
                    is_neo = mic == "XNEO"
                    exchange_name = MIC_TO_EXCHANGE.get(mic, mic)
                    country = MIC_TO_COUNTRY.get(mic, "US")

                    all_tickers.append(
                        TickerOut(
                            id=0,
                            symbol=t["ticker"],
                            name=t.get("name"),
                            exchange=exchange_name,
                            exchange_group=exchange_group.upper(),
                            country=country,
                            currency="CAD" if country == "CA" else "USD",
                            asset_type=t.get("type", "stock").lower(),
                            is_otc=is_otc,
                            is_neo=is_neo,
                            active=t.get("active", True),
                        )
                    )

                # Handle pagination
                next_url = data.get("next_url")
                if next_url:
                    url = next_url
                    params = {"apiKey": self.api_key}
                else:
                    url = None

        logger.info(f"Fetched {len(all_tickers)} tickers for {exchange_group}")
        return all_tickers

    async def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start: date,
        end: date,
        adjusted: bool = True,
    ) -> List[OHLCVBar]:
        if not self.api_key:
            logger.warning("Polygon API key not configured")
            return []

        url = (
            f"{self.BASE_URL}/v2/aggs/ticker/{ticker}/range/1/{timeframe}"
            f"/{start.isoformat()}/{end.isoformat()}"
        )
        params = {
            "adjusted": "true" if adjusted else "false",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.api_key,
        }

        await self.rate_limiter.acquire()
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        bars = []
        for r in data.get("results", []):
            # Polygon timestamps are in milliseconds
            from datetime import datetime, timezone
            trade_date = datetime.fromtimestamp(r["t"] / 1000, tz=timezone.utc).date()
            bars.append(
                OHLCVBar(
                    date=trade_date,
                    open=r["o"],
                    high=r["h"],
                    low=r["l"],
                    close=r["c"],
                    volume=int(r["v"]),
                    vwap=r.get("vw"),
                )
            )

        logger.info(f"Fetched {len(bars)} bars for {ticker}")
        return bars

    async def get_ticker_details(self, ticker: str) -> dict | None:
        """Fetch ticker details (description, SIC code, etc.) from Polygon."""
        if not self.api_key:
            return None

        url = f"{self.BASE_URL}/v3/reference/tickers/{ticker}"
        params = {"apiKey": self.api_key}

        try:
            await self.rate_limiter.acquire()
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("results", {})
            return {
                "description": result.get("description"),
                "sic_code": result.get("sic_code"),
                "sic_description": result.get("sic_description"),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch details for {ticker}: {e}")
            return None

    async def get_corporate_events(
        self, ticker: str, start: date, end: date
    ) -> List[dict]:
        # Stub for MVP
        return []
