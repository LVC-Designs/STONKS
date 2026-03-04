from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./stonks.db"

    # API Keys
    POLYGON_API_KEY: str = ""
    FINNHUB_API_KEY: str = ""

    # Backend
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"

    # Signal defaults
    SIGNAL_TARGET_PCT: float = 5.0
    SIGNAL_TARGET_DAYS: int = 20
    SIGNAL_MAX_DRAWDOWN_PCT: float = -3.0

    # Screener defaults
    SCREENER_MIN_DOLLAR_VOLUME: float = 100000
    SCREENER_MIN_PRICE: float = 1.0

    # News V2 ingestion defaults
    NEWS_QUICK_REFRESH_TICKERS: int = 50
    NEWS_FULL_INGEST_BATCH_TICKERS: int = 25
    NEWS_MAX_ARTICLES_PER_TICKER: int = 25
    NEWS_LOOKBACK_DAYS: int = 3
    NEWS_CONCURRENCY: int = 10
    NEWS_SENTIMENT_BATCH_SIZE: int = 200

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ("../.env", ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
