"""Feature extraction pipeline — DB → numpy arrays for ML training and inference."""

import logging
from datetime import date

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.indicator import ComputedIndicator
from app.models.signal import Signal
from app.models.ohlcv import OHLCVDaily
from app.models.ticker import Ticker

logger = logging.getLogger(__name__)

# Indicator columns used as features (must match computed_indicators table)
INDICATOR_COLUMNS = [
    "sma_50", "sma_100", "sma_200", "ema_9", "ema_20", "ema_50",
    "macd_line", "macd_signal", "macd_histogram",
    "rsi_14", "stoch_k", "stoch_d", "roc_12", "cci_20",
    "adx_14", "plus_di", "minus_di",
    "obv", "volume_sma_20", "volume_ratio", "obv_slope",
    "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_pctb",
    "atr_14", "atr_percentile",
    "ichi_tenkan", "ichi_kijun", "ichi_senkou_a", "ichi_senkou_b", "ichi_chikou",
    "fib_swing_high", "fib_swing_low", "fib_236", "fib_382", "fib_500",
    "fib_618", "fib_786",
]

# Sub-score columns from signals table
SUB_SCORE_COLUMNS = [
    "trend_score", "momentum_score", "volume_score",
    "volatility_score", "structure_score",
]

REGIME_MAP = {"ranging": 0, "trending": 1, "strong_trend": 2}
OUTCOME_MAP = {"win": 0, "loss": 1, "timeout": 2}


