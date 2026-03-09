"""Fast inference for signal scorer NN."""

import logging

import numpy as np
import torch

from app.ml.config import DEVICE
from app.ml.features import INDICATOR_COLUMNS, SUB_SCORE_COLUMNS, REGIME_MAP
from app.ml.models.signal_scorer import SignalScorerNet
from app.ml.registry import load_model, load_scaler

logger = logging.getLogger(__name__)

# Cached model and scaler (singleton pattern)
_cached_model: SignalScorerNet | None = None
_cached_scaler = None
_cached_model_id: int | None = None


def _build_feature_vector(indicators: dict, sub_scores: dict, regime: str, close: float) -> np.ndarray:
    """Build a feature vector from indicators and sub-scores."""
    ind_vals = [float(indicators.get(col) or 0) for col in INDICATOR_COLUMNS]
    sub_vals = [float(sub_scores.get(col) or 0) for col in SUB_SCORE_COLUMNS]
    regime_vec = [
        1.0 if regime == "ranging" else 0.0,
        1.0 if regime == "trending" else 0.0,
        1.0 if regime == "strong_trend" else 0.0,
    ]
    sma200 = float(indicators.get("sma_200") or 0)
    ema20 = float(indicators.get("ema_20") or 0)
    close_sma200 = close / sma200 if sma200 > 0 else 1.0
    close_ema20 = close / ema20 if ema20 > 0 else 1.0

    return np.array(ind_vals + sub_vals + regime_vec + [close_sma200, close_ema20], dtype=np.float32)


def load_signal_scorer(model_path: str, scaler_path: str, model_id: int, input_dim: int = 55):
    """Load and cache the signal scorer model."""
    global _cached_model, _cached_scaler, _cached_model_id

    if _cached_model_id == model_id:
        return _cached_model, _cached_scaler

    _cached_model = load_model(SignalScorerNet, model_path, input_dim=input_dim)
    _cached_scaler = load_scaler(scaler_path)
    _cached_model_id = model_id
    logger.info(f"Loaded signal scorer model id={model_id}")
    return _cached_model, _cached_scaler


def predict_signal_score(
    model: SignalScorerNet,
    scaler,
    indicators: dict,
    sub_scores: dict,
    regime: str,
    close: float,
) -> tuple[float, float]:
    """Run inference on a single ticker.

    Returns (nn_score 0-100, confidence 0-1).
    """
    features = _build_feature_vector(indicators, sub_scores, regime, close)
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    features_scaled = scaler.transform(features.reshape(1, -1)).astype(np.float32)
    x = torch.tensor(features_scaled, device=DEVICE)
    return model.predict_score(x)


def clear_cache():
    """Clear cached model (call when deploying a new version)."""
    global _cached_model, _cached_scaler, _cached_model_id
    _cached_model = None
    _cached_scaler = None
    _cached_model_id = None
