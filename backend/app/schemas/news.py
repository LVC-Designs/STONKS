from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NewsItemOut(BaseModel):
    id: Optional[int] = None
    headline: str
    summary: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    published_at: datetime
    category: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    related_tickers: Optional[str] = None

    model_config = {"from_attributes": True}


class SentimentSummary(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    avg_score: Optional[float] = None
    confidence: Optional[float] = None
