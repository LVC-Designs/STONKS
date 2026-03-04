"""Quant backtest models — disciplined train/val/OOS framework.

Design assumptions:
- A QuantBacktest is a top-level workflow that tests a grid of parameter combos.
- Each combo is a QuantBacktestCandidate with metrics per split (train/val/oos).
- Walk-forward mode produces multiple folds; per-fold metrics stored in JSONB.
- The engine optimizes on TRAIN, selects on VAL, reports on OOS.
- Stability score (0-100) measures robustness across splits and folds.
"""

from sqlalchemy import (
    Column, Integer, Numeric, String, Boolean, Date, DateTime, ForeignKey,
    Text,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.sql import func

from app.database import Base


class QuantBacktest(Base):
    """Top-level quant backtest workflow."""
    __tablename__ = "quant_backtests"

    id = Column(Integer, primary_key=True)
    name = Column(String(300))

    # "split" = single train/val/oos, "walk_forward" = rolling windows
    mode = Column(String(30), default="split", nullable=False)
    status = Column(String(20), default="pending", nullable=False)

    # Full config including date ranges, parameter grid, portfolio, etc.
    config = Column(JSONB, nullable=False)

    # The winning parameter combination (set after engine completes)
    selected_config = Column(JSONB)

    # Objective function used for ranking ("robust_composite" by default)
    objective = Column(String(60), default="robust_composite")

    # Stability score 0-100 (higher = more robust)
    stability_score = Column(Numeric(5, 2))

    # Final results: OOS metrics for the selected config
    results = Column(JSONB)

    # Diagnostics: preflight checks, coverage info
    diagnostics = Column(JSONB)

    # Warnings: list of human-readable warning strings
    warnings = Column(JSONB)

    # How many candidate configs were tested
    candidates_count = Column(Integer, default=0)

    # Progress tracking
    progress = Column(String(300))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class QuantBacktestCandidate(Base):
    """A single parameter combination tested in a quant sweep.

    Each candidate has metrics for train, validation, and OOS splits.
    For walk-forward mode, fold_metrics stores per-fold breakdown.
    """
    __tablename__ = "quant_backtest_candidates"

    id = Column(Integer, primary_key=True)
    quant_backtest_id = Column(
        Integer,
        ForeignKey("quant_backtests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The specific parameter combination
    config = Column(JSONB, nullable=False)

    # Ranking (1 = best)
    rank = Column(Integer)

    # Per-split metrics
    train_metrics = Column(JSONB)
    train_objective = Column(Numeric(8, 4))
    val_metrics = Column(JSONB)
    val_objective = Column(Numeric(8, 4))
    oos_metrics = Column(JSONB)

    # Stability score for this candidate
    stability_score = Column(Numeric(5, 2))

    # Whether this was the selected (winning) config
    is_selected = Column(Boolean, default=False)

    # Walk-forward: list of per-fold metrics dicts
    # [{fold: 0, train: {...}, val: {...}, oos: {...}}, ...]
    fold_metrics = Column(JSONB)

    # OOS equity curve for the selected candidate
    equity_curve = Column(JSONB)

    # Per-candidate warnings
    warnings = Column(JSONB)

    # Diagnostics per split
    diagnostics = Column(JSONB)
