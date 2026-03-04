from pydantic import BaseModel
from typing import Optional
from datetime import date


class ReasonItem(BaseModel):
    component: str
    reason: str
    weight: float


class InvalidationLevel(BaseModel):
    price: float
    reason: str


class SignalDetail(BaseModel):
    signal_date: date
    score: float
    regime: Optional[str] = None
    trend_score: Optional[float] = None
    momentum_score: Optional[float] = None
    volume_score: Optional[float] = None
    volatility_score: Optional[float] = None
    structure_score: Optional[float] = None
    reasons: list[ReasonItem] = []
    invalidation: Optional[dict] = None
    target_pct: float = 5.0
    target_days: int = 20
    max_drawdown_pct: float = -3.0
    outcome: Optional[str] = None
    actual_return: Optional[float] = None
    days_to_target: Optional[int] = None

    model_config = {"from_attributes": True}
