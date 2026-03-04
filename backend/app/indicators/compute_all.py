import pandas as pd

from app.indicators.trend import compute_trend
from app.indicators.momentum import compute_momentum
from app.indicators.volume import compute_volume
from app.indicators.volatility import compute_volatility
from app.indicators.structure import compute_structure


def compute_all_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators for a given OHLCV DataFrame.

    Args:
        df: DataFrame with columns [open, high, low, close, volume]
            sorted by date ascending. Should have at least 252 rows
            for full indicator coverage.

    Returns:
        Dictionary with all indicator values for the most recent bar.
        Keys match the computed_indicators table column names.
    """
    if df.empty or len(df) < 2:
        return {}

    # Ensure proper column names and types
    df = df.copy()
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)

    result = {}

    # Compute each category
    result.update(compute_trend(df))
    result.update(compute_momentum(df))
    result.update(compute_volume(df))
    result.update(compute_volatility(df))
    result.update(compute_structure(df))

    return result
