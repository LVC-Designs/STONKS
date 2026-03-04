from pydantic import BaseModel
from typing import Optional
from datetime import date


class IndicatorSet(BaseModel):
    trade_date: date
    # Trend
    sma_50: Optional[float] = None
    sma_100: Optional[float] = None
    sma_200: Optional[float] = None
    ema_9: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    # MACD
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    # Momentum
    rsi_14: Optional[float] = None
    stoch_k: Optional[float] = None
    stoch_d: Optional[float] = None
    roc_12: Optional[float] = None
    cci_20: Optional[float] = None
    adx_14: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    # Volume
    obv: Optional[int] = None
    volume_sma_20: Optional[float] = None
    volume_ratio: Optional[float] = None
    obv_slope: Optional[float] = None
    # Volatility
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    bb_pctb: Optional[float] = None
    atr_14: Optional[float] = None
    atr_percentile: Optional[float] = None
    # Ichimoku
    ichi_tenkan: Optional[float] = None
    ichi_kijun: Optional[float] = None
    ichi_senkou_a: Optional[float] = None
    ichi_senkou_b: Optional[float] = None
    ichi_chikou: Optional[float] = None
    # Fibonacci
    fib_swing_high: Optional[float] = None
    fib_swing_low: Optional[float] = None
    fib_236: Optional[float] = None
    fib_382: Optional[float] = None
    fib_500: Optional[float] = None
    fib_618: Optional[float] = None
    fib_786: Optional[float] = None

    model_config = {"from_attributes": True}
