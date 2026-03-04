from sqlalchemy import Column, Integer, Numeric, BigInteger, Boolean, String, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.database import Base


class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"

    id = Column(Integer, primary_key=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    trade_date = Column(Date, nullable=False)
    open = Column(Numeric(14, 4))
    high = Column(Numeric(14, 4))
    low = Column(Numeric(14, 4))
    close = Column(Numeric(14, 4))
    volume = Column(BigInteger)
    vwap = Column(Numeric(14, 4))
    num_trades = Column(Integer)
    adjusted = Column(Boolean, default=True)
    source = Column(String(20), default="polygon")
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("ticker_id", "trade_date", name="uq_ohlcv_ticker_date"),
        Index("idx_ohlcv_ticker_date", "ticker_id", "trade_date"),
    )
