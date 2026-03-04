"""Score the volatility component (0-100)."""


def score_volatility(indicators: dict) -> float:
    """Score volatility based on Bollinger Bands and ATR percentile.

    Components:
    - BB squeeze (low BB width) indicates potential breakout setup (40 pts)
    - BB %B position favorable (above 0.5 = bullish momentum) (30 pts)
    - ATR percentile context (moderate volatility preferred) (30 pts)
    """
    score = 0.0

    # BB width - low width = squeeze = potential breakout
    bb_width = indicators.get("bb_width")
    if bb_width is not None:
        if bb_width < 0.05:
            score += 40.0  # Tight squeeze
        elif bb_width < 0.10:
            score += 30.0
        elif bb_width < 0.15:
            score += 20.0
        elif bb_width < 0.25:
            score += 10.0
        # Very wide bands = already expanded, less setup potential

    # BB %B - position within bands
    bb_pctb = indicators.get("bb_pctb")
    if bb_pctb is not None:
        if 0.5 <= bb_pctb <= 0.8:
            score += 30.0  # Above middle, not overbought
        elif 0.8 < bb_pctb <= 1.0:
            score += 15.0  # Near upper band
        elif 0.3 <= bb_pctb < 0.5:
            score += 10.0  # Below middle but recovering

    # ATR percentile - moderate volatility is ideal
    atr_pct = indicators.get("atr_percentile")
    if atr_pct is not None:
        if 20 <= atr_pct <= 60:
            score += 30.0  # Moderate - ideal for entries
        elif 60 < atr_pct <= 80:
            score += 15.0  # Elevated but manageable
        elif atr_pct < 20:
            score += 20.0  # Very low - potential squeeze
        # Very high ATR percentile = too volatile for entries

    return min(score, 100.0)
