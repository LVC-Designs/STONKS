"""Backtest service — engine, portfolio simulation, and metrics."""

import asyncio
import logging
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.backtest import BacktestRun, BacktestSignal, PortfolioSimulation
from app.models.ohlcv import OHLCVDaily
from app.models.ticker import Ticker
from app.indicators.compute_all import compute_all_indicators
from app.services.backtest_scoring import compute_signal_with_overrides

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(val) -> float | None:
    """Convert Decimal/numeric to float, or None."""
    if val is None:
        return None
    return float(val)


def _build_ohlcv_df(bars: list[OHLCVDaily]) -> pd.DataFrame:
    """Convert a list of OHLCVDaily rows into a pandas DataFrame."""
    records = []
    for b in bars:
        records.append({
            "date": b.trade_date,
            "open": _dec(b.open),
            "high": _dec(b.high),
            "low": _dec(b.low),
            "close": _dec(b.close),
            "volume": int(b.volume) if b.volume else 0,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df.sort_values("date", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


MIN_BARS_FOR_INDICATORS = 50  # Need at least this many bars to compute indicators


# ---------------------------------------------------------------------------
# Create / list / get / delete
# ---------------------------------------------------------------------------

async def create_backtest_run(db: AsyncSession, config: dict, launch: bool = True) -> BacktestRun:
    """Create a BacktestRun row and optionally launch engine in background."""
    name = config.pop("name", None)
    date_from = config.get("date_from")
    date_to = config.get("date_to")
    if isinstance(date_from, str):
        date_from = date.fromisoformat(date_from)
    if isinstance(date_to, str):
        date_to = date.fromisoformat(date_to)

    run = BacktestRun(
        name=name or f"Backtest {date_from} to {date_to}",
        config=config,
        date_from=date_from,
        date_to=date_to,
        status="pending",
    )
    db.add(run)
    await db.flush()
    run_id = run.id
    await db.commit()

    if launch:
        asyncio.create_task(_run_backtest_background(run_id))
    return run


async def create_batch(db: AsyncSession, configs: list[dict]) -> list[int]:
    """Create multiple BacktestRun rows and process them sequentially in background."""
    run_ids = []
    for cfg in configs:
        run = await create_backtest_run(db, cfg, launch=False)
        run_ids.append(run.id)

    asyncio.create_task(_run_sequential_backtests(run_ids))
    return run_ids


async def _run_sequential_backtests(run_ids: list[int]):
    """Process backtest runs one at a time to avoid overwhelming the system."""
    for run_id in run_ids:
        try:
            await _run_backtest_background(run_id)
        except Exception as e:
            logger.error(f"Sequential backtest {run_id} failed: {e}")


async def create_sweep(db: AsyncSession, sweep_cfg: dict) -> tuple[list[int], int]:
    """Generate a grid of strategy configs and queue them for sequential processing."""
    from itertools import product

    date_from = sweep_cfg["date_from"]
    date_to = sweep_cfg["date_to"]
    exchange_groups = sweep_cfg.get("exchange_groups", ["US"])
    portfolio = sweep_cfg.get("portfolio", {})
    walk_forward = sweep_cfg.get("walk_forward")

    min_scores = sweep_cfg.get("min_scores", [50, 60, 70, 80])
    target_pcts = sweep_cfg.get("target_pcts", [3.0, 5.0, 8.0])
    target_days_list = sweep_cfg.get("target_days_list", [10, 20, 30])
    max_dd_pcts = sweep_cfg.get("max_drawdown_pcts", [-2.0, -3.0, -5.0])

    combos = list(product(min_scores, target_pcts, target_days_list, max_dd_pcts))

    run_ids = []
    for ms, tp, td, mdd in combos:
        cfg = {
            "name": f"Sweep: score\u2265{ms} target={tp}%/{td}d dd={mdd}%",
            "date_from": date_from if isinstance(date_from, str) else date_from.isoformat(),
            "date_to": date_to if isinstance(date_to, str) else date_to.isoformat(),
            "min_score": ms,
            "target_pct": tp,
            "target_days": td,
            "max_drawdown_pct": mdd,
            "exchange_groups": exchange_groups,
            "portfolio": portfolio if isinstance(portfolio, dict) else portfolio,
        }
        if walk_forward:
            cfg["walk_forward"] = walk_forward if isinstance(walk_forward, dict) else walk_forward

        run = await create_backtest_run(db, cfg, launch=False)
        run_ids.append(run.id)

    # Launch a single background worker to process all runs sequentially
    asyncio.create_task(_run_sequential_backtests(run_ids))
    return run_ids, len(combos)


async def list_backtest_runs(
    db: AsyncSession,
    status: str | None = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List backtest runs with optional filtering."""
    q = select(BacktestRun)
    count_q = select(func.count(BacktestRun.id))

    if status:
        q = q.where(BacktestRun.status == status)
        count_q = count_q.where(BacktestRun.status == status)

    sort_col = getattr(BacktestRun, sort_by, BacktestRun.created_at)
    q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    q = q.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    runs = list(result.scalars().all())

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    items = []
    for r in runs:
        # Count signals for this run
        sig_count_q = select(func.count(BacktestSignal.id)).where(
            BacktestSignal.backtest_run_id == r.id
        )
        sig_result = await db.execute(sig_count_q)
        sig_count = sig_result.scalar() or 0

        items.append({
            "id": r.id,
            "name": r.name,
            "status": r.status,
            "date_from": r.date_from,
            "date_to": r.date_to,
            "config": r.config,
            "results": r.results,
            "diagnostics": r.diagnostics,
            "signal_count": sig_count,
            "created_at": r.created_at,
            "finished_at": r.finished_at,
        })

    return items, total


async def get_backtest_detail(db: AsyncSession, run_id: int) -> dict | None:
    """Get full backtest detail including portfolio simulation."""
    run = await db.get(BacktestRun, run_id)
    if not run:
        return None

    sig_count_q = select(func.count(BacktestSignal.id)).where(
        BacktestSignal.backtest_run_id == run_id
    )
    sig_result = await db.execute(sig_count_q)
    sig_count = sig_result.scalar() or 0

    sim_q = select(PortfolioSimulation).where(
        PortfolioSimulation.backtest_run_id == run_id
    )
    sim_result = await db.execute(sim_q)
    sim = sim_result.scalar_one_or_none()

    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "date_from": run.date_from,
        "date_to": run.date_to,
        "config": run.config,
        "results": run.results,
        "diagnostics": run.diagnostics,
        "signal_count": sig_count,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "portfolio_simulation": {
            "config": sim.config,
            "equity_curve": sim.equity_curve,
            "metrics": sim.metrics,
        } if sim else None,
    }


async def get_backtest_signals(
    db: AsyncSession,
    run_id: int,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """Get paginated signals for a backtest run."""
    count_q = select(func.count(BacktestSignal.id)).where(
        BacktestSignal.backtest_run_id == run_id
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(BacktestSignal, Ticker.symbol, Ticker.name)
        .join(Ticker, BacktestSignal.ticker_id == Ticker.id, isouter=True)
        .where(BacktestSignal.backtest_run_id == run_id)
        .order_by(BacktestSignal.signal_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    rows = result.all()

    items = []
    for sig, sym, ticker_name in rows:
        items.append({
            "id": sig.id,
            "ticker_symbol": sym or "",
            "ticker_name": ticker_name or "",
            "signal_date": sig.signal_date,
            "score": _dec(sig.score),
            "entry_price": _dec(sig.entry_price),
            "target_price": _dec(sig.target_price),
            "stop_price": _dec(sig.stop_price),
            "outcome": sig.outcome,
            "actual_return": _dec(sig.actual_return),
            "days_held": sig.days_held,
            "max_drawdown": _dec(sig.max_drawdown),
        })

    return items, total


async def get_equity_curve(db: AsyncSession, run_id: int) -> list[dict]:
    """Return equity curve for a backtest run."""
    sim_q = select(PortfolioSimulation).where(
        PortfolioSimulation.backtest_run_id == run_id
    )
    sim = (await db.execute(sim_q)).scalar_one_or_none()
    if not sim or not sim.equity_curve:
        return []
    return sim.equity_curve


async def compare_runs(db: AsyncSession, run_ids: list[int]) -> list[dict]:
    """Load multiple runs for side-by-side comparison."""
    q = select(BacktestRun).where(BacktestRun.id.in_(run_ids))
    result = await db.execute(q)
    runs = list(result.scalars().all())
    return [
        {
            "id": r.id,
            "name": r.name,
            "config": r.config,
            "results": r.results,
        }
        for r in runs
    ]


async def delete_backtest_run(db: AsyncSession, run_id: int) -> bool:
    """Delete a backtest run (signals + simulations cascade)."""
    run = await db.get(BacktestRun, run_id)
    if not run:
        return False
    await db.execute(
        delete(BacktestSignal).where(BacktestSignal.backtest_run_id == run_id)
    )
    await db.execute(
        delete(PortfolioSimulation).where(PortfolioSimulation.backtest_run_id == run_id)
    )
    await db.delete(run)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Preflight diagnostics
# ---------------------------------------------------------------------------

async def _run_preflight(
    db: AsyncSession,
    ticker_ids: list[int],
    date_from: date,
    date_to: date,
    min_score: float,
) -> dict:
    """Run preflight checks and return diagnostics dict."""
    diag: dict = {
        "tickers_in_universe": len(ticker_ids),
        "bars_available": {"min_date": None, "max_date": None, "total_rows": 0},
        "signals_computed": 0,
        "signals_meeting_threshold": 0,
        "max_signal_score_in_range": None,
        "min_signal_score_in_range": None,
        "reasons": [],
    }

    if not ticker_ids:
        diag["reasons"].append("No tickers found for the given exchange/filter.")
        return diag

    # Check OHLCV coverage
    ohlcv_stats = await db.execute(
        select(
            func.min(OHLCVDaily.trade_date),
            func.max(OHLCVDaily.trade_date),
            func.count(OHLCVDaily.id),
        ).where(OHLCVDaily.ticker_id.in_(ticker_ids))
    )
    row = ohlcv_stats.one()
    ohlcv_min, ohlcv_max, ohlcv_count = row[0], row[1], row[2]

    diag["bars_available"] = {
        "min_date": ohlcv_min.isoformat() if ohlcv_min else None,
        "max_date": ohlcv_max.isoformat() if ohlcv_max else None,
        "total_rows": ohlcv_count or 0,
    }

    if ohlcv_count == 0:
        diag["reasons"].append("No OHLCV data found for any ticker. Run data import first.")
        return diag

    if ohlcv_min and ohlcv_max:
        if date_to < ohlcv_min or date_from > ohlcv_max:
            diag["reasons"].append(
                f"Requested date range {date_from} to {date_to} does not overlap "
                f"with available OHLCV data ({ohlcv_min} to {ohlcv_max})."
            )

    # Count bars within the requested range
    bars_in_range = await db.execute(
        select(func.count(OHLCVDaily.id)).where(
            OHLCVDaily.ticker_id.in_(ticker_ids),
            OHLCVDaily.trade_date >= date_from,
            OHLCVDaily.trade_date <= date_to,
        )
    )
    bars_count = bars_in_range.scalar() or 0
    if bars_count == 0:
        diag["reasons"].append(
            f"No OHLCV bars exist between {date_from} and {date_to}. "
            f"Data available from {ohlcv_min} to {ohlcv_max}."
        )

    return diag


# ---------------------------------------------------------------------------
# Background engine
# ---------------------------------------------------------------------------

async def _run_backtest_background(run_id: int):
    """Main backtest engine — runs in background task.

    Signal generation: computes indicators on-the-fly from OHLCV data for each
    ticker/date pair in the backtest window. This ensures we don't depend on
    pre-computed indicator rows in the DB.
    """
    try:
        async with async_session_factory() as db:
            run = await db.get(BacktestRun, run_id)
            if not run:
                return
            run.status = "running"
            await db.commit()

            config = run.config
            date_from = run.date_from
            date_to = run.date_to
            min_score = config.get("min_score", 60)
            target_pct = config.get("target_pct", 5.0)
            target_days = config.get("target_days", 20)
            max_dd_pct = config.get("max_drawdown_pct", -3.0)
            weight_overrides = config.get("weights")
            ticker_filter = config.get("tickers")
            exchange_groups = config.get("exchange_groups", ["US"])
            walk_forward_cfg = config.get("walk_forward")
            portfolio_cfg = config.get("portfolio", {})

            # ---- Resolve tickers ----
            ticker_q = select(Ticker).where(Ticker.active == True)  # noqa: E712
            if ticker_filter:
                ticker_q = ticker_q.where(Ticker.symbol.in_(ticker_filter))
            elif exchange_groups:
                ticker_q = ticker_q.where(Ticker.exchange_group.in_(exchange_groups))
            tickers = list((await db.execute(ticker_q)).scalars().all())

            ticker_map = {t.id: t for t in tickers}
            ticker_ids = list(ticker_map.keys())

            # ---- Preflight diagnostics ----
            diag = await _run_preflight(db, ticker_ids, date_from, date_to, min_score)

            if not tickers:
                run.status = "failed"
                run.results = {"error": "No tickers found for the given filters"}
                run.diagnostics = diag
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            if diag["bars_available"]["total_rows"] == 0:
                run.status = "failed"
                run.results = {"error": "No OHLCV data available. Run data import first."}
                run.diagnostics = diag
                run.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # ---- Update progress ----
            run.results = {"progress": f"Loading data for {len(tickers)} tickers..."}
            await db.commit()

            # ---- Load OHLCV cache ----
            # We need bars from well before date_from (for indicator context, e.g. SMA200)
            # through date_to + target_days (for outcome evaluation)
            ohlcv_start = date_from - timedelta(days=365)  # 1 year before for SMA200 context
            ohlcv_end = date_to + timedelta(days=int(target_days * 2))
            ohlcv_q = (
                select(OHLCVDaily)
                .where(
                    OHLCVDaily.ticker_id.in_(ticker_ids),
                    OHLCVDaily.trade_date >= ohlcv_start,
                    OHLCVDaily.trade_date <= ohlcv_end,
                )
                .order_by(OHLCVDaily.ticker_id, OHLCVDaily.trade_date)
            )
            ohlcv_rows = list((await db.execute(ohlcv_q)).scalars().all())
            ohlcv_by_ticker: dict[int, list[OHLCVDaily]] = {}
            for bar in ohlcv_rows:
                ohlcv_by_ticker.setdefault(bar.ticker_id, []).append(bar)

            # ---- Generate signals by computing indicators on-the-fly ----
            run.results = {"progress": "Computing indicators & generating signals..."}
            await db.commit()

            all_signals_data = []
            all_scores: list[float] = []  # Track all scores for diagnostics
            processed_ticker_dates = 0
            total_tickers = len(tickers)

            for ticker_idx, ticker in enumerate(tickers):
                # Yield to event loop every ticker to keep server responsive
                if ticker_idx % 2 == 0:
                    await asyncio.sleep(0)

                bars = ohlcv_by_ticker.get(ticker.id, [])
                if not bars:
                    continue

                ohlcv_df = _build_ohlcv_df(bars)
                if ohlcv_df.empty or len(ohlcv_df) < MIN_BARS_FOR_INDICATORS:
                    continue

                # Get all trading dates in the backtest window for this ticker
                window_dates = ohlcv_df[
                    (ohlcv_df["date"] >= date_from) & (ohlcv_df["date"] <= date_to)
                ]["date"].tolist()

                for td in window_dates:
                    # Slice OHLCV up to this date (no lookahead)
                    df_slice = ohlcv_df[ohlcv_df["date"] <= td].copy()
                    if len(df_slice) < MIN_BARS_FOR_INDICATORS:
                        continue

                    # Compute indicators on-the-fly
                    try:
                        indicators = compute_all_indicators(df_slice)
                    except Exception:
                        continue
                    if not indicators:
                        continue

                    # Score the signal
                    result = compute_signal_with_overrides(indicators, df_slice, weight_overrides)
                    all_scores.append(result.score)
                    processed_ticker_dates += 1

                    if result.score >= min_score:
                        entry_price = df_slice.iloc[-1]["close"]
                        if not entry_price or entry_price <= 0:
                            continue

                        target_price = entry_price * (1 + target_pct / 100)
                        stop_price = entry_price * (1 + max_dd_pct / 100)

                        all_signals_data.append({
                            "backtest_run_id": run_id,
                            "ticker_id": ticker.id,
                            "signal_date": td,
                            "score": result.score,
                            "entry_price": round(entry_price, 4),
                            "target_price": round(target_price, 4),
                            "stop_price": round(stop_price, 4),
                        })

                # Update progress and yield event loop periodically
                if (ticker_idx + 1) % 5 == 0 or ticker_idx == total_tickers - 1:
                    run.results = {
                        "progress": f"Scored {ticker_idx + 1}/{total_tickers} tickers, "
                        f"{len(all_signals_data)} signals found..."
                    }
                    await db.commit()
                    await asyncio.sleep(0)  # Yield to event loop

            # ---- Update diagnostics with signal info ----
            diag["signals_computed"] = processed_ticker_dates
            diag["signals_meeting_threshold"] = len(all_signals_data)
            if all_scores:
                diag["max_signal_score_in_range"] = round(max(all_scores), 2)
                diag["min_signal_score_in_range"] = round(min(all_scores), 2)

            if len(all_signals_data) == 0 and all_scores:
                max_score = max(all_scores)
                diag["reasons"].append(
                    f"No signals met min_score={min_score}. "
                    f"Max score in range was {max_score:.1f}. "
                    f"Lower min_score or adjust weight parameters."
                )
            elif len(all_signals_data) == 0 and not all_scores:
                diag["reasons"].append(
                    "Could not compute any indicator scores. "
                    "Ensure OHLCV data covers the backtest period with sufficient history."
                )

            run.diagnostics = diag

            # ---- Bulk insert signals ----
            run.results = {"progress": f"Inserting {len(all_signals_data)} signals..."}
            await db.commit()

            backtest_signals = []
            for sd in all_signals_data:
                sig = BacktestSignal(**sd)
                db.add(sig)
                backtest_signals.append(sig)
            await db.flush()

            # ---- Evaluate outcomes ----
            run.results = {"progress": "Evaluating signal outcomes..."}
            await db.commit()

            for sig in backtest_signals:
                _evaluate_backtest_signal(
                    sig,
                    ohlcv_by_ticker.get(sig.ticker_id, []),
                    target_pct,
                    target_days,
                    max_dd_pct,
                )
            await db.flush()

            # ---- Walk-forward split ----
            window_metrics = {}
            if walk_forward_cfg:
                total_days = (date_to - date_from).days
                train_end = date_from + timedelta(days=int(total_days * walk_forward_cfg.get("train_pct", 60) / 100))
                val_end = train_end + timedelta(days=int(total_days * walk_forward_cfg.get("validation_pct", 20) / 100))

                train_sigs = [s for s in backtest_signals if s.signal_date < train_end]
                val_sigs = [s for s in backtest_signals if train_end <= s.signal_date < val_end]
                oos_sigs = [s for s in backtest_signals if s.signal_date >= val_end]

                window_metrics["train"] = _compute_signal_metrics(train_sigs)
                window_metrics["validation"] = _compute_signal_metrics(val_sigs)
                window_metrics["oos"] = _compute_signal_metrics(oos_sigs)

            # ---- Portfolio simulation ----
            run.results = {"progress": "Running portfolio simulation..."}
            await db.commit()

            equity_curve, port_metrics = _run_portfolio_simulation(
                backtest_signals, ohlcv_by_ticker, portfolio_cfg, target_pct, target_days, max_dd_pct
            )

            sim = PortfolioSimulation(
                backtest_run_id=run_id,
                config=portfolio_cfg,
                equity_curve=equity_curve,
                metrics=port_metrics,
            )
            db.add(sim)

            # ---- Compute aggregate results ----
            overall_metrics = _compute_signal_metrics(backtest_signals)
            p_value = _bootstrap_p_value(backtest_signals)
            overall_metrics["p_value"] = p_value
            overall_metrics["portfolio"] = port_metrics

            if window_metrics:
                overall_metrics["walk_forward"] = window_metrics
                oos = window_metrics.get("oos", {})
                overall_metrics["oos_win_rate"] = oos.get("win_rate")
                overall_metrics["oos_sharpe"] = port_metrics.get("sharpe_ratio")

            run.results = overall_metrics
            run.status = "completed"
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"Backtest {run_id} completed: {overall_metrics.get('total_trades', 0)} trades")

    except Exception as e:
        logger.error(f"Backtest {run_id} failed: {e}", exc_info=True)
        try:
            async with async_session_factory() as db:
                run = await db.get(BacktestRun, run_id)
                if run:
                    run.status = "failed"
                    run.results = {"error": str(e)}
                    run.finished_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Signal outcome evaluation (adapted from outcome_tracker)
# ---------------------------------------------------------------------------

def _evaluate_backtest_signal(
    sig: BacktestSignal,
    ohlcv_bars: list[OHLCVDaily],
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
):
    """Evaluate a single backtest signal outcome using OHLCV data."""
    entry_price = float(sig.entry_price) if sig.entry_price else None
    if not entry_price:
        sig.outcome = "no_data"
        return

    signal_date = sig.signal_date
    window_end = signal_date + timedelta(days=int(target_days * 1.5))

    # Get bars after signal date within the window
    future_bars = [
        b for b in ohlcv_bars
        if b.trade_date > signal_date and b.trade_date <= window_end
    ]

    if not future_bars:
        sig.outcome = "no_data"
        return

    max_drawdown = 0.0
    peak = entry_price

    for i, bar in enumerate(future_bars):
        price = _dec(bar.close)
        low = _dec(bar.low)
        if not price:
            continue
        if not low:
            low = price

        if price > peak:
            peak = price
        dd = (low - peak) / peak * 100
        if dd < max_drawdown:
            max_drawdown = dd

        # Check stop loss
        if max_drawdown < max_dd_pct:
            actual_return = (price - entry_price) / entry_price * 100
            sig.outcome = "loss"
            sig.actual_return = round(actual_return, 4)
            sig.days_held = i + 1
            sig.max_drawdown = round(max_drawdown, 4)
            return

        # Check target hit
        return_pct = (price - entry_price) / entry_price * 100
        if return_pct >= target_pct:
            sig.outcome = "win"
            sig.actual_return = round(return_pct, 4)
            sig.days_held = i + 1
            sig.max_drawdown = round(max_drawdown, 4)
            return

    # Time expired
    final_price = _dec(future_bars[-1].close) or entry_price
    actual_return = (final_price - entry_price) / entry_price * 100
    sig.outcome = "timeout"
    sig.actual_return = round(actual_return, 4)
    sig.days_held = len(future_bars)
    sig.max_drawdown = round(max_drawdown, 4)


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def _compute_signal_metrics(signals: list[BacktestSignal]) -> dict:
    """Compute aggregate metrics from a list of evaluated signals."""
    evaluated = [s for s in signals if s.outcome and s.outcome not in ("no_data",)]
    if not evaluated:
        return {"total_trades": 0, "win_rate": 0, "avg_return": 0}

    total = len(evaluated)
    wins = [s for s in evaluated if s.outcome == "win"]
    losses = [s for s in evaluated if s.outcome == "loss"]
    timeouts = [s for s in evaluated if s.outcome == "timeout"]

    returns = [float(s.actual_return) for s in evaluated if s.actual_return is not None]
    win_returns = [float(s.actual_return) for s in wins if s.actual_return is not None]
    loss_returns = [float(s.actual_return) for s in losses if s.actual_return is not None]
    days = [s.days_held for s in evaluated if s.days_held is not None]

    avg_return = np.mean(returns) if returns else 0
    avg_win = np.mean(win_returns) if win_returns else 0
    avg_loss = np.mean(loss_returns) if loss_returns else 0
    win_rate = len(wins) / total if total else 0
    loss_rate = len(losses) / total if total else 0

    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    expectancy = (avg_win * win_rate) - (abs(avg_loss) * loss_rate)

    return {
        "total_trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate": round(win_rate, 4),
        "avg_return": round(float(avg_return), 4),
        "avg_win": round(float(avg_win), 4),
        "avg_loss": round(float(avg_loss), 4),
        "profit_factor": round(float(profit_factor), 4) if profit_factor != float("inf") else None,
        "expectancy": round(float(expectancy), 4),
        "avg_days_held": round(float(np.mean(days)), 1) if days else 0,
        "total_return": round(float(sum(returns)), 4) if returns else 0,
    }


def _bootstrap_p_value(signals: list[BacktestSignal], n_iterations: int = 1000) -> float | None:
    """Bootstrap test: is the win rate significantly better than random?"""
    evaluated = [s for s in signals if s.outcome and s.outcome not in ("no_data",)]
    if len(evaluated) < 10:
        return None

    actual_win_rate = sum(1 for s in evaluated if s.outcome == "win") / len(evaluated)
    outcomes = [1 if s.outcome == "win" else 0 for s in evaluated]

    beat_count = 0
    for _ in range(n_iterations):
        shuffled = random.choices(outcomes, k=len(outcomes))
        if np.mean(shuffled) >= actual_win_rate:
            beat_count += 1

    return round(beat_count / n_iterations, 4)


# ---------------------------------------------------------------------------
# Portfolio simulation
# ---------------------------------------------------------------------------

def _run_portfolio_simulation(
    signals: list[BacktestSignal],
    ohlcv_cache: dict[int, list[OHLCVDaily]],
    portfolio_cfg: dict,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
) -> tuple[list[dict], dict]:
    """Simulate portfolio management with position sizing.

    Returns (equity_curve, metrics).
    """
    starting_capital = portfolio_cfg.get("starting_capital", 10000)
    max_positions = portfolio_cfg.get("max_positions", 5)
    position_size_pct = portfolio_cfg.get("position_size_pct", 20)

    # Sort signals by date
    sorted_signals = sorted(
        [s for s in signals if s.outcome and s.outcome != "no_data"],
        key=lambda s: s.signal_date,
    )

    if not sorted_signals:
        return [], {"sharpe_ratio": 0, "cagr": 0, "max_drawdown": 0, "total_return": 0}

    # Build a date-indexed price lookup for all tickers
    price_lookup: dict[int, dict[date, float]] = {}
    for tid, bars in ohlcv_cache.items():
        price_lookup[tid] = {}
        for b in bars:
            c = _dec(b.close)
            if c:
                price_lookup[tid][b.trade_date] = c

    equity = starting_capital
    cash = starting_capital
    positions: list[dict] = []  # Active positions
    equity_curve: list[dict] = []
    daily_returns: list[float] = []
    peak_equity = starting_capital
    max_dd = 0.0

    # Get all trading days in range
    all_dates: set[date] = set()
    for tid_prices in price_lookup.values():
        all_dates.update(tid_prices.keys())
    if not all_dates:
        return [], {"sharpe_ratio": 0, "cagr": 0, "max_drawdown": 0, "total_return": 0}

    first_date = sorted_signals[0].signal_date
    last_date = max(all_dates)
    trading_days = sorted(d for d in all_dates if first_date <= d <= last_date)

    if not trading_days:
        return [], {"sharpe_ratio": 0, "cagr": 0, "max_drawdown": 0, "total_return": 0}

    # Index signals by date for fast lookup
    signals_by_date: dict[date, list[BacktestSignal]] = {}
    for s in sorted_signals:
        signals_by_date.setdefault(s.signal_date, []).append(s)

    prev_equity = starting_capital

    for day in trading_days:
        # Check exits for existing positions
        closed_positions = []
        for pos in positions:
            price = price_lookup.get(pos["ticker_id"], {}).get(day)
            if not price:
                continue

            pos["current_price"] = price
            pos["days_held"] += 1
            pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100

            # Track position drawdown
            if price > pos["peak_price"]:
                pos["peak_price"] = price
            pos_dd = (price - pos["peak_price"]) / pos["peak_price"] * 100

            should_exit = False
            if pnl_pct >= target_pct:
                should_exit = True
            elif pos_dd < max_dd_pct:
                should_exit = True
            elif pos["days_held"] >= target_days:
                should_exit = True

            if should_exit:
                cash += pos["shares"] * price
                closed_positions.append(pos)

        for cp in closed_positions:
            positions.remove(cp)

        # Enter new positions
        day_signals = signals_by_date.get(day, [])
        # Sort by score descending — best signals first
        day_signals.sort(key=lambda s: float(s.score or 0), reverse=True)

        for sig in day_signals:
            if len(positions) >= max_positions:
                break
            entry_price = price_lookup.get(sig.ticker_id, {}).get(day)
            if not entry_price or entry_price <= 0:
                continue

            # Position size based on current equity
            current_equity = cash + sum(
                p["shares"] * price_lookup.get(p["ticker_id"], {}).get(day, p["entry_price"])
                for p in positions
            )
            alloc = current_equity * (position_size_pct / 100)
            shares = int(alloc / entry_price)
            if shares <= 0:
                continue
            cost = shares * entry_price
            if cost > cash:
                shares = int(cash / entry_price)
                if shares <= 0:
                    continue
                cost = shares * entry_price

            cash -= cost
            positions.append({
                "ticker_id": sig.ticker_id,
                "entry_price": entry_price,
                "current_price": entry_price,
                "peak_price": entry_price,
                "shares": shares,
                "days_held": 0,
            })

        # Calculate end-of-day equity
        position_value = sum(
            p["shares"] * price_lookup.get(p["ticker_id"], {}).get(day, p["current_price"])
            for p in positions
        )
        equity = cash + position_value

        # Track daily return
        if prev_equity > 0:
            daily_ret = (equity - prev_equity) / prev_equity
            daily_returns.append(daily_ret)
        prev_equity = equity

        # Track drawdown
        if equity > peak_equity:
            peak_equity = equity
        dd = (equity - peak_equity) / peak_equity * 100
        if dd < max_dd:
            max_dd = dd

        equity_curve.append({
            "date": day.isoformat(),
            "equity": round(equity, 2),
            "positions": len(positions),
        })

    # Compute portfolio-level metrics
    total_return = (equity - starting_capital) / starting_capital * 100
    n_days = len(trading_days)
    years = n_days / 252 if n_days > 0 else 1

    if daily_returns:
        mean_daily = np.mean(daily_returns)
        std_daily = np.std(daily_returns)
        sharpe = (mean_daily / std_daily) * np.sqrt(252) if std_daily > 0 else 0
    else:
        sharpe = 0

    cagr = ((equity / starting_capital) ** (1 / years) - 1) * 100 if years > 0 and equity > 0 else 0

    metrics = {
        "starting_capital": starting_capital,
        "final_equity": round(equity, 2),
        "total_return": round(total_return, 2),
        "cagr": round(float(cagr), 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "max_drawdown": round(max_dd, 2),
        "trading_days": n_days,
    }

    return equity_curve, metrics
