"""Top-level signal scorer orchestrating all sub-components."""

import pandas as pd

from app.scoring.weights import get_weights
from app.scoring.regime import detect_regime
from app.scoring.trend_scorer import score_trend
from app.scoring.momentum_scorer import score_momentum
from app.scoring.volume_scorer import score_volume
from app.scoring.volatility_scorer import score_volatility
from app.scoring.structure_scorer import score_structure
from app.scoring.reasons import generate_reasons
from app.scoring.invalidation import compute_invalidation


class SignalResult:
    """Result of signal computation."""

    def __init__(
        self,
        score: float,
        regime: str,
        trend_score: float,
        momentum_score: float,
        volume_score: float,
        volatility_score: float,
        structure_score: float,
        reasons: list[dict],
        invalidation: dict,
    ):
        self.score = score
        self.regime = regime
        self.trend_score = trend_score
        self.momentum_score = momentum_score
        self.volume_score = volume_score
        self.volatility_score = volatility_score
        self.structure_score = structure_score
        self.reasons = reasons
        self.invalidation = invalidation


def compute_signal(indicators: dict, df: pd.DataFrame) -> SignalResult:
    """Compute the bullish signal score for a ticker.

    Args:
        indicators: Dictionary of computed indicator values (from compute_all_indicators)
        df: OHLCV DataFrame used for structure analysis

    Returns:
        SignalResult with composite score, sub-scores, reasons, and invalidation
    """
    # Detect market regime from ADX
    regime = detect_regime(indicators.get("adx_14"))

    # Get regime-adjusted weights
    weights = get_weights(regime)

    # Compute sub-scores
    trend = score_trend(indicators, df)
    momentum = score_momentum(indicators)
    vol = score_volume(indicators)
    volatility = score_volatility(indicators)
    struct = score_structure(indicators, df)

    # Compute weighted composite score
    composite = (
        trend * weights["trend"]
        + momentum * weights["momentum"]
        + vol * weights["volume"]
        + volatility * weights["volatility"]
        + struct * weights["structure"]
    )
    composite = round(min(composite, 100.0), 2)

    # Generate reasons and invalidation
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
