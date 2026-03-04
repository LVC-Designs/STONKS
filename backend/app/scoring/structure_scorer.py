"""Score the structure component (0-100)."""

import pandas as pd

from app.indicators.structure import detect_higher_highs_lows, detect_breakout


def score_structure(indicators: dict, df: pd.DataFrame) -> float:
    """Score structure based on price patterns and Fibonacci support.

    Components:
    - Higher highs + higher lows pattern (35 pts)
    - Breakout above recent range (35 pts)
    - Price near Fibonacci support levels (30 pts)
    """
    score = 0.0

    # Higher highs and lows
    hhl = detect_higher_highs_lows(df)
    if hhl["trend_structure"] == "bullish":
        score += 35.0
    elif hhl["higher_highs"] or hhl["higher_lows"]:
        score += 17.5

    # Breakout detection
    bo = detect_breakout(df)
    if bo["breakout"]:
        score += 35.0

    # Fibonacci support: check if price is near a support level
    close = float(df["close"].iloc[-1])
    fib_levels = [
        indicators.get("fib_236"),
        indicators.get("fib_382"),
        indicators.get("fib_500"),
        indicators.get("fib_618"),
    ]

    for level in fib_levels:
        if level is not None and level > 0:
            distance_pct = abs(close - level) / close * 100
            if distance_pct < 2.0:
                score += 30.0
                break
            elif distance_pct < 5.0:
                score += 15.0
                break

    return min(score, 100.0)
