"""Pattern Recognition CNN training pipeline."""

import asyncio
import logging
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import torch
from sklearn.metrics import precision_score, recall_score, f1_score
from torch.utils.data import DataLoader

from app.database import async_session_factory
from app.ml.config import (
    DEVICE, DEFAULT_EPOCHS, DEFAULT_BATCH_SIZE, DEFAULT_LR,
    DEFAULT_WEIGHT_DECAY, DEFAULT_DROPOUT, PATTERN_CHANNELS, PATTERN_WINDOW,
    NUM_PATTERNS, MIN_TRAINING_SAMPLES,
)
from app.ml.dataset import OHLCVWindowDataset
from app.ml.features import extract_ohlcv_windows
from app.ml.models.pattern_recognizer import PatternRecognizerNet, PATTERN_NAMES
from app.ml.registry import get_next_version, save_model, get_model_file_size
from app.ml.training.base_trainer import BaseTrainer
from app.models.ml import MLModel, MLTrainingRun
from app.models.ticker import Ticker
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _label_patterns(windows: list[dict]) -> list[dict]:
    """Add programmatic pattern labels to OHLCV windows.

    Uses simple heuristic detectors based on price action within each window.
    Labels are multi-label binary vectors of shape (11,).
    """
    for w in windows:
        tensor = w["tensor"]  # (6, 60) — [O, H, L, C, log_vol, returns]
        close = tensor[3]  # normalized close prices
        high = tensor[1]
        low = tensor[2]
        returns = tensor[5]
        n = len(close)

        labels = [0.0] * NUM_PATTERNS

        # Split window into halves for pattern detection
        mid = n // 2
        first_half = close[:mid]
        second_half = close[mid:]

        # Simple trend detection
        slope_full = (close[-1] - close[0]) / n if n > 0 else 0
        slope_first = (first_half[-1] - first_half[0]) / mid if mid > 0 else 0
        slope_second = (second_half[-1] - second_half[0]) / (n - mid) if (n - mid) > 0 else 0

        std_close = float(np.std(close))
        range_close = float(np.max(close) - np.min(close))

        if std_close < 1e-6:
            w["pattern_labels"] = labels
            continue

        # Bull flag: decline then consolidation then uptick
        q1, q2, q3, q4 = close[:15], close[15:30], close[30:45], close[45:]
        s_q1 = (q1[-1] - q1[0]) / 15 if len(q1) >= 15 else 0
        s_q4 = (q4[-1] - q4[0]) / max(len(q4), 1) if len(q4) > 0 else 0
        std_mid = float(np.std(close[15:45]))
        if s_q1 > 0.02 and std_mid < std_close * 0.6 and s_q4 > 0.01:
            labels[0] = 1.0  # bull_flag

        # Bear flag: rally then consolidation then downtick
        if s_q1 < -0.02 and std_mid < std_close * 0.6 and s_q4 < -0.01:
            labels[1] = 1.0  # bear_flag

        # Double bottom: two lows at similar level
        min1_idx = int(np.argmin(first_half))
        min2_idx = int(np.argmin(second_half)) + mid
        min1_val = float(close[min1_idx])
        min2_val = float(close[min2_idx])
        if abs(min1_val - min2_val) < 0.3 * std_close and close[-1] > max(min1_val, min2_val):
            # Check there's a peak between the two bottoms
            peak_between = float(np.max(close[min1_idx:min2_idx])) if min2_idx > min1_idx else 0
            if peak_between > min1_val + 0.5 * std_close:
                labels[2] = 1.0  # double_bottom

        # Double top: two highs at similar level
        max1_idx = int(np.argmax(first_half))
        max2_idx = int(np.argmax(second_half)) + mid
        max1_val = float(close[max1_idx])
        max2_val = float(close[max2_idx])
        if abs(max1_val - max2_val) < 0.3 * std_close and close[-1] < min(max1_val, max2_val):
            trough_between = float(np.min(close[max1_idx:max2_idx])) if max2_idx > max1_idx else 0
            if trough_between < max1_val - 0.5 * std_close:
                labels[3] = 1.0  # double_top

        # Head and shoulders (simplified)
        thirds = n // 3
        peak_l = float(np.max(close[:thirds]))
        peak_m = float(np.max(close[thirds:2*thirds]))
        peak_r = float(np.max(close[2*thirds:]))
        if peak_m > peak_l and peak_m > peak_r and abs(peak_l - peak_r) < 0.3 * std_close:
            if peak_m > peak_l + 0.3 * std_close:
                labels[4] = 1.0  # head_and_shoulders

        # Inverse head and shoulders
        trough_l = float(np.min(close[:thirds]))
        trough_m = float(np.min(close[thirds:2*thirds]))
        trough_r = float(np.min(close[2*thirds:]))
        if trough_m < trough_l and trough_m < trough_r and abs(trough_l - trough_r) < 0.3 * std_close:
            if trough_m < trough_l - 0.3 * std_close:
                labels[5] = 1.0  # inv_head_and_shoulders

        # Ascending triangle: rising lows, flat highs
        lows = [float(np.min(close[i:i+15])) for i in range(0, n-14, 15)]
        highs_seg = [float(np.max(close[i:i+15])) for i in range(0, n-14, 15)]
        if len(lows) >= 3:
            lows_rising = all(lows[i+1] > lows[i] - 0.1 * std_close for i in range(len(lows)-1))
            highs_flat = (max(highs_seg) - min(highs_seg)) < 0.4 * std_close
            if lows_rising and highs_flat:
                labels[6] = 1.0  # ascending_triangle

        # Descending triangle: falling highs, flat lows
        if len(lows) >= 3:
            highs_falling = all(highs_seg[i+1] < highs_seg[i] + 0.1 * std_close for i in range(len(highs_seg)-1))
            lows_flat = (max(lows) - min(lows)) < 0.4 * std_close
            if highs_falling and lows_flat:
                labels[7] = 1.0  # descending_triangle

        # Cup and handle (simplified): U-shape then small dip
        cup_mid = float(np.min(close[10:50]))
        cup_left = float(close[5])
        cup_right = float(close[50]) if n > 50 else float(close[-10])
        if cup_mid < cup_left - 0.5 * std_close and cup_mid < cup_right - 0.5 * std_close:
            if abs(cup_left - cup_right) < 0.4 * std_close:
                labels[8] = 1.0  # cup_and_handle

        # Breakout: low volatility period followed by sharp move
        vol_early = float(np.std(close[:40]))
        vol_late = float(np.std(close[40:]))
        last_move = abs(float(close[-1] - close[-5])) if n > 5 else 0
        if vol_late > vol_early * 1.5 and last_move > std_close * 0.8:
            labels[9] = 1.0  # breakout

        # Consolidation: low volatility, tight range
        if range_close < std_close * 3 and vol_early < std_close * 0.7:
            labels[10] = 1.0  # consolidation

        w["pattern_labels"] = labels

    return windows


class PatternTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("pattern_recognizer")

    async def build_datasets(self, db, config):
        pass  # Not used directly — we use the main function

    def build_model(self, config, input_dim=None):
        return PatternRecognizerNet(
            in_channels=config.get("in_channels", PATTERN_CHANNELS),
            seq_len=config.get("seq_len", PATTERN_WINDOW),
        )

    def compute_metrics(self, model, dataloader):
        model.eval()
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch_x, batch_y in dataloader:
                batch_x = batch_x.to(self.device)
                logits = model(batch_x)
                probs = torch.sigmoid(logits).cpu()
                preds = (probs > 0.5).float()
                all_preds.append(preds)
                all_labels.append(batch_y)

        all_preds = torch.cat(all_preds).numpy()
        all_labels = torch.cat(all_labels).numpy()

        # Per-pattern and overall metrics
        metrics = {
            "samples": len(all_labels),
        }

        # Macro averages
        try:
            metrics["precision_macro"] = round(float(precision_score(
                all_labels, all_preds, average="macro", zero_division=0
            )), 4)
            metrics["recall_macro"] = round(float(recall_score(
                all_labels, all_preds, average="macro", zero_division=0
            )), 4)
            metrics["f1_macro"] = round(float(f1_score(
                all_labels, all_preds, average="macro", zero_division=0
            )), 4)
        except Exception:
            metrics["precision_macro"] = 0
            metrics["recall_macro"] = 0
            metrics["f1_macro"] = 0

        # Per-pattern stats
        pattern_stats = {}
        for i, name in enumerate(PATTERN_NAMES):
            count = int(all_labels[:, i].sum())
            pred_count = int(all_preds[:, i].sum())
            pattern_stats[name] = {"actual": count, "predicted": pred_count}
        metrics["pattern_counts"] = pattern_stats

        return metrics


