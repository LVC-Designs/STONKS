import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_volume(df: pd.DataFrame) -> dict:
    """Compute volume indicators from OHLCV DataFrame.

    Expects columns: open, high, low, close, volume
    Returns dict of indicator values for the most recent bar.
    """
    result = {}

    # OBV
    obv = ta.obv(df["close"], df["volume"])
    result["obv"] = int(_last(obv)) if _last(obv) is not None else None

    # Volume SMA 20
    vol_sma = ta.sma(df["volume"].astype(float), length=20)
    result["volume_sma_20"] = _last(vol_sma)

    # Volume ratio (current volume / 20-day average)
    if result["volume_sma_20"] and result["volume_sma_20"] > 0:
        current_vol = float(df["volume"].iloc[-1])
        result["volume_ratio"] = round(current_vol / result["volume_sma_20"], 4)
    else:
        result["volume_ratio"] = None

    # OBV slope (linear regression over last 5 periods)
    if obv is not None and len(obv.dropna()) >= 5:
        obv_last5 = obv.dropna().tail(5).values
        x = np.arange(5)
        slope = np.polyfit(x, obv_last5, 1)[0]
        result["obv_slope"] = round(float(slope), 4)
    else:
        result["obv_slope"] = None

    return result


def _last(series: pd.Series | None) -> float | None:
    """Get the last non-NaN value from a Series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 4)
