"""Score the trend component (0-100)."""

import pandas as pd


def score_trend(indicators: dict, df: pd.DataFrame) -> float:
    """Score trend based on SMA/EMA positioning, Ichimoku confirmation.

    Components:
    - Price above SMA200 (25 pts)
    - EMA stack order: 9 > 20 > 50 (25 pts)
    - Price above Ichimoku cloud (25 pts)
    - Tenkan > Kijun (bullish cross) (25 pts)
    """
    score = 0.0
    close = float(df["close"].iloc[-1])

    # Price above SMA200
    sma200 = indicators.get("sma_200")
    if sma200 and close > sma200:
        score += 25.0

    # EMA stack: 9 > 20 > 50 (bullish alignment)
    ema9 = indicators.get("ema_9")
    ema20 = indicators.get("ema_20")
    ema50 = indicators.get("ema_50")
    if ema9 and ema20 and ema50:
        if ema9 > ema20 > ema50:
            score += 25.0
        elif ema9 > ema20 or ema20 > ema50:
            score += 12.5

    # Price above Ichimoku cloud
    senkou_a = indicators.get("ichi_senkou_a")
    senkou_b = indicators.get("ichi_senkou_b")
    if senkou_a is not None and senkou_b is not None:
        cloud_top = max(senkou_a, senkou_b)
        if close > cloud_top:
            score += 25.0
        elif close > min(senkou_a, senkou_b):
            score += 12.5

    # Tenkan > Kijun (bullish cross signal)
    tenkan = indicators.get("ichi_tenkan")
    kijun = indicators.get("ichi_kijun")
    if tenkan is not None and kijun is not None:
        if tenkan > kijun:
            score += 25.0

    return min(score, 100.0)
