"""Fast inference for price predictor LSTM."""

import logging

import numpy as np
import torch

from app.ml.config import DEVICE, PRICE_HIDDEN, PRICE_HORIZONS
from app.ml.models.price_predictor import PricePredictorNet
from app.ml.registry import load_model

logger = logging.getLogger(__name__)

_cached_model: PricePredictorNet | None = None
_cached_model_id: int | None = None


def load_price_predictor(model_path: str, model_id: int, input_dim: int = 6):
    """Load and cache the price predictor model."""
    global _cached_model, _cached_model_id

    if _cached_model_id == model_id:
        return _cached_model

    _cached_model = load_model(
        PricePredictorNet, model_path,
        input_dim=input_dim, hidden_dim=PRICE_HIDDEN, horizons=PRICE_HORIZONS,
    )
    _cached_model_id = model_id
    logger.info(f"Loaded price predictor model id={model_id}")
    return _cached_model


def predict_price(
    model: PricePredictorNet,
    ohlcv_window: np.ndarray,
) -> list[dict]:
    """Run price prediction on a single OHLCV window.

    Args:
        model: Loaded PricePredictorNet
        ohlcv_window: (seq_len, channels) array — note transposed from pattern input

    Returns list of {horizon_days, direction, probability, magnitude_pct} dicts.
    """
    x = torch.tensor(ohlcv_window, dtype=torch.float32, device=DEVICE).unsqueeze(0)
    return model.predict(x)


def clear_cache():
    global _cached_model, _cached_model_id
    _cached_model = None
    _cached_model_id = None
