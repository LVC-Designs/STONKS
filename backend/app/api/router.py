from fastapi import APIRouter

from app.api import screener, ticker_detail, news, settings, jobs, backtest, quant_backtest

api_router = APIRouter()

api_router.include_router(screener.router, prefix="/screener", tags=["screener"])
api_router.include_router(ticker_detail.router, prefix="/tickers", tags=["tickers"])
api_router.include_router(news.router, prefix="/news", tags=["news"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(quant_backtest.router, prefix="/backtest/quant", tags=["quant-backtest"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
