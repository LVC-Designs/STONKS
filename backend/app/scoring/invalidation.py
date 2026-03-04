"""Compute invalidation levels (support levels and ATR stops)."""

import pandas as pd


def compute_invalidation(indicators: dict, df: pd.DataFrame) -> dict:
    """Compute invalidation levels where the bullish thesis breaks.

    Returns dict with:
    - levels: list of {price, reason}
    - stop_atr_multiple: suggested ATR stop multiple
    """
    levels = []
    close = float(df["close"].iloc[-1])

    # SMA200 as major support
    sma200 = indicators.get("sma_200")
    if sma200:
        levels.append({"price": round(sma200, 2), "reason": "Below SMA200"})

    # EMA20 as short-term support
    ema20 = indicators.get("ema_20")
    if ema20:
        levels.append({"price": round(ema20, 2), "reason": "Below EMA20"})

    # Ichimoku cloud bottom
    senkou_a = indicators.get("ichi_senkou_a")
    senkou_b = indicators.get("ichi_senkou_b")
    if senkou_a is not None and senkou_b is not None:
        cloud_bottom = min(senkou_a, senkou_b)
        levels.append({"price": round(cloud_bottom, 2), "reason": "Below Ichimoku cloud"})

    # Fibonacci 61.8% retracement
    fib_618 = indicators.get("fib_618")
    if fib_618:
        levels.append({"price": round(fib_618, 2), "reason": "Below Fibonacci 61.8%"})

    # ATR-based stop
    atr = indicators.get("atr_14")
    if atr:
        atr_stop = close - (2.0 * atr)
        levels.append({"price": round(atr_stop, 2), "reason": "2x ATR stop"})

    # Recent swing low
    if len(df) >= 20:
        recent_low = float(df.tail(20)["low"].min())
        levels.append({"price": round(recent_low, 2), "reason": "Recent 20-day low"})

    # Sort levels by price descending (closest to current price first)
    levels.sort(key=lambda x: x["price"], reverse=True)

    return {
        "levels": levels,
        "stop_atr_multiple": 2.0,
    }