async def train_pattern_recognizer(config: dict) -> int:
    """Full training pipeline for pattern recognizer. Returns ml_model_id."""
    start_time = time.time()
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    # Create DB records first
    async with async_session_factory() as db:
        version = await get_next_version(db, "pattern_recognizer")
        ml_model = MLModel(
            model_type="pattern_recognizer",
            version=version,
            name=config.get("name", f"Pattern Recognizer v{version}"),
            status="training",
            architecture={
                "type": "PatternRecognizerNet",
                "in_channels": PATTERN_CHANNELS,
                "seq_len": PATTERN_WINDOW,
                "num_patterns": NUM_PATTERNS,
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

    # Extract data
    async with async_session_factory() as db:
        # Get all ticker IDs
        result = await db.execute(select(Ticker.id))
        ticker_ids = [r[0] for r in result.all()]

        from datetime import date as date_type
        date_from = date_type.fromisoformat(config.get("date_from", "2024-01-01"))
        date_to = date_type.fromisoformat(config.get("date_to", "2025-12-31"))

        windows = await extract_ohlcv_windows(
            db, ticker_ids, date_from, date_to,
            window_size=PATTERN_WINDOW, stride=config.get("stride", 5),
        )

        if len(windows) < MIN_TRAINING_SAMPLES:
            raise ValueError(
                f"Only {len(windows)} windows extracted. Need at least {MIN_TRAINING_SAMPLES}."
            )

        # Label patterns
        windows = _label_patterns(windows)

        # Update DB with sample count
        ml_model = await db.get(MLModel, model_id)
        n = len(windows)
        n_train = int(n * 0.70)
        n_val = int(n * 0.85)
        ml_model.train_samples = n_train
        ml_model.val_samples = n_val - n_train
        ml_model.test_samples = n - n_val
        await db.commit()

    # Train (CPU-bound)
    try:
        model, history, best_epoch, train_metrics, val_metrics, test_metrics = await asyncio.to_thread(
            _train_pattern_sync, windows, config,
        )

        model_path, scaler_path = save_model(
            model, None, "pattern_recognizer", version,
            metadata={"config": config, "pattern_names": PATTERN_NAMES},
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
            run.best_val_loss = history[best_epoch - 1]["val_loss"] if best_epoch > 0 else None
            run.best_val_metric = val_metrics.get("f1_macro")
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            f"Pattern recognizer v{version} trained in {elapsed:.0f}s. "
            f"Test F1: {test_metrics.get('f1_macro', 0):.4f}"
        )
        return model_id

    except Exception as e:
        logger.error(f"Pattern recognizer training failed: {e}", exc_info=True)
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


def _train_pattern_sync(windows, config):
    """Synchronous training for pattern recognizer."""
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    n = len(windows)
    n_train = int(n * 0.70)
    n_val = int(n * 0.85)

    train_ds = OHLCVWindowDataset(windows[:n_train], task="pattern")
    val_ds = OHLCVWindowDataset(windows[n_train:n_val], task="pattern")
    test_ds = OHLCVWindowDataset(windows[n_val:], task="pattern")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    model = PatternRecognizerNet(
        in_channels=config.get("in_channels", PATTERN_CHANNELS),
        seq_len=config.get("seq_len", PATTERN_WINDOW),
    )

    # Use pos_weight for imbalanced patterns (most samples won't have most patterns)
    criterion = torch.nn.BCEWithLogitsLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=DEFAULT_WEIGHT_DECAY)

    trainer = PatternTrainer()
    model, history, best_epoch = trainer.train_loop(
        model, train_loader, val_loader, criterion, optimizer, epochs,
    )

    train_metrics = trainer.compute_metrics(model, train_loader)
    val_metrics = trainer.compute_metrics(model, val_loader)
    test_metrics = trainer.compute_metrics(model, test_loader)

    return model, history, best_epoch, train_metrics, val_metrics, test_metrics
