from sqlalchemy import Column, Integer, Numeric, BigInteger, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class ComputedIndicator(Base):
    __tablename__ = "computed_indicators"

    id = Column(Integer, primary_key=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    # Trend
    sma_50 = Column(Numeric(14, 4))
    sma_100 = Column(Numeric(14, 4))
    sma_200 = Column(Numeric(14, 4))
    ema_9 = Column(Numeric(14, 4))
    ema_20 = Column(Numeric(14, 4))
    ema_50 = Column(Numeric(14, 4))
    # MACD
    macd_line = Column(Numeric(14, 6))
    macd_signal = Column(Numeric(14, 6))
    macd_histogram = Column(Numeric(14, 6))
    # Momentum
    rsi_14 = Column(Numeric(8, 4))
    stoch_k = Column(Numeric(8, 4))
    stoch_d = Column(Numeric(8, 4))
    roc_12 = Column(Numeric(10, 4))
    cci_20 = Column(Numeric(10, 4))
    adx_14 = Column(Numeric(8, 4))
    plus_di = Column(Numeric(8, 4))
    minus_di = Column(Numeric(8, 4))
    # Volume
    obv = Column(BigInteger)
    volume_sma_20 = Column(Numeric(18, 2))
    volume_ratio = Column(Numeric(8, 4))
    obv_slope = Column(Numeric(14, 4))
    # Volatility
    bb_upper = Column(Numeric(14, 4))
    bb_middle = Column(Numeric(14, 4))
    bb_lower = Column(Numeric(14, 4))
    bb_width = Column(Numeric(10, 6))
    bb_pctb = Column(Numeric(8, 4))
    atr_14 = Column(Numeric(14, 4))
    atr_percentile = Column(Numeric(8, 4))
    # Ichimoku
    ichi_tenkan = Column(Numeric(14, 4))
    ichi_kijun = Column(Numeric(14, 4))
    ichi_senkou_a = Column(Numeric(14, 4))
    ichi_senkou_b = Column(Numeric(14, 4))
    ichi_chikou = Column(Numeric(14, 4))
    # Fibonacci
    fib_swing_high = Column(Numeric(14, 4))
    fib_swing_low = Column(Numeric(14, 4))
    fib_236 = Column(Numeric(14, 4))
    fib_382 = Column(Numeric(14, 4))
    fib_500 = Column(Numeric(14, 4))
    fib_618 = Column(Numeric(14, 4))
    fib_786 = Column(Numeric(14, 4))
    # Meta
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker_id", "trade_date", name="uq_indicators_ticker_date"),
        Index("idx_indicators_ticker_date", "ticker_id", "trade_date"),
    )
