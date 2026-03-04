import pandas as pd
import pandas_ta as ta


def compute_momentum(df: pd.DataFrame) -> dict:
    """Compute momentum indicators from OHLCV DataFrame.

    Expects columns: open, high, low, close, volume
    Returns dict of indicator values for the most recent bar.
    """
    result = {}

    # RSI
    rsi = ta.rsi(df["close"], length=14)
    result["rsi_14"] = _last(rsi)

    # MACD
    macd_result = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd_result is not None and not macd_result.empty:
        result["macd_line"] = _last(macd_result.iloc[:, 0])
        result["macd_signal"] = _last(macd_result.iloc[:, 2])
        result["macd_histogram"] = _last(macd_result.iloc[:, 1])
    else:
        result["macd_line"] = None
        result["macd_signal"] = None
        result["macd_histogram"] = None

    # Stochastic
    stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        result["stoch_k"] = _last(stoch.iloc[:, 0])
        result["stoch_d"] = _last(stoch.iloc[:, 1])
    else:
        result["stoch_k"] = None
        result["stoch_d"] = None

    # ROC
    roc = ta.roc(df["close"], length=12)
    result["roc_12"] = _last(roc)

    # CCI
    cci = ta.cci(df["high"], df["low"], df["close"], length=20)
    result["cci_20"] = _last(cci)

    # ADX
    adx_result = ta.adx(df["high"], df["low"], df["close"], length=14)
    if adx_result is not None and not adx_result.empty:
        result["adx_14"] = _last(adx_result.iloc[:, 0])
        result["plus_di"] = _last(adx_result.iloc[:, 1])
        result["minus_di"] = _last(adx_result.iloc[:, 2])
    else:
        result["adx_14"] = None
        result["plus_di"] = None
        result["minus_di"] = None

    return result


def _last(series: pd.Series | None) -> float | None:
    """Get the last non-NaN value from a Series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 4)
