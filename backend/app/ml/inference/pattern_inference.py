"""Fast inference for pattern recognizer CNN."""

import logging

import numpy as np
import torch

from app.ml.config import DEVICE, PATTERN_CHANNELS, PATTERN_WINDOW
from app.ml.models.pattern_recognizer import PatternRecognizerNet, PATTERN_NAMES
from app.ml.registry import load_model

logger = logging.getLogger(__name__)

_cached_model: PatternRecognizerNet | None = None
_cached_model_id: int | None = None


def load_pattern_recognizer(model_path: str, model_id: int):
    """Load and cache the pattern recognizer model."""
    global _cached_model, _cached_model_id

    if _cached_model_id == model_id:
        return _cached_model

    _cached_model = load_model(
        PatternRecognizerNet, model_path,
        in_channels=PATTERN_CHANNELS, seq_len=PATTERN_WINDOW,
    )
    _cached_model_id = model_id
    logger.info(f"Loaded pattern recognizer model id={model_id}")
    return _cached_model


def predict_patterns(
    model: PatternRecognizerNet,
    ohlcv_window: np.ndarray,
    threshold: float = 0.5,
) -> list[dict]:
    """Run pattern detection on a single OHLCV window.

    Args:
        model: Loaded PatternRecognizerNet
        ohlcv_window: (channels, seq_len) normalized window
        threshold: Minimum probability to report a pattern

    Returns list of {pattern, confidence} dicts.
    """
    x = torch.tensor(ohlcv_window, dtype=torch.float32, device=DEVICE).unsqueeze(0)
    return model.detect_patterns(x, threshold=threshold)


def clear_cache():
    global _cached_model, _cached_model_id
    _cached_model = None
    _cached_model_id = None
