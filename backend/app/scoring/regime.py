"""Market regime detection based on ADX."""


def detect_regime(adx: float | None) -> str:
    """Classify market regime based on ADX value.

    Returns:
        "ranging" if ADX < 20
        "trending" if 20 <= ADX <= 30
        "strong_trend" if ADX > 30
    """
    if adx is None:
        return "trending"  # Default assumption
    if adx < 20:
        return "ranging"
    elif adx > 30:
        return "strong_trend"
    else:
        return "trending"
