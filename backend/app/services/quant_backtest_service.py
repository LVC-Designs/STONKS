"""Quant backtest engine — disciplined train/val/OOS framework.

Architecture:
- Signal source: computed on-the-fly from OHLCV via compute_all_indicators().
  This avoids dependency on pre-computed indicator rows and ensures consistency.
- Workflow: optimize on TRAIN only → select top K → evaluate on VAL → pick winner → run OOS.
- Walk-forward: rolls windows forward by step_months, aggregates across folds.
- Stability score penalizes overfitting, low trade counts, and cross-split degradation.

Default split settings (daily swing trading):
  Train: 12 months, Validation: 6 months, OOS: 6 months, Step: 3 months.
"""

import asyncio
import logging
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import product

import numpy as np
import pandas as pd
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.quant_backtest import QuantBacktest, QuantBacktestCandidate
from app.models.ohlcv import OHLCVDaily
from app.models.ticker import Ticker
from app.indicators.compute_all import compute_all_indicators
from app.services.backtest_scoring import compute_signal_with_overrides

logger = logging.getLogger(__name__)

MIN_BARS_FOR_INDICATORS = 50
MIN_TRADES_STAT = 30  # below this, results are "statistically weak"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(val) -> float | None:
    if val is None:
        return None
    return float(val)


def _build_ohlcv_df(bars: list[OHLCVDaily]) -> pd.DataFrame:
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


def _months_delta(d: date, months: int) -> date:
    """Add months to a date (approximate: 30.44 days/month)."""
    return d + timedelta(days=int(months * 30.44))


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

async def create_quant_backtest(db: AsyncSession, config: dict) -> QuantBacktest:
    """Create a QuantBacktest row and launch engine in background."""
    mode = config.get("mode", "split")
    name = config.pop("name", None)

    qb = QuantBacktest(
        name=name or f"Quant {'Walk-Forward' if mode == 'walk_forward' else 'Split'} Sweep",
        mode=mode,
        status="pending",
        config=config,
        objective=config.get("objective", "robust_composite"),
        candidates_count=0,
    )
    db.add(qb)
    await db.flush()
    qb_id = qb.id
    await db.commit()

    asyncio.create_task(_run_quant_backtest(qb_id))
    return qb


