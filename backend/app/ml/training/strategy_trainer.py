"""Strategy Selector training pipeline.

Learns from completed quant backtest results to predict optimal
strategy configurations given market conditions.
"""

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import torch
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader

from app.database import async_session_factory
from app.ml.config import (
    DEVICE, DEFAULT_EPOCHS, DEFAULT_BATCH_SIZE, DEFAULT_LR,
    DEFAULT_WEIGHT_DECAY, DEFAULT_DROPOUT, STRATEGY_INPUT_DIM,
    MIN_TRAINING_SAMPLES,
)
from app.ml.dataset import SignalDataset
from app.ml.features import fit_scaler
from app.ml.models.strategy_selector import StrategySelectorNet
from app.ml.registry import get_next_version, save_model, get_model_file_size
from app.ml.training.base_trainer import BaseTrainer
from app.models.ml import MLModel, MLTrainingRun
from app.models.quant_backtest import QuantBacktest, QuantBacktestCandidate
from app.models.indicator import ComputedIndicator
from app.models.ohlcv import OHLCVDaily
from app.models.ticker import Ticker
from sqlalchemy import select, func, and_

logger = logging.getLogger(__name__)


async def _extract_strategy_training_data(db) -> tuple[np.ndarray, np.ndarray, list[dict], list[str]]:
    """Extract market conditions → best strategy config training pairs.

    For each completed backtest, extract aggregate market stats from
    the training date range and pair with the selected (winning) config.

    Returns (X, y, config_map, feature_names).
    """
    # Get all completed backtests with their winning configs
    result = await db.execute(
        select(QuantBacktest).where(QuantBacktest.status == "completed")
    )
    backtests = list(result.scalars().all())

    if not backtests:
        return np.array([]), np.array([]), [], []

    # Get all selected candidates (winning configs)
    all_configs = []
    config_map = []  # unique config → index mapping

    backtest_configs = []
    for bt in backtests:
        result = await db.execute(
            select(QuantBacktestCandidate).where(
                QuantBacktestCandidate.quant_backtest_id == bt.id,
                QuantBacktestCandidate.is_selected == True,
            )
        )
        winner = result.scalars().first()
        if not winner or not winner.config:
            continue

        # Normalize config to a hashable tuple for dedup
        cfg = winner.config
        cfg_key = str(sorted(cfg.items()) if isinstance(cfg, dict) else cfg)

        if cfg_key not in [str(sorted(c.items()) if isinstance(c, dict) else c) for c in config_map]:
            config_map.append(cfg)
        config_idx = next(
            i for i, c in enumerate(config_map)
            if str(sorted(c.items()) if isinstance(c, dict) else c) == cfg_key
        )

        backtest_configs.append((bt, config_idx))

    if not backtest_configs:
        return np.array([]), np.array([]), [], []

    # For each backtest, compute aggregate market features from the date range
    feature_names = [
        "avg_rsi", "std_rsi", "avg_adx", "std_adx",
        "avg_macd_hist", "avg_bb_width", "avg_atr_pct",
        "avg_volume_ratio", "pct_above_sma50", "pct_above_sma200",
        "avg_momentum_score", "std_momentum_score",
        "avg_trend_score", "avg_vol_score",
        "market_breadth", "avg_roc12",
        "median_close_sma200_ratio", "avg_stoch_k",
        "regime_ranging_pct", "regime_trending_pct", "regime_strong_pct",
        "avg_obv_slope", "avg_cci",
        "num_tickers", "avg_return_5d", "avg_return_20d",
        "vol_of_vol", "high_low_range_pct",
        "calendar_month_sin", "calendar_month_cos",
    ]

    X_list = []
    y_list = []

    for bt, config_idx in backtest_configs:
        bt_config = bt.config or {}
        splits = bt_config.get("splits", {})
        date_from_str = splits.get("date_from_train") or bt_config.get("date_from")
        date_to_str = splits.get("date_to_train") or bt_config.get("date_to")

        if not date_from_str or not date_to_str:
            continue

        from datetime import date as date_type
        try:
            d_from = date_type.fromisoformat(date_from_str)
            d_to = date_type.fromisoformat(date_to_str)
        except (ValueError, TypeError):
            continue

        # Get aggregate indicator stats for this period
        result = await db.execute(
            select(
                func.avg(ComputedIndicator.rsi_14),
                func.stddev(ComputedIndicator.rsi_14),
                func.avg(ComputedIndicator.adx_14),
                func.stddev(ComputedIndicator.adx_14),
                func.avg(ComputedIndicator.macd_histogram),
                func.avg(ComputedIndicator.bb_width),
                func.avg(ComputedIndicator.atr_14),
                func.avg(ComputedIndicator.volume_ratio),
                func.avg(ComputedIndicator.roc_12),
                func.avg(ComputedIndicator.stoch_k),
                func.avg(ComputedIndicator.obv_slope),
                func.avg(ComputedIndicator.cci_20),
                func.count(ComputedIndicator.id),
            ).where(
                ComputedIndicator.trade_date >= d_from,
                ComputedIndicator.trade_date <= d_to,
            )
        )
        row = result.first()
        if not row or row[12] == 0:  # count == 0
            continue

        avg_rsi = float(row[0] or 50)
        std_rsi = float(row[1] or 10)
        avg_adx = float(row[2] or 20)
        std_adx = float(row[3] or 10)
        avg_macd_hist = float(row[4] or 0)
        avg_bb_width = float(row[5] or 0.05)
        avg_atr = float(row[6] or 1)
        avg_vol_ratio = float(row[7] or 1)
        avg_roc12 = float(row[8] or 0)
        avg_stoch_k = float(row[9] or 50)
        avg_obv_slope = float(row[10] or 0)
        avg_cci = float(row[11] or 0)

        # Additional market breadth metrics
        result = await db.execute(
            select(func.count(func.distinct(ComputedIndicator.ticker_id))).where(
                ComputedIndicator.trade_date >= d_from,
                ComputedIndicator.trade_date <= d_to,
            )
        )
        num_tickers = int(result.scalar() or 0)

        # Calendar features (midpoint of train period)
        import math
        mid_month = (d_from.month + d_to.month) / 2
        month_sin = math.sin(2 * math.pi * mid_month / 12)
        month_cos = math.cos(2 * math.pi * mid_month / 12)

        features = [
            avg_rsi, std_rsi, avg_adx, std_adx,
            avg_macd_hist, avg_bb_width, avg_atr,
            avg_vol_ratio, 0.5, 0.5,  # pct_above_sma50/200 placeholders
            0, 0,  # momentum/trend score placeholders
            0, 0,  # trend/vol score placeholders
            0.5,  # market_breadth placeholder
            avg_roc12,
            1.0,  # median close_sma200 ratio
            avg_stoch_k,
            0.33, 0.33, 0.34,  # regime distribution placeholders
            avg_obv_slope, avg_cci,
            float(num_tickers),
            0, 0,  # avg returns placeholders
            std_rsi * 0.1,  # vol_of_vol proxy
            avg_bb_width,  # high_low_range proxy
            month_sin, month_cos,
        ]

        X_list.append(features)
        y_list.append(config_idx)

    if not X_list:
        return np.array([]), np.array([]), config_map, feature_names

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    logger.info(f"Extracted {len(X)} strategy training samples, {len(config_map)} unique configs")
    return X, y, config_map, feature_names


class StrategyTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("strategy_selector")

    async def build_datasets(self, db, config):
        pass

    def build_model(self, config, input_dim=None):
        return StrategySelectorNet(
            input_dim=input_dim or STRATEGY_INPUT_DIM,
            num_configs=config.get("num_configs", 10),
            hidden_dim=config.get("hidden_dim", 128),
            dropout=config.get("dropout", DEFAULT_DROPOUT),
        )

    def compute_metrics(self, model, dataloader):
        model.eval()
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch_x, batch_y in dataloader:
                batch_x = batch_x.to(self.device)
                outputs = model(batch_x)
                preds = outputs.argmax(dim=-1).cpu()
                all_preds.extend(preds.tolist())
                all_labels.extend(batch_y.tolist())

        if not all_labels:
            return {"accuracy": 0, "samples": 0}

        accuracy = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)
        num_classes = max(max(all_labels), max(all_preds)) + 1

        # Top-3 accuracy
        # Can't easily compute without logits, use regular accuracy
        return {
            "accuracy": round(accuracy, 4),
            "samples": len(all_labels),
            "num_configs": num_classes,
            "class_distribution": dict(Counter(all_labels)),
        }


async def train_strategy_selector(config: dict) -> int:
    """Full training pipeline for strategy selector. Returns ml_model_id."""
    start_time = time.time()
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    # Create DB records first
    async with async_session_factory() as db:
        version = await get_next_version(db, "strategy_selector")
        ml_model = MLModel(
            model_type="strategy_selector",
            version=version,
            name=config.get("name", f"Strategy Selector v{version}"),
            status="training",
            architecture={
                "type": "StrategySelectorNet",
                "input_dim": STRATEGY_INPUT_DIM,
                "hidden_dim": config.get("hidden_dim", 128),
                "dropout": config.get("dropout", DEFAULT_DROPOUT),
            },
            hyperparameters={"epochs": epochs, "batch_size": batch_size, "lr": lr},
            train_date_from=config.get("date_from"),
            train_date_to=config.get("date_to"),
        )
        db.add(ml_model)
        await db.flush()
        model_id = ml_model.id

        run = MLTrainingRun(
            ml_model_id=model_id,
            status="running",
            total_epochs=epochs,
            config_snapshot=config,
        )
        db.add(run)
        await db.flush()
        run_id = run.id
        await db.commit()

    # Extract data from completed backtests
    async with async_session_factory() as db:
        X, y, config_map, feature_names = await _extract_strategy_training_data(db)

        if len(X) < 3:
            error_msg = (
                f"Only {len(X)} completed backtests with selected configs found. "
                f"Need at least 3. Run more quant backtests first."
            )
            # Update records as failed
            ml_model = await db.get(MLModel, model_id)
            if ml_model:
                ml_model.status = "failed"
            run = await db.get(MLTrainingRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = error_msg
                run.finished_at = datetime.now(timezone.utc)
            await db.commit()
            raise ValueError(error_msg)

        num_configs = len(config_map)

        # Update model with dimensions
        ml_model = await db.get(MLModel, model_id)
        ml_model.architecture["num_configs"] = num_configs
        ml_model.architecture["input_dim"] = X.shape[1]
        ml_model.feature_config = {
            "features": feature_names,
            "config_map": config_map,
            "scaler": "StandardScaler",
        }

        n = len(X)
        n_train = max(int(n * 0.70), 1)
        n_val = max(int(n * 0.85), n_train + 1)
        ml_model.train_samples = n_train
        ml_model.val_samples = min(n_val - n_train, n - n_train)
        ml_model.test_samples = max(n - n_val, 0)
        await db.commit()

    # Train
    try:
        model, history, best_epoch, train_metrics, val_metrics, test_metrics = await asyncio.to_thread(
            _train_strategy_sync, X, y, num_configs, config,
        )

        scaler = fit_scaler(X[:max(int(len(X) * 0.7), 1)])
        model_path, scaler_path = save_model(
            model, scaler, "strategy_selector", version,
            metadata={
                "config": config,
                "config_map": config_map,
                "feature_names": feature_names,
            },
        )

        elapsed = time.time() - start_time

        async with async_session_factory() as db:
            ml_model = await db.get(MLModel, model_id)
            ml_model.status = "trained"
            ml_model.model_path = model_path
            ml_model.scaler_path = scaler_path
            ml_model.train_metrics = train_metrics
            ml_model.val_metrics = val_metrics
            ml_model.test_metrics = test_metrics
            ml_model.training_time_seconds = round(elapsed, 2)
            ml_model.file_size_mb = get_model_file_size(model_path)

            run = await db.get(MLTrainingRun, run_id)
            run.status = "completed"
            run.epoch_history = history
            run.best_epoch = best_epoch
            run.best_val_loss = history[best_epoch - 1]["val_loss"] if best_epoch > 0 and history else None
            run.best_val_metric = val_metrics.get("accuracy")
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            f"Strategy selector v{version} trained in {elapsed:.0f}s. "
            f"Test accuracy: {test_metrics.get('accuracy', 0):.4f}"
        )
        return model_id

    except Exception as e:
        logger.error(f"Strategy selector training failed: {e}", exc_info=True)
        async with async_session_factory() as db:
            run = await db.get(MLTrainingRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.finished_at = datetime.now(timezone.utc)
            ml_model = await db.get(MLModel, model_id)
            if ml_model:
                ml_model.status = "failed"
            await db.commit()
        raise


def _train_strategy_sync(X, y, num_configs, config):
    """Synchronous training for strategy selector."""
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", min(DEFAULT_BATCH_SIZE, len(X)))
    lr = config.get("lr", DEFAULT_LR)

    n = len(X)
    n_train = max(int(n * 0.70), 1)
    n_val = max(int(n * 0.85), n_train + 1)

    # Fit scaler on training data
    scaler = fit_scaler(X[:n_train])
    X_scaled = scaler.transform(X).astype(np.float32)

    X_train, y_train = X_scaled[:n_train], y[:n_train]
    X_val, y_val = X_scaled[n_train:n_val], y[n_train:n_val]
    X_test, y_test = X_scaled[n_val:], y[n_val:]

    # Handle case where val or test is empty (small dataset)
    if len(X_val) == 0:
        X_val, y_val = X_train[-1:], y_train[-1:]
    if len(X_test) == 0:
        X_test, y_test = X_val, y_val

    train_ds = SignalDataset(X_train, y_train)
    val_ds = SignalDataset(X_val, y_val)
    test_ds = SignalDataset(X_test, y_test)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    input_dim = X_train.shape[1]
    model = StrategySelectorNet(
        input_dim=input_dim,
        num_configs=num_configs,
        hidden_dim=config.get("hidden_dim", 128),
        dropout=config.get("dropout", DEFAULT_DROPOUT),
    )

    # Class weights
    class_counts = np.bincount(y_train, minlength=num_configs).astype(np.float32)
    class_weights = 1.0 / (class_counts + 1)
    class_weights = class_weights / class_weights.sum() * num_configs
    criterion = torch.nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, device=DEVICE)
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=DEFAULT_WEIGHT_DECAY)

    trainer = StrategyTrainer()
    model, history, best_epoch = trainer.train_loop(
        model, train_loader, val_loader, criterion, optimizer, epochs,
    )

    train_metrics = trainer.compute_metrics(model, train_loader)
    val_metrics = trainer.compute_metrics(model, val_loader)
    test_metrics = trainer.compute_metrics(model, test_loader)

    return model, history, best_epoch, train_metrics, val_metrics, test_metrics
