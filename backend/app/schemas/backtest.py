from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date, datetime


class WeightConfig(BaseModel):
    trend: float = 0.30
    momentum: float = 0.25
    volume: float = 0.15
    volatility: float = 0.10
    structure: float = 0.20


class PortfolioConfig(BaseModel):
    starting_capital: float = 10000.0
    max_positions: int = Field(5, ge=1, le=50)
    position_size_pct: float = Field(20.0, gt=0, le=100)
    use_equal_weight: bool = True


class WalkForwardConfig(BaseModel):
    train_pct: float = Field(60.0, gt=0, lt=100)
    validation_pct: float = Field(20.0, gt=0, lt=100)
    oos_pct: float = Field(20.0, gt=0, lt=100)


class BacktestConfig(BaseModel):
    name: Optional[str] = None
    date_from: date
    date_to: date
    min_score: float = Field(60.0, ge=0, le=100)
    target_pct: float = Field(5.0, gt=0)
    target_days: int = Field(20, ge=1, le=252)
    max_drawdown_pct: float = Field(-3.0, lt=0)
    weights: Optional[WeightConfig] = None
    portfolio: PortfolioConfig = PortfolioConfig()
    tickers: Optional[list[str]] = None
    exchange_groups: list[str] = ["US"]
    walk_forward: Optional[WalkForwardConfig] = None


class BatchRequest(BaseModel):
    configs: list[BacktestConfig] = Field(..., min_length=1, max_length=100)


class BatchResponse(BaseModel):
    run_ids: list[int]


class BacktestRunOut(BaseModel):
    id: int
    name: Optional[str] = None
    status: str
    date_from: date
    date_to: date
    config: dict
    results: Optional[dict] = None
    diagnostics: Optional[dict] = None
    signal_count: int = 0
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BacktestDetailOut(BacktestRunOut):
    portfolio_simulation: Optional[dict] = None


class BacktestRunListResponse(BaseModel):
    items: list[BacktestRunOut]
    total: int
    page: int
    page_size: int


class BacktestSignalOut(BaseModel):
    id: int
    ticker_symbol: str = ""
    ticker_name: str = ""
    signal_date: date
    score: Optional[float] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    outcome: Optional[str] = None
    actual_return: Optional[float] = None
    days_held: Optional[int] = None
    max_drawdown: Optional[float] = None

    model_config = {"from_attributes": True}


class BacktestSignalListResponse(BaseModel):
    items: list[BacktestSignalOut]
    total: int
    page: int
    page_size: int


class EquityCurvePoint(BaseModel):
    date: str
    equity: float
    positions: int = 0


class CompareRunSummary(BaseModel):
    id: int
    name: Optional[str] = None
    config: dict
    results: Optional[dict] = None


class CompareResponse(BaseModel):
    runs: list[CompareRunSummary]


class SweepConfig(BaseModel):
    """Configuration for automated strategy parameter sweep."""
    date_from: date
    date_to: date
    exchange_groups: list[str] = ["US"]
    # Parameter ranges to sweep
    min_scores: list[float] = Field(default=[50, 60, 70, 80])
    target_pcts: list[float] = Field(default=[3.0, 5.0, 8.0])
    target_days_list: list[int] = Field(default=[10, 20, 30])
    max_drawdown_pcts: list[float] = Field(default=[-2.0, -3.0, -5.0])
    # Portfolio (same for all runs)
    portfolio: PortfolioConfig = PortfolioConfig()
    walk_forward: Optional[WalkForwardConfig] = None


class SweepResponse(BaseModel):
    run_ids: list[int]
    total_combinations: int
