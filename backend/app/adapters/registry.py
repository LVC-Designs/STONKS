from app.adapters.base_market_adapter import BaseMarketAdapter
from app.adapters.base_news_adapter import BaseNewsAdapter
from app.adapters.polygon_adapter import PolygonAdapter
from app.adapters.yahoo_adapter import YahooAdapter
from app.adapters.alphavantage_adapter import AlphaVantageAdapter
from app.adapters.finnhub_news_adapter import FinnhubNewsAdapter
from app.adapters.yahoo_news_adapter import YahooNewsAdapter
from app.adapters.newsapi_adapter import NewsAPIAdapter

_market_adapters: dict[str, type[BaseMarketAdapter]] = {
    "polygon": PolygonAdapter,
    "yahoo": YahooAdapter,
    "alphavantage": AlphaVantageAdapter,
}

_news_adapters: dict[str, type[BaseNewsAdapter]] = {
    "finnhub": FinnhubNewsAdapter,
    "yahoo_news": YahooNewsAdapter,
    "newsapi": NewsAPIAdapter,
}

# Singleton instances
_market_instance: BaseMarketAdapter | None = None
_news_instance: BaseNewsAdapter | None = None


def get_market_adapter(name: str = "polygon") -> BaseMarketAdapter:
    global _market_instance
    if _market_instance is None:
        adapter_class = _market_adapters.get(name)
        if not adapter_class:
            raise ValueError(f"Unknown market adapter: {name}. Available: {list(_market_adapters.keys())}")
        _market_instance = adapter_class()
    return _market_instance


def get_news_adapter(name: str = "finnhub") -> BaseNewsAdapter:
    global _news_instance
    if _news_instance is None:
        adapter_class = _news_adapters.get(name)
        if not adapter_class:
            raise ValueError(f"Unknown news adapter: {name}. Available: {list(_news_adapters.keys())}")
        _news_instance = adapter_class()
    return _news_instance


async def close_adapters():
    global _market_instance, _news_instance
    if _market_instance:
        await _market_instance.close()
        _market_instance = None
    if _news_instance:
        await _news_instance.close()
        _news_instance = None
