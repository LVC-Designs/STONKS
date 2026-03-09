"""Fast inference for strategy selector."""

import logging

import numpy as np
import torch

from app.ml.config import DEVICE, STRATEGY_INPUT_DIM
from app.ml.models.strategy_selector import StrategySelectorNet
from app.ml.registry import load_model, load_scaler

logger = logging.getLogger(__name__)

_cached_model: StrategySelectorNet | None = None
_cached_scaler = None
_cached_model_id: int | None = None
_cached_config_map: list[dict] | None = None


def load_strategy_selector(
    model_path: str,
    scaler_path: str,
    model_id: int,
    input_dim: int = 30,
    num_configs: int = 10,
    config_map: list[dict] | None = None,
):
    """Load and cache the strategy selector model."""
    global _cached_model, _cached_scaler, _cached_model_id, _cached_config_map

    if _cached_model_id == model_id:
        return _cached_model, _cached_scaler, _cached_config_map

    _cached_model = load_model(
        StrategySelectorNet, model_path,
        input_dim=input_dim, num_configs=num_configs,
    )
    _cached_scaler = load_scaler(scaler_path)
    _cached_model_id = model_id
    _cached_config_map = config_map or []
    logger.info(f"Loaded strategy selector model id={model_id}")
    return _cached_model, _cached_scaler, _cached_config_map


def predict_strategy(
    model: StrategySelectorNet,
    scaler,
    features: np.ndarray,
    config_map: list[dict],
) -> dict:
    """Recommend a strategy config given market condition features.

    Args:
        model: Loaded StrategySelectorNet
        scaler: Fitted StandardScaler
        features: (n_features,) array of market condition features
        config_map: List of strategy config dicts

    Returns dict with recommended_config, confidence, top_3.
    """
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    features_scaled = scaler.transform(features.reshape(1, -1)).astype(np.float32)
    x = torch.tensor(features_scaled, device=DEVICE)
    return model.recommend(x, config_map)


def clear_cache():
    global _cached_model, _cached_scaler, _cached_model_id, _cached_config_map
    _cached_model = None
    _cached_scaler = None
    _cached_model_id = None
    _cached_config_map = None