async def list_quant_backtests(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    q = select(QuantBacktest).order_by(QuantBacktest.created_at.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    total = (await db.execute(select(func.count(QuantBacktest.id)))).scalar() or 0
    rows = list((await db.execute(q)).scalars().all())
    items = []
    for r in rows:
        items.append(_qb_to_dict(r))
    return items, total


async def get_quant_backtest_detail(db: AsyncSession, qb_id: int) -> dict | None:
    qb = await db.get(QuantBacktest, qb_id)
    if not qb:
        return None
    # Load candidates
    cands = list((await db.execute(
        select(QuantBacktestCandidate)
        .where(QuantBacktestCandidate.quant_backtest_id == qb_id)
        .order_by(QuantBacktestCandidate.rank.asc().nulls_last())
    )).scalars().all())
    d = _qb_to_dict(qb)
    d["candidates"] = [_cand_to_dict(c) for c in cands]
    return d


async def delete_quant_backtest(db: AsyncSession, qb_id: int) -> bool:
    qb = await db.get(QuantBacktest, qb_id)
    if not qb:
        return False
    await db.execute(
        delete(QuantBacktestCandidate).where(QuantBacktestCandidate.quant_backtest_id == qb_id)
    )
    await db.delete(qb)
    await db.commit()
    return True


def _qb_to_dict(qb: QuantBacktest) -> dict:
    return {
        "id": qb.id,
        "name": qb.name,
        "mode": qb.mode,
        "status": qb.status,
        "config": qb.config,
        "selected_config": qb.selected_config,
        "objective": qb.objective,
        "stability_score": float(qb.stability_score) if qb.stability_score else None,
        "results": qb.results,
        "diagnostics": qb.diagnostics,
        "warnings": qb.warnings,
        "candidates_count": qb.candidates_count or 0,
        "progress": qb.progress,
        "created_at": qb.created_at,
        "finished_at": qb.finished_at,
    }


def _cand_to_dict(c: QuantBacktestCandidate) -> dict:
    return {
        "id": c.id,
        "config": c.config,
        "rank": c.rank,
        "train_metrics": c.train_metrics,
        "train_objective": float(c.train_objective) if c.train_objective else None,
        "val_metrics": c.val_metrics,
        "val_objective": float(c.val_objective) if c.val_objective else None,
        "oos_metrics": c.oos_metrics,
        "stability_score": float(c.stability_score) if c.stability_score else None,
        "is_selected": c.is_selected,
        "fold_metrics": c.fold_metrics,
        "equity_curve": c.equity_curve,
        "warnings": c.warnings,
        "diagnostics": c.diagnostics,
    }


# ---------------------------------------------------------------------------
# Generate splits for walk-forward mode
# ---------------------------------------------------------------------------

def _generate_walk_forward_folds(
    date_from: date, date_to: date, wf: dict,
) -> list[dict]:
    """Generate rolling window folds.

    Returns list of {fold, date_from_train, date_to_train,
                     date_from_val, date_to_val, date_from_oos, date_to_oos}.
    """
    train_m = wf.get("window_train_months", 12)
    val_m = wf.get("window_val_months", 3)
    oos_m = wf.get("window_oos_months", 3)
    step_m = wf.get("step_months", 3)
    total_window = train_m + val_m + oos_m

    folds = []
    fold_idx = 0
    cursor = date_from
    while True:
        train_start = cursor
        train_end = _months_delta(train_start, train_m) - timedelta(days=1)
        val_start = _months_delta(train_start, train_m)
        val_end = _months_delta(train_start, train_m + val_m) - timedelta(days=1)
        oos_start = _months_delta(train_start, train_m + val_m)
        oos_end = _months_delta(train_start, total_window) - timedelta(days=1)

        if oos_end > date_to:
            break

        folds.append({
            "fold": fold_idx,
            "date_from_train": train_start,
            "date_to_train": train_end,
            "date_from_val": val_start,
            "date_to_val": val_end,
            "date_from_oos": oos_start,
            "date_to_oos": oos_end,
        })
        fold_idx += 1
        cursor = _months_delta(cursor, step_m)

    return folds


# ---------------------------------------------------------------------------
# Pre-computation: compute indicators + scores ONCE per ticker×date
# ---------------------------------------------------------------------------

def _precompute_score_table(
    ohlcv_by_ticker: dict[int, pd.DataFrame],
    date_from: date,
    date_to: date,
    weight_overrides: dict | None = None,
) -> list[dict]:
    """Pre-compute scores for all ticker×date combos in a date range.

    Returns a list of dicts, each with:
      ticker_id, signal_date, score, entry_price
    This is computed ONCE and reused across all parameter combos.
    """
    score_table: list[dict] = []

    for ticker_id, ohlcv_df in ohlcv_by_ticker.items():
        if ohlcv_df.empty or len(ohlcv_df) < MIN_BARS_FOR_INDICATORS:
            continue

        window_dates = ohlcv_df[
            (ohlcv_df["date"] >= date_from) & (ohlcv_df["date"] <= date_to)
        ]["date"].tolist()

        if not window_dates:
            continue

        for td in window_dates:
            df_slice = ohlcv_df[ohlcv_df["date"] <= td].copy()
            if len(df_slice) < MIN_BARS_FOR_INDICATORS:
                continue

            try:
                indicators = compute_all_indicators(df_slice)
            except Exception:
                continue
            if not indicators:
                continue

            result = compute_signal_with_overrides(indicators, df_slice, weight_overrides)
            entry_price = float(df_slice.iloc[-1]["close"])
            if not entry_price or entry_price <= 0:
                continue

            score_table.append({
                "ticker_id": ticker_id,
                "signal_date": td,
                "score": result.score,
                "entry_price": round(entry_price, 4),
            })

    logger.info(
        f"Pre-computed {len(score_table)} scores for "
        f"{date_from} to {date_to}"
    )
    return score_table


def _apply_combo_to_score_table(
    score_table: list[dict],
    ohlcv_by_ticker: dict[int, pd.DataFrame],
    min_score: float,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
) -> tuple[list[dict], list[float], dict]:
    """Apply a parameter combo to a pre-computed score table.

    Filters by min_score, evaluates outcomes. Much faster than recomputing
    indicators — just lookups and outcome evaluation.
    """
    signals = []
    all_scores = [row["score"] for row in score_table]
    diag = {
        "tickers_scored": len(set(r["ticker_id"] for r in score_table)),
        "dates_scored": len(score_table),
        "signals_above_threshold": 0,
        "max_score": round(max(all_scores), 2) if all_scores else None,
        "min_score": round(min(all_scores), 2) if all_scores else None,
        "reasons": [],
    }

    for row in score_table:
        if row["score"] < min_score:
            continue

        entry_price = row["entry_price"]
        target_price = entry_price * (1 + target_pct / 100)
        stop_price = entry_price * (1 + max_dd_pct / 100)

        ohlcv_df = ohlcv_by_ticker.get(row["ticker_id"])
        if ohlcv_df is None:
            continue

        outcome, actual_return, days_held, max_drawdown = _evaluate_signal(
            ohlcv_df, row["signal_date"], entry_price,
            target_pct, target_days, max_dd_pct,
        )

        signals.append({
            "ticker_id": row["ticker_id"],
            "signal_date": row["signal_date"],
            "score": row["score"],
            "entry_price": entry_price,
            "target_price": round(target_price, 4),
            "stop_price": round(stop_price, 4),
            "outcome": outcome,
            "actual_return": actual_return,
            "days_held": days_held,
            "max_drawdown": max_drawdown,
        })
        diag["signals_above_threshold"] += 1

    if not all_scores:
        diag["reasons"].append("No indicators could be computed. Check OHLCV coverage.")
    elif diag["signals_above_threshold"] == 0:
        diag["reasons"].append(
            f"No signals met min_score={min_score}. "
            f"Max score was {diag['max_score']}. Lower min_score or adjust weights."
        )

    return signals, all_scores, diag


# Keep the old function for non-quant backtests that call it
def _generate_signals_for_range(
    ohlcv_by_ticker: dict[int, pd.DataFrame],
    ticker_map: dict[int, object],
    date_from: date,
    date_to: date,
    min_score: float,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
    weight_overrides: dict | None = None,
) -> tuple[list[dict], list[float], dict]:
    """Generate and evaluate signals for a date range (legacy, used by non-quant backtests)."""
    score_table = _precompute_score_table(
        ohlcv_by_ticker, date_from, date_to, weight_overrides,
    )
    return _apply_combo_to_score_table(
        score_table, ohlcv_by_ticker,
        min_score, target_pct, target_days, max_dd_pct,
    )


def _evaluate_signal(
    ohlcv_df: pd.DataFrame,
    signal_date: date,
    entry_price: float,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
) -> tuple[str, float | None, int | None, float | None]:
    """Evaluate signal outcome from OHLCV DataFrame."""
    future = ohlcv_df[ohlcv_df["date"] > signal_date].head(int(target_days * 1.5))
    if future.empty:
        return "no_data", None, None, None

    peak = entry_price
    max_drawdown = 0.0

    for i, (_, row) in enumerate(future.iterrows()):
        price = float(row["close"])
        low = float(row["low"]) if row["low"] else price

        if price > peak:
            peak = price
        dd = (low - peak) / peak * 100
        if dd < max_drawdown:
            max_drawdown = dd

        # Stop loss hit
        if max_drawdown < max_dd_pct:
            ret = (price - entry_price) / entry_price * 100
            return "loss", round(ret, 4), i + 1, round(max_drawdown, 4)

        # Target hit
        ret_pct = (price - entry_price) / entry_price * 100
        if ret_pct >= target_pct:
            return "win", round(ret_pct, 4), i + 1, round(max_drawdown, 4)

    # Time expired
    final = float(future.iloc[-1]["close"])
    ret = (final - entry_price) / entry_price * 100
    return "timeout", round(ret, 4), len(future), round(max_drawdown, 4)


# ---------------------------------------------------------------------------
# Extended metrics computation
# ---------------------------------------------------------------------------

def _compute_extended_metrics(
    signals: list[dict],
    ohlcv_by_ticker: dict[int, pd.DataFrame],
    portfolio_cfg: dict,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
    date_from: date,
    date_to: date,
) -> dict:
    """Compute comprehensive performance metrics for a set of signals.

    Returns dict with: trades, win_rate, avg_return, expectancy, profit_factor,
    max_drawdown, calmar, sharpe, sortino, volatility, exposure, avg_hold_days,
    best/worst trade, p_value, final_equity, cagr.
    """
    evaluated = [s for s in signals if s.get("outcome") and s["outcome"] != "no_data"]
    if not evaluated:
        return _empty_metrics()

    total = len(evaluated)
    wins = [s for s in evaluated if s["outcome"] == "win"]
    losses = [s for s in evaluated if s["outcome"] == "loss"]
    timeouts = [s for s in evaluated if s["outcome"] == "timeout"]

    returns = [s["actual_return"] for s in evaluated if s["actual_return"] is not None]
    win_returns = [s["actual_return"] for s in wins if s["actual_return"] is not None]
    loss_returns = [s["actual_return"] for s in losses if s["actual_return"] is not None]
    days_list = [s["days_held"] for s in evaluated if s["days_held"] is not None]

    win_rate = len(wins) / total if total else 0
    loss_rate = len(losses) / total if total else 0
    avg_return = float(np.mean(returns)) if returns else 0
    avg_win = float(np.mean(win_returns)) if win_returns else 0
    avg_loss = float(np.mean(loss_returns)) if loss_returns else 0
    expectancy = (avg_win * win_rate) - (abs(avg_loss) * loss_rate)

    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    avg_hold_days = float(np.mean(days_list)) if days_list else 0
    best_trade = max(returns) if returns else None
    worst_trade = min(returns) if returns else None

    # Volatility & ratios from returns
    vol = float(np.std(returns)) if len(returns) > 1 else 0
    sharpe = avg_return / vol if vol > 0 else 0

    # Sortino: use downside deviation
    neg_returns = [r for r in returns if r < 0]
    downside_dev = float(np.std(neg_returns)) if len(neg_returns) > 1 else 0
    sortino = avg_return / downside_dev if downside_dev > 0 else None

    # Portfolio simulation for drawdown, equity, CAGR
    equity_data = _simulate_portfolio(
        evaluated, ohlcv_by_ticker, portfolio_cfg, target_pct, target_days, max_dd_pct
    )
    max_dd = equity_data["max_drawdown"]
    final_eq = equity_data["final_equity"]
    start_cap = portfolio_cfg.get("starting_capital", 10000)
    total_ret = (final_eq - start_cap) / start_cap * 100 if start_cap > 0 else 0
    n_days = (date_to - date_from).days
    years = n_days / 365.25 if n_days > 0 else 1
    cagr = ((final_eq / start_cap) ** (1 / years) - 1) * 100 if years > 0 and final_eq > 0 else 0

    calmar = abs(cagr / max_dd) if max_dd < 0 else None

    # Exposure: fraction of days with open positions
    total_days_in_market = sum(s["days_held"] for s in evaluated if s["days_held"])
    trading_days_in_range = max(n_days * 252 / 365.25, 1)  # approximate
    exposure = min(total_days_in_market / trading_days_in_range * 100, 100)

    # Bootstrap p-value
    p_value = _bootstrap_p_value(evaluated)

    return {
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate": round(win_rate, 4),
        "avg_return": round(avg_return, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "total_return": round(total_ret, 2),
        "max_drawdown": round(max_dd, 2),
        "calmar_ratio": round(calmar, 4) if calmar is not None else None,
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4) if sortino is not None else None,
        "volatility": round(vol, 4),
        "exposure_pct": round(exposure, 1),
        "avg_hold_days": round(avg_hold_days, 1),
        "best_trade": round(best_trade, 4) if best_trade is not None else None,
        "worst_trade": round(worst_trade, 4) if worst_trade is not None else None,
        "p_value": p_value,
        "final_equity": round(final_eq, 2),
        "cagr": round(cagr, 2),
        "equity_curve": equity_data.get("equity_curve", []),
    }


def _empty_metrics() -> dict:
    return {
        "trades": 0, "wins": 0, "losses": 0, "timeouts": 0,
        "win_rate": 0, "avg_return": 0, "avg_win": 0, "avg_loss": 0,
        "expectancy": 0, "profit_factor": None, "total_return": 0,
        "max_drawdown": 0, "calmar_ratio": None, "sharpe": 0,
        "sortino": None, "volatility": 0, "exposure_pct": 0,
        "avg_hold_days": 0, "best_trade": None, "worst_trade": None,
        "p_value": None, "final_equity": None, "cagr": None,
        "equity_curve": [],
    }


def _simulate_portfolio(
    signals: list[dict],
    ohlcv_by_ticker: dict[int, pd.DataFrame],
    portfolio_cfg: dict,
    target_pct: float,
    target_days: int,
    max_dd_pct: float,
) -> dict:
    """Simplified portfolio simulation returning equity curve + metrics."""
    start_cap = portfolio_cfg.get("starting_capital", 10000)
    max_pos = portfolio_cfg.get("max_positions", 5)
    pos_pct = portfolio_cfg.get("position_size_pct", 20)

    sorted_sigs = sorted(
        [s for s in signals if s.get("outcome") and s["outcome"] != "no_data"],
        key=lambda s: s["signal_date"],
    )
    if not sorted_sigs:
        return {"final_equity": start_cap, "max_drawdown": 0, "equity_curve": []}

    # Build price lookup
    price_lookup: dict[int, dict[date, float]] = {}
    for tid, df in ohlcv_by_ticker.items():
        price_lookup[tid] = {}
        for _, row in df.iterrows():
            c = row["close"]
            if c and c > 0:
                price_lookup[tid][row["date"]] = float(c)

    all_dates: set[date] = set()
    for tid_prices in price_lookup.values():
        all_dates.update(tid_prices.keys())
    if not all_dates:
        return {"final_equity": start_cap, "max_drawdown": 0, "equity_curve": []}

    first = sorted_sigs[0]["signal_date"]
    last = max(all_dates)
    trading_days = sorted(d for d in all_dates if first <= d <= last)
    if not trading_days:
        return {"final_equity": start_cap, "max_drawdown": 0, "equity_curve": []}

    sigs_by_date: dict[date, list] = {}
    for s in sorted_sigs:
        sigs_by_date.setdefault(s["signal_date"], []).append(s)

    equity = start_cap
    cash = start_cap
    positions: list[dict] = []
    curve: list[dict] = []
    peak_eq = start_cap
    max_dd = 0.0
    prev_eq = start_cap

    for day in trading_days:
        # Exit logic
        closed = []
        for pos in positions:
            price = price_lookup.get(pos["tid"], {}).get(day)
            if not price:
                continue
            pos["days"] += 1
            pnl = (price - pos["entry"]) / pos["entry"] * 100
            if price > pos["peak"]:
                pos["peak"] = price
            pos_dd = (price - pos["peak"]) / pos["peak"] * 100
            if pnl >= target_pct or pos_dd < max_dd_pct or pos["days"] >= target_days:
                cash += pos["shares"] * price
                closed.append(pos)
        for cp in closed:
            positions.remove(cp)

        # Entry logic
        day_sigs = sigs_by_date.get(day, [])
        day_sigs.sort(key=lambda s: s.get("score", 0), reverse=True)
        for sig in day_sigs:
            if len(positions) >= max_pos:
                break
            ep = price_lookup.get(sig["ticker_id"], {}).get(day)
            if not ep or ep <= 0:
                continue
            alloc = equity * (pos_pct / 100)
            shares = int(alloc / ep)
            if shares <= 0:
                continue
            cost = shares * ep
            if cost > cash:
                shares = int(cash / ep)
                if shares <= 0:
                    continue
                cost = shares * ep
            cash -= cost
            positions.append({
                "tid": sig["ticker_id"], "entry": ep, "peak": ep,
                "shares": shares, "days": 0,
            })

        # Mark to market
        pos_val = sum(
            p["shares"] * price_lookup.get(p["tid"], {}).get(day, p["entry"])
            for p in positions
        )
        equity = cash + pos_val
        if equity > peak_eq:
            peak_eq = equity
        dd = (equity - peak_eq) / peak_eq * 100
        if dd < max_dd:
            max_dd = dd

        # Sample equity curve (every 5th day to keep size reasonable)
        if len(curve) == 0 or len(trading_days) < 200 or trading_days.index(day) % 3 == 0:
            curve.append({
                "date": day.isoformat(),
                "equity": round(equity, 2),
                "positions": len(positions),
            })

    return {"final_equity": equity, "max_drawdown": max_dd, "equity_curve": curve}


def _bootstrap_p_value(signals: list[dict], n_iter: int = 500) -> float | None:
    if len(signals) < 10:
        return None
    wins = sum(1 for s in signals if s.get("outcome") == "win")
    actual_wr = wins / len(signals)
    outcomes = [1 if s.get("outcome") == "win" else 0 for s in signals]
    beat = sum(1 for _ in range(n_iter) if np.mean(random.choices(outcomes, k=len(outcomes))) >= actual_wr)
    return round(beat / n_iter, 4)


# ---------------------------------------------------------------------------
# Objective function for ranking candidates
# ---------------------------------------------------------------------------

def _compute_objective(metrics: dict) -> float:
    """Robust composite objective for ranking parameter combos on TRAIN.

    Components (weighted):
    - 35% normalized return (capped at reasonable range)
    - 25% profit factor (capped)
    - 20% calmar ratio (capped)
    - 10% sharpe (capped)
    - 10% trade count adequacy

    Penalties applied for low trade counts.
    """
    if metrics.get("trades", 0) == 0:
        return 0.0

    # Normalize to 0-1 range with sensible caps
    total_ret = metrics.get("total_return", 0)
    norm_return = max(0, min(total_ret / 50, 1.0))  # 50% = perfect

    pf = metrics.get("profit_factor") or 0
    norm_pf = max(0, min(pf / 3.0, 1.0))  # 3.0 = excellent

    calmar = metrics.get("calmar_ratio") or 0
    norm_calmar = max(0, min(calmar / 3.0, 1.0))

    sharpe = metrics.get("sharpe", 0)
    norm_sharpe = max(0, min(sharpe / 5.0, 1.0))

    trades = metrics.get("trades", 0)
    norm_trades = min(trades / 100, 1.0)  # 100+ trades = full credit

    score = (
        0.35 * norm_return +
        0.25 * norm_pf +
        0.20 * norm_calmar +
        0.10 * norm_sharpe +
        0.10 * norm_trades
    )

    # Penalties
    if trades < MIN_TRADES_STAT:
        score *= 0.5  # Heavy penalty for statistically weak results

    max_dd = metrics.get("max_drawdown", 0)
    if max_dd < -30:
        score *= 0.3  # Severe drawdown penalty

    return round(score, 6)


# ---------------------------------------------------------------------------
# Stability score (0-100)
# ---------------------------------------------------------------------------

def _compute_stability_score(
    train_metrics: dict,
    val_metrics: dict,
    fold_metrics: list[dict] | None = None,
) -> float:
    """Compute stability score (0-100) measuring robustness.

    High score = consistent across splits. Penalizes:
    - Large performance drop train -> val
    - High variance across folds
    - Too few trades
    - Negative val performance
    """
    score = 100.0

    # 1. Train -> Val consistency (up to -40 points)
    train_wr = train_metrics.get("win_rate", 0)
    val_wr = val_metrics.get("win_rate", 0)
    if train_wr > 0:
        wr_drop = (train_wr - val_wr) / train_wr
        score -= max(0, wr_drop * 100) * 0.4  # Max -40 for 100% drop

    train_ret = train_metrics.get("total_return", 0)
    val_ret = val_metrics.get("total_return", 0)
    if train_ret > 0 and val_ret < 0:
        score -= 20  # Penalty for going negative on val

    # 2. Trade count adequacy (up to -20 points)
    val_trades = val_metrics.get("trades", 0)
    if val_trades < MIN_TRADES_STAT:
        score -= 20 * (1 - val_trades / MIN_TRADES_STAT)

    # 3. Walk-forward fold consistency (up to -30 points)
    if fold_metrics and len(fold_metrics) > 1:
        fold_returns = [f.get("val", {}).get("total_return", 0) for f in fold_metrics if f.get("val")]
        if len(fold_returns) > 1:
            std = float(np.std(fold_returns))
            mean_r = float(np.mean(fold_returns))
            if mean_r != 0:
                cv = abs(std / mean_r)  # Coefficient of variation
                score -= min(30, cv * 15)  # Penalize high variance

        # Count losing folds
        losing = sum(1 for r in fold_returns if r < 0)
        loss_frac = losing / len(fold_returns) if fold_returns else 0
        score -= loss_frac * 10

    # 4. Max drawdown severity (up to -10 points)
    val_dd = val_metrics.get("max_drawdown", 0)
    if val_dd < -20:
        score -= min(10, abs(val_dd) / 5)

    return round(max(0, min(100, score)), 2)


# ---------------------------------------------------------------------------
# Main background engine
# ---------------------------------------------------------------------------

async def _run_quant_backtest(qb_id: int):
    """Main quant backtest workflow — runs in background."""
    try:
        async with async_session_factory() as db:
            qb = await db.get(QuantBacktest, qb_id)
            if not qb:
                return
            qb.status = "running"
            qb.progress = "Initializing..."
            await db.commit()

            config = qb.config
            mode = qb.mode

            # Extract config
            exchange_groups = config.get("exchange_groups", ["US"])
            ticker_filter = config.get("tickers")
            portfolio_cfg = config.get("portfolio", {})
            top_k = config.get("top_k", 10)

            # Parameter grid
            min_scores = config.get("min_scores", [40, 50, 60, 70])
            target_pcts = config.get("target_pcts", [3.0, 5.0, 8.0])
            target_days_list = config.get("target_days_list", [10, 20, 30])
            max_dd_pcts = config.get("max_drawdown_pcts", [-2.0, -3.0, -5.0])
            combos = list(product(min_scores, target_pcts, target_days_list, max_dd_pcts))

            qb.candidates_count = len(combos)
            qb.progress = f"Generated {len(combos)} parameter combinations"
            await db.commit()

            # ---- Resolve tickers ----
            ticker_q = select(Ticker).where(Ticker.active == True)  # noqa: E712
            if ticker_filter:
                ticker_q = ticker_q.where(Ticker.symbol.in_(ticker_filter))
            elif exchange_groups:
                ticker_q = ticker_q.where(Ticker.exchange_group.in_(exchange_groups))
            tickers = list((await db.execute(ticker_q)).scalars().all())
            ticker_map = {t.id: t for t in tickers}
            ticker_ids = list(ticker_map.keys())

            if not tickers:
                qb.status = "failed"
                qb.diagnostics = {"error": "No tickers found for filters"}
                qb.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # ---- Determine splits ----
            if mode == "walk_forward":
                wf_params = config.get("walk_forward", {})
                df_from = date.fromisoformat(config["date_from"]) if isinstance(config.get("date_from"), str) else config.get("date_from")
                df_to = date.fromisoformat(config["date_to"]) if isinstance(config.get("date_to"), str) else config.get("date_to")
                folds = _generate_walk_forward_folds(df_from, df_to, wf_params)
                if not folds:
                    qb.status = "failed"
                    qb.diagnostics = {"error": "Date range too short for walk-forward windows"}
                    qb.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    return
                qb.progress = f"{len(folds)} walk-forward folds generated"
                await db.commit()
            else:
                # Single split mode
                splits = config.get("splits", {})
                folds = [{
                    "fold": 0,
                    "date_from_train": _parse_date(splits.get("date_from_train", config.get("date_from_train"))),
                    "date_to_train": _parse_date(splits.get("date_to_train", config.get("date_to_train"))),
                    "date_from_val": _parse_date(splits.get("date_from_val", config.get("date_from_val"))),
                    "date_to_val": _parse_date(splits.get("date_to_val", config.get("date_to_val"))),
                    "date_from_oos": _parse_date(splits.get("date_from_oos", config.get("date_from_oos"))),
                    "date_to_oos": _parse_date(splits.get("date_to_oos", config.get("date_to_oos"))),
                }]

            # ---- Load ALL OHLCV data covering all folds ----
            earliest = min(f["date_from_train"] for f in folds)
            latest = max(f["date_to_oos"] for f in folds)
            ohlcv_start = earliest - timedelta(days=365)
            ohlcv_end = latest + timedelta(days=90)

            qb.progress = f"Loading OHLCV for {len(tickers)} tickers..."
            await db.commit()

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

            if not ohlcv_rows:
                qb.status = "failed"
                qb.diagnostics = {"error": "No OHLCV data available"}
                qb.finished_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # Build DataFrames per ticker (once, reused across all combos)
            raw_by_ticker: dict[int, list] = {}
            for bar in ohlcv_rows:
                raw_by_ticker.setdefault(bar.ticker_id, []).append(bar)

            ohlcv_dfs: dict[int, pd.DataFrame] = {}
            for tid, bars in raw_by_ticker.items():
                ohlcv_dfs[tid] = _build_ohlcv_df(bars)

            qb.progress = f"Loaded {len(ohlcv_rows)} bars for {len(ohlcv_dfs)} tickers"
            await db.commit()

            # ---- PRE-COMPUTE: Score tables for each fold's TRAIN window ----
            qb.progress = "Phase 1/3: Pre-computing indicators (one-time)..."
            await db.commit()

            # Pre-compute scores ONCE per fold (the expensive part)
            train_score_tables: list[list[dict]] = []
            for fi, fold in enumerate(folds):
                qb.progress = f"Phase 1/3: Computing indicators for fold {fi + 1}/{len(folds)}..."
                await db.commit()
                st = await asyncio.to_thread(
                    _precompute_score_table,
                    ohlcv_dfs,
                    fold["date_from_train"], fold["date_to_train"],
                )
                train_score_tables.append(st)
                logger.info(f"Fold {fi}: {len(st)} score entries for TRAIN")

            # ---- PHASE 1: Apply all combos to pre-computed scores (fast) ----
            qb.progress = f"Phase 1/3: Testing {len(combos)} combos on TRAIN..."
            await db.commit()

            train_results: list[dict] = []

            for ci, (ms, tp, td, mdd) in enumerate(combos):
                combo_config = {
                    "min_score": ms,
                    "target_pct": tp,
                    "target_days": td,
                    "max_drawdown_pct": mdd,
                }

                fold_train_list = []
                all_train_signals = []

                for fi, fold in enumerate(folds):
                    signals, _, diag = await asyncio.to_thread(
                        _apply_combo_to_score_table,
                        train_score_tables[fi], ohlcv_dfs,
                        ms, tp, td, mdd,
                    )
                    fold_metrics = await asyncio.to_thread(
                        _compute_extended_metrics,
                        signals, ohlcv_dfs, portfolio_cfg, tp, td, mdd,
                        fold["date_from_train"], fold["date_to_train"],
                    )
                    fold_train_list.append(fold_metrics)
                    all_train_signals.extend(signals)

                if len(fold_train_list) > 1:
                    avg_metrics = _average_metrics(fold_train_list)
                else:
                    avg_metrics = fold_train_list[0] if fold_train_list else _empty_metrics()

                obj = _compute_objective(avg_metrics)
                train_results.append({
                    "combo": combo_config,
                    "train_metrics": avg_metrics,
                    "train_objective": obj,
                    "fold_train_metrics": fold_train_list,
                })

                if (ci + 1) % max(1, len(combos) // 10) == 0:
                    qb.progress = f"Phase 1/3: TRAIN {ci + 1}/{len(combos)} combos..."
                    await db.commit()

            # Sort by objective, pick top K
            train_results.sort(key=lambda x: x["train_objective"], reverse=True)
            top_candidates = train_results[:top_k]

            qb.progress = f"Phase 1 done. Top {len(top_candidates)} configs selected for validation."
            await db.commit()

            # ---- PRE-COMPUTE: Score tables for VALIDATION windows ----
            qb.progress = "Phase 2/3: Pre-computing indicators for validation..."
            await db.commit()

            val_score_tables: list[list[dict]] = []
            for fi, fold in enumerate(folds):
                st = await asyncio.to_thread(
                    _precompute_score_table,
                    ohlcv_dfs,
                    fold["date_from_val"], fold["date_to_val"],
                )
                val_score_tables.append(st)

            # ---- PHASE 2: Apply top K combos to validation scores ----
            qb.progress = f"Phase 2/3: Testing {len(top_candidates)} configs on VALIDATION..."
            await db.commit()

            val_results: list[dict] = []

            for vi, cand in enumerate(top_candidates):
                combo = cand["combo"]
                ms, tp, td, mdd = combo["min_score"], combo["target_pct"], combo["target_days"], combo["max_drawdown_pct"]

                fold_val_list = []
                for fi, fold in enumerate(folds):
                    signals, _, diag = await asyncio.to_thread(
                        _apply_combo_to_score_table,
                        val_score_tables[fi], ohlcv_dfs,
                        ms, tp, td, mdd,
                    )
                    fold_metrics = await asyncio.to_thread(
                        _compute_extended_metrics,
                        signals, ohlcv_dfs, portfolio_cfg, tp, td, mdd,
                        fold["date_from_val"], fold["date_to_val"],
                    )
                    fold_val_list.append(fold_metrics)

                val_avg = _average_metrics(fold_val_list) if len(fold_val_list) > 1 else (fold_val_list[0] if fold_val_list else _empty_metrics())
                val_obj = _compute_objective(val_avg)

                # Compute stability
                stability = _compute_stability_score(
                    cand["train_metrics"], val_avg,
                    [{"train": ft, "val": fv} for ft, fv in zip(cand["fold_train_metrics"], fold_val_list)]
                    if len(folds) > 1 else None,
                )

                val_results.append({
                    **cand,
                    "val_metrics": val_avg,
                    "val_objective": val_obj,
                    "stability_score": stability,
                    "fold_val_metrics": fold_val_list,
                })

                qb.progress = f"Phase 2/3: VAL {vi + 1}/{len(top_candidates)} configs..."
                await db.commit()

            # Select winner: highest val_objective with stability bonus
            for vr in val_results:
                vr["selection_score"] = vr["val_objective"] * 0.7 + (vr["stability_score"] / 100) * 0.3

            val_results.sort(key=lambda x: x["selection_score"], reverse=True)

            qb.progress = "Phase 2 done. Running winner on OOS..."
            await db.commit()

            # ---- PHASE 3: Run winner on OOS ----
            winner = val_results[0]
            wc = winner["combo"]
            ms, tp, td, mdd = wc["min_score"], wc["target_pct"], wc["target_days"], wc["max_drawdown_pct"]

            qb.progress = "Phase 3/3: Pre-computing indicators for OOS..."
            await db.commit()

            fold_oos_list = []
            oos_equity = []
            for fi, fold in enumerate(folds):
                oos_st = await asyncio.to_thread(
                    _precompute_score_table,
                    ohlcv_dfs,
                    fold["date_from_oos"], fold["date_to_oos"],
                )
                signals, _, diag = await asyncio.to_thread(
                    _apply_combo_to_score_table,
                    oos_st, ohlcv_dfs,
                    ms, tp, td, mdd,
                )
                fold_metrics = await asyncio.to_thread(
                    _compute_extended_metrics,
                    signals, ohlcv_dfs, portfolio_cfg, tp, td, mdd,
                    fold["date_from_oos"], fold["date_to_oos"],
                )
                fold_oos_list.append(fold_metrics)
                oos_equity.extend(fold_metrics.get("equity_curve", []))

            oos_avg = _average_metrics(fold_oos_list) if len(fold_oos_list) > 1 else (fold_oos_list[0] if fold_oos_list else _empty_metrics())

            # ---- Save candidates to DB ----
            qb.progress = "Saving results..."
            await db.commit()

            warnings_list = []

            for rank_idx, vr in enumerate(val_results):
                is_winner = (rank_idx == 0)

                cand_warnings = []
                if vr.get("val_metrics", {}).get("trades", 0) < MIN_TRADES_STAT:
                    cand_warnings.append(f"Low trade count on VAL ({vr['val_metrics']['trades']})")
                if vr.get("stability_score", 0) < 50:
                    cand_warnings.append("Overfit risk: stability < 50")
                if vr.get("train_metrics", {}).get("total_return", 0) > 0 and vr.get("val_metrics", {}).get("total_return", 0) < 0:
                    cand_warnings.append("Performance flips negative on validation")

                # Build fold_metrics for walk-forward
                fold_detail = None
                if len(folds) > 1:
                    fold_detail = []
                    for fi, fold in enumerate(folds):
                        fd = {
                            "fold": fi,
                            "dates": {
                                "train": f"{fold['date_from_train']} to {fold['date_to_train']}",
                                "val": f"{fold['date_from_val']} to {fold['date_to_val']}",
                                "oos": f"{fold['date_from_oos']} to {fold['date_to_oos']}",
                            },
                            "train": _strip_equity(vr["fold_train_metrics"][fi]) if fi < len(vr.get("fold_train_metrics", [])) else None,
                            "val": _strip_equity(vr["fold_val_metrics"][fi]) if fi < len(vr.get("fold_val_metrics", [])) else None,
                        }
                        if is_winner and fi < len(fold_oos_list):
                            fd["oos"] = _strip_equity(fold_oos_list[fi])
                        fold_detail.append(fd)

                cand = QuantBacktestCandidate(
                    quant_backtest_id=qb_id,
                    config=vr["combo"],
                    rank=rank_idx + 1,
                    train_metrics=_strip_equity(vr["train_metrics"]),
                    train_objective=vr["train_objective"],
                    val_metrics=_strip_equity(vr["val_metrics"]),
                    val_objective=vr["val_objective"],
                    oos_metrics=_strip_equity(oos_avg) if is_winner else None,
                    stability_score=vr["stability_score"],
                    is_selected=is_winner,
                    fold_metrics=fold_detail,
                    equity_curve=oos_equity if is_winner else None,
                    warnings=cand_warnings if cand_warnings else None,
                )
                db.add(cand)

                if is_winner:
                    warnings_list.extend(cand_warnings)

            # ---- Update top-level record ----
            final_stability = winner["stability_score"]
            if oos_avg.get("trades", 0) < MIN_TRADES_STAT:
                warnings_list.append(f"OOS has only {oos_avg['trades']} trades (statistically weak)")
            if oos_avg.get("total_return", 0) < 0:
                warnings_list.append("OOS return is negative — strategy may not be viable")

            qb.selected_config = winner["combo"]
            qb.stability_score = final_stability
            qb.results = {
                "train": _strip_equity(winner["train_metrics"]),
                "val": _strip_equity(winner["val_metrics"]),
                "oos": _strip_equity(oos_avg),
                "folds": len(folds),
                "candidates_tested": len(combos),
                "top_k_evaluated": len(val_results),
            }
            qb.diagnostics = {
                "tickers": len(tickers),
                "ohlcv_bars": len(ohlcv_rows),
                "folds": len(folds),
                "mode": mode,
            }
            qb.warnings = warnings_list if warnings_list else None
            qb.status = "completed"
            qb.progress = None
            qb.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"Quant backtest {qb_id} completed. Winner: {winner['combo']}, Stability: {final_stability}")

    except Exception as e:
        logger.error(f"Quant backtest {qb_id} failed: {e}", exc_info=True)
        try:
            async with async_session_factory() as db:
                qb = await db.get(QuantBacktest, qb_id)
                if qb:
                    qb.status = "failed"
                    qb.diagnostics = {"error": str(e)}
                    qb.progress = None
                    qb.finished_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _parse_date(val) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse date: {val}")


def _strip_equity(metrics: dict) -> dict:
    """Return metrics without the equity_curve (to save DB space in bulk)."""
    if not metrics:
        return metrics
    return {k: v for k, v in metrics.items() if k != "equity_curve"}


def _average_metrics(metrics_list: list[dict]) -> dict:
    """Average numeric metrics across multiple folds."""
    if not metrics_list:
        return _empty_metrics()
    if len(metrics_list) == 1:
        return metrics_list[0]

    result = {}
    for key in metrics_list[0]:
        if key == "equity_curve":
            continue
        vals = [m.get(key) for m in metrics_list if m.get(key) is not None]
        if not vals:
            result[key] = None
        elif isinstance(vals[0], (int, float)):
            result[key] = round(float(np.mean(vals)), 4)
        else:
            result[key] = vals[0]  # Non-numeric: take first

    # Sum trades instead of averaging
    result["trades"] = sum(m.get("trades", 0) for m in metrics_list)
    result["wins"] = sum(m.get("wins", 0) for m in metrics_list)
    result["losses"] = sum(m.get("losses", 0) for m in metrics_list)
    result["timeouts"] = sum(m.get("timeouts", 0) for m in metrics_list)

    return result
