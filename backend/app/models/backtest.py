from sqlalchemy import Column, Integer, Numeric, String, Date, DateTime, ForeignKey
from sqlalchemy import JSON as JSONB
from sqlalchemy.sql import func
from app.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    config = Column(JSONB, nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    status = Column(String(20), default="pending")
    results = Column(JSONB)
    diagnostics = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class BacktestSignal(Base):
    __tablename__ = "backtest_signals"

    id = Column(Integer, primary_key=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False)
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False)
    signal_date = Column(Date, nullable=False)
    score = Column(Numeric(5, 2))
    entry_price = Column(Numeric(14, 4))
    target_price = Column(Numeric(14, 4))
    stop_price = Column(Numeric(14, 4))
    outcome = Column(String(20))
    actual_return = Column(Numeric(8, 4))
    days_held = Column(Integer)
    max_drawdown = Column(Numeric(8, 4))


class PortfolioSimulation(Base):
    __tablename__ = "portfolio_simulations"

    id = Column(Integer, primary_key=True)
    backtest_run_id = Column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    config = Column(JSONB)
    equity_curve = Column(JSONB)
    metrics = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
