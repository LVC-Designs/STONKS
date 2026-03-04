"""Generate human-readable reasons for signal scoring."""

import pandas as pd


def generate_reasons(indicators: dict, df: pd.DataFrame) -> list[dict]:
    """Generate a list of bullish reasons from indicator values.

    Returns list of {"component": str, "reason": str, "weight": float}
    """
    reasons = []
    close = float(df["close"].iloc[-1])

    # Trend reasons
    sma200 = indicators.get("sma_200")
    if sma200 and close > sma200:
        reasons.append({
            "component": "trend",
            "reason": f"Price (${close:.2f}) above SMA200 (${sma200:.2f})",
            "weight": 0.30,
        })

    ema9 = indicators.get("ema_9")
    ema20 = indicators.get("ema_20")
    ema50 = indicators.get("ema_50")
    if ema9 and ema20 and ema50 and ema9 > ema20 > ema50:
        reasons.append({
            "component": "trend",
            "reason": "Bullish EMA stack (9 > 20 > 50)",
            "weight": 0.30,
        })

    senkou_a = indicators.get("ichi_senkou_a")
    senkou_b = indicators.get("ichi_senkou_b")
    if senkou_a is not None and senkou_b is not None:
        cloud_top = max(senkou_a, senkou_b)
        if close > cloud_top:
            reasons.append({
                "component": "trend",
                "reason": "Price above Ichimoku cloud",
                "weight": 0.30,
            })

    # Momentum reasons
    rsi = indicators.get("rsi_14")
    if rsi and 40 <= rsi <= 70:
        reasons.append({
            "component": "momentum",
            "reason": f"RSI ({rsi:.1f}) in bullish continuation zone",
            "weight": 0.25,
        })

    macd_hist = indicators.get("macd_histogram")
    if macd_hist and macd_hist > 0:
        reasons.append({
            "component": "momentum",
            "reason": "MACD histogram positive",
            "weight": 0.25,
        })

    stoch_k = indicators.get("stoch_k")
    stoch_d = indicators.get("stoch_d")
    if stoch_k and stoch_d and stoch_k > stoch_d:
        reasons.append({
            "component": "momentum",
            "reason": f"Stochastic bullish crossover (K:{stoch_k:.1f} > D:{stoch_d:.1f})",
            "weight": 0.25,
        })

    # Volume reasons
    vol_ratio = indicators.get("volume_ratio")
    if vol_ratio and vol_ratio >= 1.5:
        reasons.append({
            "component": "volume",
            "reason": f"Volume {vol_ratio:.1f}x above 20-day average",
            "weight": 0.15,
        })

    obv_slope = indicators.get("obv_slope")
    if obv_slope and obv_slope > 0:
        reasons.append({
            "component": "volume",
            "reason": "Positive OBV slope (accumulation)",
            "weight": 0.15,
        })

    # Volatility reasons
    bb_width = indicators.get("bb_width")
    if bb_width and bb_width < 0.10:
        reasons.append({
            "component": "volatility",
            "reason": "Bollinger Band squeeze (potential breakout)",
            "weight": 0.10,
        })

    # Structure reasons
    from app.indicators.structure import detect_higher_highs_lows, detect_breakout
    hhl = detect_higher_highs_lows(df)
    if hhl["trend_structure"] == "bullish":
        reasons.append({
            "component": "structure",
            "reason": "Higher highs and higher lows pattern",
            "weight": 0.20,
        })

    bo = detect_breakout(df)
    if bo["breakout"]:
        reasons.append({
            "component": "structure",
            "reason": f"Breakout above recent range ({bo['breakout_pct']:.1f}% above)",
            "weight": 0.20,
        })

    return reasons
