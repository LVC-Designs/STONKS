import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_volatility(df: pd.DataFrame) -> dict:
    """Compute volatility indicators from OHLCV DataFrame.

    Expects columns: open, high, low, close, volume
    Returns dict of indicator values for the most recent bar.
    """
    result = {}

    # Bollinger Bands
    bb = ta.bbands(df["close"], length=20, std=2)
    if bb is not None and not bb.empty:
        result["bb_lower"] = _last(bb.iloc[:, 0])
        result["bb_middle"] = _last(bb.iloc[:, 1])
        result["bb_upper"] = _last(bb.iloc[:, 2])
        result["bb_width"] = _last(bb.iloc[:, 3]) if bb.shape[1] > 3 else None
        result["bb_pctb"] = _last(bb.iloc[:, 4]) if bb.shape[1] > 4 else None
    else:
        result["bb_upper"] = None
        result["bb_middle"] = None
        result["bb_lower"] = None
        result["bb_width"] = None
        result["bb_pctb"] = None

    # ATR
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    result["atr_14"] = _last(atr)

    # ATR percentile rank over 252 days
    if atr is not None and len(atr.dropna()) >= 20:
        atr_values = atr.dropna().tail(252).values
        current_atr = atr_values[-1]
        percentile = (np.sum(atr_values < current_atr) / len(atr_values)) * 100
        result["atr_percentile"] = round(float(percentile), 4)
    else:
        result["atr_percentile"] = None

    return result


def _last(series: pd.Series | None) -> float | None:
    """Get the last non-NaN value from a Series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 4)
