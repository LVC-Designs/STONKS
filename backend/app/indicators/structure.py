import numpy as np
import pandas as pd


def compute_structure(df: pd.DataFrame) -> dict:
    """Compute structure indicators from OHLCV DataFrame.

    Includes: higher highs/lows detection, breakout detection, Fibonacci retracement.
    Expects columns: open, high, low, close, volume
    Returns dict of indicator values for the most recent bar.
    """
    result = {}

    # Fibonacci retracement from last major swing (120-day lookback)
    fib = _compute_fibonacci(df, lookback=120)
    result.update(fib)

    return result


def _compute_fibonacci(df: pd.DataFrame, lookback: int = 120) -> dict:
    """Compute Fibonacci retracement levels from the last major swing.

    Strategy: Find the highest high and lowest low over the lookback period.
    If the high came first (bearish swing), compute retracement from high to low.
    If the low came first (bullish swing), compute retracement from low to high.
    """
    if len(df) < lookback:
        lookback = len(df)
    if lookback < 10:
        return {
            "fib_swing_high": None, "fib_swing_low": None,
            "fib_236": None, "fib_382": None, "fib_500": None,
            "fib_618": None, "fib_786": None,
        }

    window = df.tail(lookback)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())

    high_idx = window["high"].idxmax()
    low_idx = window["low"].idxmin()

    # Determine swing direction
    # If low came before high => bullish swing => retracement is measured from high
    # Fibonacci levels represent potential support during pullback
    diff = swing_high - swing_low

    result = {
        "fib_swing_high": round(swing_high, 4),
        "fib_swing_low": round(swing_low, 4),
    }

    if diff > 0:
        # Standard Fibonacci retracement levels (from swing high)
        result["fib_236"] = round(swing_high - diff * 0.236, 4)
        result["fib_382"] = round(swing_high - diff * 0.382, 4)
        result["fib_500"] = round(swing_high - diff * 0.500, 4)
        result["fib_618"] = round(swing_high - diff * 0.618, 4)
        result["fib_786"] = round(swing_high - diff * 0.786, 4)
    else:
        result["fib_236"] = None
        result["fib_382"] = None
        result["fib_500"] = None
        result["fib_618"] = None
        result["fib_786"] = None

    return result


def detect_higher_highs_lows(df: pd.DataFrame, window: int = 20) -> dict:
    """Detect pattern of higher highs and higher lows.

    Returns a dict with:
    - higher_highs: bool (recent high > previous high)
    - higher_lows: bool (recent low > previous low)
    - trend_structure: str ("bullish", "bearish", or "mixed")
    """
    if len(df) < window * 2:
        return {"higher_highs": False, "higher_lows": False, "trend_structure": "mixed"}

    recent = df.tail(window)
    previous = df.iloc[-(window * 2):-window]

    recent_high = float(recent["high"].max())
    previous_high = float(previous["high"].max())
    recent_low = float(recent["low"].min())
    previous_low = float(previous["low"].min())

    hh = recent_high > previous_high
    hl = recent_low > previous_low

    if hh and hl:
        structure = "bullish"
    elif not hh and not hl:
        structure = "bearish"
    else:
        structure = "mixed"

    return {"higher_highs": hh, "higher_lows": hl, "trend_structure": structure}


def detect_breakout(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Detect if the latest close is a breakout above the recent range.

    Returns:
    - breakout: bool
    - breakout_pct: float (% above the range high)
    """
    if len(df) < lookback + 1:
        return {"breakout": False, "breakout_pct": 0.0}

    range_data = df.iloc[-(lookback + 1):-1]
    range_high = float(range_data["high"].max())
    current_close = float(df["close"].iloc[-1])

    breakout = current_close > range_high
    breakout_pct = ((current_close - range_high) / range_high * 100) if range_high > 0 else 0.0

    return {"breakout": breakout, "breakout_pct": round(breakout_pct, 4)}
