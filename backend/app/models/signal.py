from sqlalchemy import Column, Integer, Numeric, String, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy import JSON as JSONB
from sqlalchemy.sql import func
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    signal_date = Column(Date, nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    regime = Column(String(20))
    trend_score = Column(Numeric(5, 2))
    momentum_score = Column(Numeric(5, 2))
    volume_score = Column(Numeric(5, 2))
    volatility_score = Column(Numeric(5, 2))
    structure_score = Column(Numeric(5, 2))
    reasons = Column(JSONB)
    invalidation = Column(JSONB)
    target_pct = Column(Numeric(5, 2), default=5.0)
    target_days = Column(Integer, default=20)
    max_drawdown_pct = Column(Numeric(5, 2), default=-3.0)
    outcome = Column(String(20))
    actual_return = Column(Numeric(8, 4))
    actual_max_dd = Column(Numeric(8, 4))
    days_to_target = Column(Integer)
    outcome_date = Column(Date)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker_id", "signal_date", name="uq_signals_ticker_date"),
        Index("idx_signals_date_score", "signal_date", "score"),
        Index("idx_signals_ticker", "ticker_id"),
        Index("idx_signals_outcome", "outcome"),
    )
