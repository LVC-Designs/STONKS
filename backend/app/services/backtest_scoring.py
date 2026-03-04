"""Backtest scoring wrapper that supports custom weight overrides."""

import pandas as pd

from app.scoring.regime import detect_regime
from app.scoring.trend_scorer import score_trend
from app.scoring.momentum_scorer import score_momentum
from app.scoring.volume_scorer import score_volume
from app.scoring.volatility_scorer import score_volatility
from app.scoring.structure_scorer import score_structure
from app.scoring.weights import get_weights
from app.scoring.reasons import generate_reasons
from app.scoring.invalidation import compute_invalidation
from app.scoring.scorer import SignalResult


def compute_signal_with_overrides(
    indicators: dict,
    df: pd.DataFrame,
    weight_overrides: dict | None = None,
) -> SignalResult:
    """Compute signal score with optional weight overrides for backtesting.

    Args:
        indicators: Dict of computed indicator values
        df: OHLCV DataFrame for structure analysis
        weight_overrides: Optional dict like {"trend": 0.40, "momentum": 0.20, ...}

    Returns:
        SignalResult with composite score and sub-scores
    """
    regime = detect_regime(indicators.get("adx_14"))

    if weight_overrides:
        weights = {
            "trend": weight_overrides.get("trend", 0.30),
            "momentum": weight_overrides.get("momentum", 0.25),
            "volume": weight_overrides.get("volume", 0.15),
            "volatility": weight_overrides.get("volatility", 0.10),
            "structure": weight_overrides.get("structure", 0.20),
        }
    else:
        weights = get_weights(regime)

    trend = score_trend(indicators, df)
    momentum = score_momentum(indicators)
    vol = score_volume(indicators)
    volatility = score_volatility(indicators)
    struct = score_structure(indicators, df)

    composite = (
        trend * weights["trend"]
        + momentum * weights["momentum"]
        + vol * weights["volume"]
        + volatility * weights["volatility"]
        + struct * weights["structure"]
    )
    composite = round(min(composite, 100.0), 2)

    reasons = generate_reasons(indicators, df)
    invalidation = compute_invalidation(indicators, df)

    return SignalResult(
        score=composite,
        regime=regime,
        trend_score=round(trend, 2),
        momentum_score=round(momentum, 2),
        volume_score=round(vol, 2),
        volatility_score=round(volatility, 2),
        structure_score=round(struct, 2),
        reasons=reasons,
        invalidation=invalidation,
    )
