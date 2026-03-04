"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tickers
    op.create_table(
        "tickers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("exchange", sa.String(20)),
        sa.Column("exchange_group", sa.String(20)),
        sa.Column("country", sa.String(5)),
        sa.Column("currency", sa.String(5)),
        sa.Column("asset_type", sa.String(20), server_default="stock"),
        sa.Column("is_otc", sa.Boolean(), server_default="false"),
        sa.Column("is_neo", sa.Boolean(), server_default="false"),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("polygon_ticker", sa.String(30)),
        sa.Column("finnhub_ticker", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "exchange", name="uq_ticker_symbol_exchange"),
    )
    op.create_index("idx_tickers_symbol", "tickers", ["symbol"])
    op.create_index("idx_tickers_exchange_group", "tickers", ["exchange_group"])
    op.create_index("idx_tickers_active", "tickers", ["active"])

    # Ticker universe snapshots
    op.create_table(
        "ticker_universe_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(20)),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("snapshot_date", "ticker_id", name="uq_universe_snap"),
    )
    op.create_index("idx_universe_snap_date", "ticker_universe_snapshots", ["snapshot_date"])

    # OHLCV daily
    op.create_table(
        "ohlcv_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(14, 4)),
        sa.Column("high", sa.Numeric(14, 4)),
        sa.Column("low", sa.Numeric(14, 4)),
        sa.Column("close", sa.Numeric(14, 4)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("vwap", sa.Numeric(14, 4)),
        sa.Column("num_trades", sa.Integer()),
        sa.Column("adjusted", sa.Boolean(), server_default="true"),
        sa.Column("source", sa.String(20), server_default="polygon"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker_id", "trade_date", name="uq_ohlcv_ticker_date"),
    )
    op.create_index("idx_ohlcv_ticker_date", "ohlcv_daily", ["ticker_id", "trade_date"])

    # Computed indicators
    op.create_table(
        "computed_indicators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        # Trend
        sa.Column("sma_50", sa.Numeric(14, 4)),
        sa.Column("sma_100", sa.Numeric(14, 4)),
        sa.Column("sma_200", sa.Numeric(14, 4)),
        sa.Column("ema_9", sa.Numeric(14, 4)),
        sa.Column("ema_20", sa.Numeric(14, 4)),
        sa.Column("ema_50", sa.Numeric(14, 4)),
        # MACD
        sa.Column("macd_line", sa.Numeric(14, 6)),
        sa.Column("macd_signal", sa.Numeric(14, 6)),
        sa.Column("macd_histogram", sa.Numeric(14, 6)),
        # Momentum
        sa.Column("rsi_14", sa.Numeric(8, 4)),
        sa.Column("stoch_k", sa.Numeric(8, 4)),
        sa.Column("stoch_d", sa.Numeric(8, 4)),
        sa.Column("roc_12", sa.Numeric(10, 4)),
        sa.Column("cci_20", sa.Numeric(10, 4)),
        sa.Column("adx_14", sa.Numeric(8, 4)),
        sa.Column("plus_di", sa.Numeric(8, 4)),
        sa.Column("minus_di", sa.Numeric(8, 4)),
        # Volume
        sa.Column("obv", sa.BigInteger()),
        sa.Column("volume_sma_20", sa.Numeric(18, 2)),
        sa.Column("volume_ratio", sa.Numeric(8, 4)),
        sa.Column("obv_slope", sa.Numeric(14, 4)),
        # Volatility
        sa.Column("bb_upper", sa.Numeric(14, 4)),
        sa.Column("bb_middle", sa.Numeric(14, 4)),
        sa.Column("bb_lower", sa.Numeric(14, 4)),
        sa.Column("bb_width", sa.Numeric(10, 6)),
        sa.Column("bb_pctb", sa.Numeric(8, 4)),
        sa.Column("atr_14", sa.Numeric(14, 4)),
        sa.Column("atr_percentile", sa.Numeric(8, 4)),
        # Ichimoku
        sa.Column("ichi_tenkan", sa.Numeric(14, 4)),
        sa.Column("ichi_kijun", sa.Numeric(14, 4)),
        sa.Column("ichi_senkou_a", sa.Numeric(14, 4)),
        sa.Column("ichi_senkou_b", sa.Numeric(14, 4)),
        sa.Column("ichi_chikou", sa.Numeric(14, 4)),
        # Fibonacci
        sa.Column("fib_swing_high", sa.Numeric(14, 4)),
        sa.Column("fib_swing_low", sa.Numeric(14, 4)),
        sa.Column("fib_236", sa.Numeric(14, 4)),
        sa.Column("fib_382", sa.Numeric(14, 4)),
        sa.Column("fib_500", sa.Numeric(14, 4)),
        sa.Column("fib_618", sa.Numeric(14, 4)),
        sa.Column("fib_786", sa.Numeric(14, 4)),
        # Meta
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker_id", "trade_date", name="uq_indicators_ticker_date"),
    )
    op.create_index("idx_indicators_ticker_date", "computed_indicators", ["ticker_id", "trade_date"])

    # Signals
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("regime", sa.String(20)),
        sa.Column("trend_score", sa.Numeric(5, 2)),
        sa.Column("momentum_score", sa.Numeric(5, 2)),
        sa.Column("volume_score", sa.Numeric(5, 2)),
        sa.Column("volatility_score", sa.Numeric(5, 2)),
        sa.Column("structure_score", sa.Numeric(5, 2)),
        sa.Column("reasons", postgresql.JSONB()),
        sa.Column("invalidation", postgresql.JSONB()),
        sa.Column("target_pct", sa.Numeric(5, 2), server_default="5.0"),
        sa.Column("target_days", sa.Integer(), server_default="20"),
        sa.Column("max_drawdown_pct", sa.Numeric(5, 2), server_default="-3.0"),
        sa.Column("outcome", sa.String(20)),
        sa.Column("actual_return", sa.Numeric(8, 4)),
        sa.Column("actual_max_dd", sa.Numeric(8, 4)),
        sa.Column("days_to_target", sa.Integer()),
        sa.Column("outcome_date", sa.Date()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ticker_id", "signal_date", name="uq_signals_ticker_date"),
    )
    op.create_index("idx_signals_date_score", "signals", ["signal_date", "score"])
    op.create_index("idx_signals_ticker", "signals", ["ticker_id"])
    op.create_index("idx_signals_outcome", "signals", ["outcome"])

    # News items
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=True),
        sa.Column("symbol", sa.String(20)),
        sa.Column("source_id", sa.String(100)),
        sa.Column("source", sa.String(30)),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("url", sa.String(1000)),
        sa.Column("image_url", sa.String(1000)),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("sentiment_score", sa.Numeric(5, 4)),
        sa.Column("sentiment_label", sa.String(20)),
        sa.Column("related_tickers", sa.String(200)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_id", name="uq_news_source_id"),
    )
    op.create_index("idx_news_ticker_date", "news_items", ["ticker_id", "published_at"])
    op.create_index("idx_news_published", "news_items", ["published_at"])

    # Settings
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Job runs
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("tickers_processed", sa.Integer(), server_default="0"),
        sa.Column("errors", postgresql.JSONB()),
        sa.Column("summary", postgresql.JSONB()),
    )
    op.create_index("idx_job_runs_name_started", "job_runs", ["job_name", "started_at"])

    # Backtest runs (Phase 2 scaffold)
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200)),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("results", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    # Backtest signals (Phase 2 scaffold)
    op.create_table(
        "backtest_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("backtest_run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker_id", sa.Integer(), sa.ForeignKey("tickers.id"), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("entry_price", sa.Numeric(14, 4)),
        sa.Column("target_price", sa.Numeric(14, 4)),
        sa.Column("stop_price", sa.Numeric(14, 4)),
        sa.Column("outcome", sa.String(20)),
        sa.Column("actual_return", sa.Numeric(8, 4)),
        sa.Column("days_held", sa.Integer()),
        sa.Column("max_drawdown", sa.Numeric(8, 4)),
    )
    op.create_index("idx_bt_signals_run", "backtest_signals", ["backtest_run_id"])

    # Portfolio simulations (Phase 2 scaffold)
    op.create_table(
        "portfolio_simulations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("backtest_run_id", sa.Integer(), sa.ForeignKey("backtest_runs.id", ondelete="CASCADE")),
        sa.Column("config", postgresql.JSONB()),
        sa.Column("equity_curve", postgresql.JSONB()),
        sa.Column("metrics", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("portfolio_simulations")
    op.drop_table("backtest_signals")
    op.drop_table("backtest_runs")
    op.drop_table("job_runs")
    op.drop_table("settings")
    op.drop_table("news_items")
    op.drop_table("signals")
    op.drop_table("computed_indicators")
    op.drop_table("ohlcv_daily")
    op.drop_table("ticker_universe_snapshots")
    op.drop_table("tickers")
