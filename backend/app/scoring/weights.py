"""Weight profiles for signal scoring, adjusted by market regime."""

DEFAULT_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.25,
    "volume": 0.15,
    "volatility": 0.10,
    "structure": 0.20,
}

RANGING_WEIGHTS = {
    "trend": 0.10,
    "momentum": 0.35,
    "volume": 0.15,
    "volatility": 0.15,
    "structure": 0.25,
}

STRONG_TREND_WEIGHTS = {
    "trend": 0.40,
    "momentum": 0.20,
    "volume": 0.15,
    "volatility": 0.05,
    "structure": 0.20,
}


def get_weights(regime: str) -> dict[str, float]:
    """Return weight profile for the given regime."""
    if regime == "ranging":
        return RANGING_WEIGHTS.copy()
    elif regime == "strong_trend":
        return STRONG_TREND_WEIGHTS.copy()
    else:
        return DEFAULT_WEIGHTS.copy()
