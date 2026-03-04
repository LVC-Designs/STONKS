"""Score the volume component (0-100)."""


def score_volume(indicators: dict) -> float:
    """Score volume based on volume ratio and OBV slope.

    Components:
    - Volume above 20-day average (volume_ratio > 1.0) (50 pts)
    - OBV slope positive (accumulation) (50 pts)
    """
    score = 0.0

    # Volume ratio: current volume vs 20D average
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio is not None:
        if vol_ratio >= 2.0:
            score += 50.0  # Very high volume confirmation
        elif vol_ratio >= 1.5:
            score += 40.0
        elif vol_ratio >= 1.0:
            score += 25.0
        elif vol_ratio >= 0.7:
            score += 10.0
        # Below 0.7 = very low volume, no points

    # OBV slope: positive slope = accumulation
    obv_slope = indicators.get("obv_slope")
    if obv_slope is not None:
        if obv_slope > 0:
            score += 50.0
        elif obv_slope > -1000:
            # Slightly negative but not strongly distributing
            score += 15.0

    return min(score, 100.0)
