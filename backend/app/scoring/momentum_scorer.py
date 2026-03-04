"""Score the momentum component (0-100)."""


def score_momentum(indicators: dict) -> float:
    """Score momentum based on RSI, MACD, Stochastic, ROC.

    Components:
    - RSI in bullish zone 40-70 for trend continuation (20 pts)
    - MACD histogram positive and rising (25 pts)
    - Stochastic cross above oversold (25 pts)
    - ROC positive (15 pts)
    - CCI in bullish zone (15 pts)
    """
    score = 0.0

    # RSI: 40-70 is the bullish continuation zone
    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if 40 <= rsi <= 70:
            score += 20.0
        elif 30 <= rsi < 40:
            # Approaching oversold in uptrend - potential reversal
            score += 10.0
        elif rsi > 70:
            # Overbought - momentum strong but risky
            score += 5.0

    # MACD histogram positive
    macd_hist = indicators.get("macd_histogram")
    macd_line = indicators.get("macd_line")
    macd_signal = indicators.get("macd_signal")
    if macd_hist is not None:
        if macd_hist > 0:
            score += 15.0
        if macd_line is not None and macd_signal is not None and macd_line > macd_signal:
            score += 10.0

    # Stochastic: K above D and not extremely overbought
    stoch_k = indicators.get("stoch_k")
    stoch_d = indicators.get("stoch_d")
    if stoch_k is not None and stoch_d is not None:
        if stoch_k > stoch_d:
            score += 15.0
        # Bullish cross from oversold
        if stoch_k > stoch_d and stoch_d < 30:
            score += 10.0

    # ROC positive
    roc = indicators.get("roc_12")
    if roc is not None and roc > 0:
        score += 15.0

    # CCI bullish zone (0 to +200)
    cci = indicators.get("cci_20")
    if cci is not None:
        if 0 < cci < 200:
            score += 15.0
        elif cci >= 200:
            score += 5.0  # Extremely overbought

    return min(score, 100.0)
