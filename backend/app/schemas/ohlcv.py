from pydantic import BaseModel
from typing import Optional
from datetime import date


class OHLCVBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None

    model_config = {"from_attributes": True}


class OHLCVResponse(BaseModel):
    bars: list[OHLCVBar]
    ticker: str