async def extract_signal_training_data(
    db: AsyncSession,
    date_from: date,
    date_to: date,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract features and labels for signal scorer training.

    Returns (X, y, feature_names) where:
    - X: (n_samples, n_features) float array
    - y: (n_samples,) int array — 0=win, 1=loss, 2=timeout
    - feature_names: list of feature column names
    """
    # Step 1: Get signals with outcomes (fast — uses outcome index)
    sig_query = (
        select(Signal)
        .where(
            Signal.outcome.in_(["win", "loss", "timeout"]),
            Signal.signal_date >= date_from,
            Signal.signal_date <= date_to,
        )
    )
    result = await db.execute(sig_query)
    signals = list(result.scalars().all())

    if not signals:
        return np.array([]), np.array([]), []

    logger.info(f"Found {len(signals)} signals with outcomes")

    # Step 2: Fetch indicators and OHLCV per-ticker (only for that ticker's signal dates)
    from collections import defaultdict
    ticker_signal_dates = defaultdict(list)
    for s in signals:
        ticker_signal_dates[s.ticker_id].append(s.signal_date)

    ind_lookup = {}
    close_lookup = {}

    for tid, dates in ticker_signal_dates.items():
        # Fetch only the indicator rows for this ticker's signal dates
        result = await db.execute(
            select(ComputedIndicator).where(
                ComputedIndicator.ticker_id == tid,
                ComputedIndicator.trade_date.in_(dates),
            )
        )
        for ci in result.scalars().all():
            ind_lookup[(ci.ticker_id, ci.trade_date)] = ci

        # Fetch OHLCV closes for this ticker's signal dates
        result = await db.execute(
            select(OHLCVDaily.trade_date, OHLCVDaily.close).where(
                OHLCVDaily.ticker_id == tid,
                OHLCVDaily.trade_date.in_(dates),
            )
        )
        for row in result.all():
            close_lookup[(tid, row[0])] = float(row[1]) if row[1] else 0.0

    logger.info(f"Fetched {len(ind_lookup)} indicator rows, {len(close_lookup)} close prices")

    feature_names = INDICATOR_COLUMNS + SUB_SCORE_COLUMNS + [
        "regime_ranging", "regime_trending", "regime_strong_trend",
        "close_sma200_ratio", "close_ema20_ratio",
    ]

    X_list = []
    y_list = []

    for sig in signals:
        ci = ind_lookup.get((sig.ticker_id, sig.signal_date))
        if ci is None:
            continue  # skip signals without indicator data

        # Indicator features
        ind_vals = [float(getattr(ci, col, None) or 0) for col in INDICATOR_COLUMNS]

        # Sub-scores
        sub_vals = [float(getattr(sig, col, None) or 0) for col in SUB_SCORE_COLUMNS]

        # Regime one-hot
        regime = sig.regime or "trending"
        regime_vec = [
            1.0 if regime == "ranging" else 0.0,
            1.0 if regime == "trending" else 0.0,
            1.0 if regime == "strong_trend" else 0.0,
        ]

        # Price-relative features
        close = close_lookup.get((sig.ticker_id, sig.signal_date), 0.0)
        sma200 = float(ind_vals[INDICATOR_COLUMNS.index("sma_200")] or 0)
        ema20 = float(ind_vals[INDICATOR_COLUMNS.index("ema_20")] or 0)
        close_sma200 = close / sma200 if sma200 > 0 else 1.0
        close_ema20 = close / ema20 if ema20 > 0 else 1.0

        features = ind_vals + sub_vals + regime_vec + [close_sma200, close_ema20]
        X_list.append(features)
        y_list.append(OUTCOME_MAP.get(sig.outcome, 2))

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)

    # Replace NaN/inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    logger.info(f"Extracted {len(X)} signal training samples ({date_from} to {date_to})")
    return X, y, feature_names


async def extract_ohlcv_windows(
    db: AsyncSession,
    ticker_ids: list[int],
    date_from: date,
    date_to: date,
    window_size: int = 60,
    stride: int = 5,
) -> list[dict]:
    """Extract OHLCV windows for pattern recognition / price prediction.

    Returns list of dicts with 'tensor' (channels, seq_len), 'ticker_id',
    'end_date', and forward return labels.
    """
    windows = []

    for tid in ticker_ids:
        query = (
            select(OHLCVDaily)
            .where(
                OHLCVDaily.ticker_id == tid,
                OHLCVDaily.trade_date >= date_from - pd.Timedelta(days=window_size * 2),
                OHLCVDaily.trade_date <= date_to + pd.Timedelta(days=30),
            )
            .order_by(OHLCVDaily.trade_date)
        )
        result = await db.execute(query)
        bars = list(result.scalars().all())

        if len(bars) < window_size + 20:
            continue

        records = []
        for b in bars:
            records.append({
                "date": b.trade_date,
                "open": float(b.open) if b.open else 0,
                "high": float(b.high) if b.high else 0,
                "low": float(b.low) if b.low else 0,
                "close": float(b.close) if b.close else 0,
                "volume": int(b.volume) if b.volume else 0,
            })

        df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

        for i in range(window_size, len(df) - 20, stride):
            window = df.iloc[i - window_size:i]
            end_date = window.iloc[-1]["date"]

            if end_date < date_from or end_date > date_to:
                continue

            # Normalize per window
            close_mean = window["close"].mean()
            close_std = window["close"].std()
            vol_mean = window["volume"].mean()

            if close_std == 0 or close_mean == 0 or vol_mean == 0:
                continue

            tensor = np.stack([
                (window["open"].values - close_mean) / close_std,
                (window["high"].values - close_mean) / close_std,
                (window["low"].values - close_mean) / close_std,
                (window["close"].values - close_mean) / close_std,
                np.log1p(window["volume"].values / vol_mean),
                window["close"].pct_change().fillna(0).values,
            ], axis=0).astype(np.float32)

            # Forward returns for labels
            future = df.iloc[i:i + 20]
            if len(future) < 5:
                continue
            last_close = window.iloc[-1]["close"]
            forward_returns = {}
            for h in [5, 10, 20]:
                if len(future) >= h:
                    fwd = float(future.iloc[h - 1]["close"])
                    forward_returns[h] = round((fwd - last_close) / last_close * 100, 4)

            windows.append({
                "tensor": tensor,
                "ticker_id": tid,
                "end_date": end_date,
                "forward_returns": forward_returns,
            })

    logger.info(f"Extracted {len(windows)} OHLCV windows")
    return windows


def fit_scaler(X: np.ndarray) -> StandardScaler:
    """Fit a StandardScaler on training data."""
    scaler = StandardScaler()
    scaler.fit(X)
    return scaler
