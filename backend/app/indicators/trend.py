import pandas as pd
import pandas_ta as ta


def compute_trend(df: pd.DataFrame) -> dict:
    """Compute trend indicators from OHLCV DataFrame.

    Expects columns: open, high, low, close, volume
    Returns dict of indicator values for the most recent bar.
    """
    result = {}

    # SMA
    sma50 = ta.sma(df["close"], length=50)
    sma100 = ta.sma(df["close"], length=100)
    sma200 = ta.sma(df["close"], length=200)
    result["sma_50"] = _last(sma50)
    result["sma_100"] = _last(sma100)
    result["sma_200"] = _last(sma200)

    # EMA
    ema9 = ta.ema(df["close"], length=9)
    ema20 = ta.ema(df["close"], length=20)
    ema50 = ta.ema(df["close"], length=50)
    result["ema_9"] = _last(ema9)
    result["ema_20"] = _last(ema20)
    result["ema_50"] = _last(ema50)

    # Ichimoku
    ichi = ta.ichimoku(df["high"], df["low"], df["close"], tenkan=9, kijun=26, senkou=52)
    if ichi is not None and len(ichi) == 2:
        ichi_df = ichi[0]
        result["ichi_tenkan"] = _last(ichi_df.iloc[:, 0]) if len(ichi_df.columns) > 0 else None
        result["ichi_kijun"] = _last(ichi_df.iloc[:, 1]) if len(ichi_df.columns) > 1 else None
        result["ichi_senkou_a"] = _last(ichi_df.iloc[:, 2]) if len(ichi_df.columns) > 2 else None
        result["ichi_senkou_b"] = _last(ichi_df.iloc[:, 3]) if len(ichi_df.columns) > 3 else None
        result["ichi_chikou"] = _last(ichi_df.iloc[:, 4]) if len(ichi_df.columns) > 4 else None
    else:
        result["ichi_tenkan"] = None
        result["ichi_kijun"] = None
        result["ichi_senkou_a"] = None
        result["ichi_senkou_b"] = None
        result["ichi_chikou"] = None

    return result


def _last(series: pd.Series | None) -> float | None:
    """Get the last non-NaN value from a Series."""
    if series is None or series.empty:
        return None
    val = series.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 4)
