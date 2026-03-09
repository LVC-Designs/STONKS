"""Ensemble scorer — combines rule-based and NN scores."""

import logging

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.inference.signal_inference import (
    load_signal_scorer, predict_signal_score, clear_cache,
)
from app.ml.registry import get_active_model
from app.scoring.scorer import compute_signal

logger = logging.getLogger(__name__)


async def ensemble_score(
    db: AsyncSession,
    indicators: dict,
    df: pd.DataFrame,
    mode: str = "ensemble",
    nn_weight: float = 0.5,
) -> dict:
    """Produce a unified score combining rule-based and NN predictions.

    Args:
        db: Database session
        indicators: Dict of computed indicator values
        df: OHLCV DataFrame
        mode: "rule_based", "nn_only", or "ensemble"
        nn_weight: Weight for NN score in ensemble mode (0-1)

    Returns dict with composite_score, rule_based_score, nn_score, nn_confidence, mode.
    """
    # Always compute rule-based score
    rule_result = compute_signal(indicators, df)
    rule_score = rule_result.score

    result = {
        "composite_score": rule_score,
        "rule_based_score": rule_score,
        "nn_score": None,
        "nn_confidence": None,
        "mode": mode,
        "regime": rule_result.regime,
        "trend_score": rule_result.trend_score,
        "momentum_score": rule_result.momentum_score,
        "volume_score": rule_result.volume_score,
        "volatility_score": rule_result.volatility_score,
        "structure_score": rule_result.structure_score,
        "reasons": rule_result.reasons,
        "invalidation": rule_result.invalidation,
    }

    if mode == "rule_based":
        return result

    # Try to load NN model
    active_model = await get_active_model(db, "signal_scorer")
    if not active_model or not active_model.model_path or not active_model.scaler_path:
        logger.debug("No active signal scorer model — falling back to rule-based")
        result["mode"] = "rule_based"
        return result

    try:
        input_dim = (active_model.architecture or {}).get("input_dim", 55)
        model, scaler = load_signal_scorer(
            active_model.model_path, active_model.scaler_path,
            active_model.id, input_dim=input_dim,
        )

        close = float(df.iloc[-1]["close"]) if not df.empty else 0
        sub_scores = {
            "trend_score": rule_result.trend_score,
            "momentum_score": rule_result.momentum_score,
            "volume_score": rule_result.volume_score,
            "volatility_score": rule_result.volatility_score,
            "structure_score": rule_result.structure_score,
        }

        nn_score, nn_confidence = predict_signal_score(
            model, scaler, indicators, sub_scores, rule_result.regime, close,
        )

        result["nn_score"] = nn_score
        result["nn_confidence"] = nn_confidence

        if mode == "nn_only":
            result["composite_score"] = nn_score
        elif mode == "ensemble":
            result["composite_score"] = round(
                rule_score * (1 - nn_weight) + nn_score * nn_weight, 2
            )

    except Exception as e:
        logger.warning(f"NN scoring failed, falling back to rule-based: {e}")
        result["mode"] = "rule_based"

    return result
