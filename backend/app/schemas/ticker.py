from pydantic import BaseModel
from typing import Optional


class TickerOut(BaseModel):
    id: int
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    exchange_group: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    asset_type: str = "stock"
    is_otc: bool = False
    is_neo: bool = False
    active: bool = True

    model_config = {"from_attributes": True}


class TickerFilter(BaseModel):
    exchange_group: Optional[str] = None
    active_only: bool = True
    is_otc: Optional[bool] = None
    is_neo: Optional[bool] = None


class ScreenerRow(BaseModel):
    symbol: str
    name: Optional[str] = None
    exchange: Optional[str] = None
    exchange_group: Optional[str] = None
    last_price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    avg_volume_20d: Optional[float] = None
    score: Optional[float] = None
    regime: Optional[str] = None
    signal_date: Optional[str] = None
    trend_score: Optional[float] = None
    momentum_score: Optional[float] = None
    volume_score: Optional[float] = None
    volatility_score: Optional[float] = None
    structure_score: Optional[float] = None


class ScreenerResponse(BaseModel):
    items: list[ScreenerRow]
    total: int
    page: int
    page_size: int
