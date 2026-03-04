"""Pydantic schemas for quant backtesting API."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class QuantSplitDates(BaseModel):
    """Date ranges for train/val/oos splits."""
    date_from_train: date
    date_to_train: date
    date_from_val: date
    date_to_val: date
    date_from_oos: date
    date_to_oos: date


class WalkForwardParams(BaseModel):
    """Walk-forward rolling window parameters."""
    window_train_months: int = Field(12, ge=3, le=60)
    window_val_months: int = Field(3, ge=1, le=24)
    window_oos_months: int = Field(3, ge=1, le=24)
    step_months: int = Field(3, ge=1, le=12)


class QuantPortfolioConfig(BaseModel):
    starting_capital: float = 10000.0
    max_positions: int = Field(5, ge=1, le=50)
    position_size_pct: float = Field(20.0, gt=0, le=100)


class QuantSweepRequest(BaseModel):
    """Request body for POST /api/backtest/quant_sweep."""
    name: Optional[str] = None

    # Mode: "split" for single train/val/oos, "walk_forward" for rolling
    mode: str = Field("split", pattern="^(split|walk_forward)$")

    # For "split" mode: explicit date ranges
    splits: Optional[QuantSplitDates] = None

    # For "walk_forward" mode: overall range + window params
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    walk_forward: Optional[WalkForwardParams] = None

    # Parameter grid to sweep (each is a list of values)
    min_scores: list[float] = Field(default=[40, 50, 60, 70])
    target_pcts: list[float] = Field(default=[3.0, 5.0, 8.0])
    target_days_list: list[int] = Field(default=[10, 20, 30])
    max_drawdown_pcts: list[float] = Field(default=[-2.0, -3.0, -5.0])

    # Portfolio config (same for all candidates)
    portfolio: QuantPortfolioConfig = QuantPortfolioConfig()

    # Exchange filter
    exchange_groups: list[str] = ["US"]
    tickers: Optional[list[str]] = None

    # Top K candidates to promote from train to validation
    top_k: int = Field(10, ge=1, le=50)

    # Objective function name
    objective: str = "robust_composite"


class QuantMetrics(BaseModel):
    """Extended performance metrics computed per split."""
    trades: int = 0
    wins: int = 0
    losses: int = 0
    timeouts: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy: float = 0.0
    profit_factor: Optional[float] = None
    total_return: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: Optional[float] = None
    sharpe: float = 0.0
    sortino: Optional[float] = None
    volatility: float = 0.0
    exposure_pct: float = 0.0
    avg_hold_days: float = 0.0
    best_trade: Optional[float] = None
    worst_trade: Optional[float] = None
    p_value: Optional[float] = None
    # Portfolio-level
    final_equity: Optional[float] = None
    cagr: Optional[float] = None


class CandidateOut(BaseModel):
    id: int
    config: dict
    rank: Optional[int] = None
    train_metrics: Optional[dict] = None
    train_objective: Optional[float] = None
    val_metrics: Optional[dict] = None
    val_objective: Optional[float] = None
    oos_metrics: Optional[dict] = None
    stability_score: Optional[float] = None
    is_selected: bool = False
    fold_metrics: Optional[list] = None
    equity_curve: Optional[list] = None
    warnings: Optional[list] = None
    diagnostics: Optional[dict] = None

    model_config = {"from_attributes": True}


class QuantBacktestOut(BaseModel):
    id: int
    name: Optional[str] = None
    mode: str
    status: str
    config: dict
    selected_config: Optional[dict] = None
    objective: Optional[str] = None
    stability_score: Optional[float] = None
    results: Optional[dict] = None
    diagnostics: Optional[dict] = None
    warnings: Optional[list] = None
    candidates_count: int = 0
    progress: Optional[str] = None
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class QuantBacktestListResponse(BaseModel):
    items: list[QuantBacktestOut]
    total: int
    page: int
    page_size: int


class QuantBacktestDetailOut(QuantBacktestOut):
    candidates: list[CandidateOut] = []
