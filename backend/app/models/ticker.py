from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.sql import func
from app.database import Base


class Ticker(Base):
    __tablename__ = "tickers"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(255))
    exchange = Column(String(20))
    exchange_group = Column(String(20))
    country = Column(String(5))
    currency = Column(String(5))
    asset_type = Column(String(20), default="stock")
    is_otc = Column(Boolean, default=False)
    is_neo = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    polygon_ticker = Column(String(30))
    finnhub_ticker = Column(String(30))
    description = Column(Text)
    sic_code = Column(String(10))
    sic_description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_ticker_symbol_exchange"),
        Index("idx_tickers_symbol", "symbol"),
        Index("idx_tickers_exchange_group", "exchange_group"),
        Index("idx_tickers_active", "active"),
    )


class TickerUniverseSnapshot(Base):
    __tablename__ = "ticker_universe_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_date = Column(Date, nullable=False)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20))
    active = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("snapshot_date", "ticker_id", name="uq_universe_snap"),
        Index("idx_universe_snap_date", "snapshot_date"),
    )
