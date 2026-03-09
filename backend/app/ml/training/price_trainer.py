"""Price Prediction LSTM training pipeline."""

import asyncio
import logging
import time
from datetime import datetime, timezone

import numpy as np
import torch
from torch.utils.data import DataLoader

from app.database import async_session_factory
from app.ml.config import (
    DEVICE, DEFAULT_EPOCHS, DEFAULT_BATCH_SIZE, DEFAULT_LR,
    DEFAULT_WEIGHT_DECAY, DEFAULT_DROPOUT, PRICE_HIDDEN, PRICE_HORIZONS,
    PRICE_INPUT_DIM, PRICE_SEQ_LEN, MIN_TRAINING_SAMPLES,
)
from app.ml.dataset import OHLCVWindowDataset
from app.ml.features import extract_ohlcv_windows
from app.ml.models.price_predictor import PricePredictorNet
from app.ml.registry import get_next_version, save_model, get_model_file_size
from app.ml.training.base_trainer import BaseTrainer
from app.models.ml import MLModel, MLTrainingRun
from app.models.ticker import Ticker
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PriceTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("price_predictor")

    async def build_datasets(self, db, config):
        pass  # Not used directly

    def build_model(self, config, input_dim=None):
        return PricePredictorNet(
            input_dim=config.get("input_dim", 6),  # OHLCV channels
            hidden_dim=config.get("hidden_dim", PRICE_HIDDEN),
            dropout=config.get("dropout", DEFAULT_DROPOUT),
            horizons=PRICE_HORIZONS,
        )

    def compute_metrics(self, model, dataloader):
        """Compute direction accuracy and magnitude MAE per horizon."""
        model.eval()
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch_x, batch_y in dataloader:
                batch_x = batch_x.to(self.device)
                outputs = model(batch_x).cpu()
                all_preds.append(outputs)
                all_labels.append(batch_y)

        all_preds = torch.cat(all_preds).numpy()
        all_labels = torch.cat(all_labels).numpy()

        metrics = {"samples": len(all_labels)}

        for i, h in enumerate(PRICE_HORIZONS):
            # Direction: predicted logit vs actual direction
            pred_dir = (all_preds[:, i * 2] > 0).astype(int)
            actual_dir = all_labels[:, i * 2].astype(int)
            dir_acc = float(np.mean(pred_dir == actual_dir))

            # Magnitude MAE
            pred_mag = np.abs(all_preds[:, i * 2 + 1])
            actual_mag = all_labels[:, i * 2 + 1]
            mag_mae = float(np.mean(np.abs(pred_mag - actual_mag)))

            metrics[f"dir_acc_{h}d"] = round(dir_acc, 4)
            metrics[f"mag_mae_{h}d"] = round(mag_mae, 4)

        # Overall direction accuracy
        all_dir_acc = []
        for i, h in enumerate(PRICE_HORIZONS):
            all_dir_acc.append(metrics[f"dir_acc_{h}d"])
        metrics["avg_dir_accuracy"] = round(float(np.mean(all_dir_acc)), 4)

        return metrics


class PricePredictionLoss(torch.nn.Module):
    """Combined loss: BCE for direction + SmoothL1 for magnitude."""

    def __init__(self, horizons=(5, 10, 20)):
        super().__init__()
        self.horizons = horizons
        self.bce = torch.nn.BCEWithLogitsLoss()
        self.smooth_l1 = torch.nn.SmoothL1Loss()

    def forward(self, pred, target):
        loss = 0
        for i in range(len(self.horizons)):
            # Direction loss
            loss += self.bce(pred[:, i * 2], target[:, i * 2])
            # Magnitude loss
            loss += self.smooth_l1(pred[:, i * 2 + 1], target[:, i * 2 + 1])
        return loss / len(self.horizons)


async def train_price_predictor(config: dict) -> int:
    """Full training pipeline for price predictor. Returns ml_model_id."""
    start_time = time.time()
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    # Create DB records first
    async with async_session_factory() as db:
        version = await get_next_version(db, "price_predictor")
        ml_model = MLModel(
            model_type="price_predictor",
            version=version,
            name=config.get("name", f"Price Predictor v{version}"),
            status="training",
            architecture={
                "type": "PricePredictorNet",
                "hidden_dim": config.get("hidden_dim", PRICE_HIDDEN),
                "dropout": config.get("dropout", DEFAULT_DROPOUT),
                "horizons": list(PRICE_HORIZONS),
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
        result = await db.execute(select(Ticker.id))
        ticker_ids = [r[0] for r in result.all()]

        from datetime import date as date_type
        date_from = date_type.fromisoformat(config.get("date_from", "2024-01-01"))
        date_to = date_type.fromisoformat(config.get("date_to", "2025-12-31"))

        windows = await extract_ohlcv_windows(
            db, ticker_ids, date_from, date_to,
            window_size=PRICE_SEQ_LEN, stride=config.get("stride", 5),
        )

        # Filter to only windows that have all 3 horizons
        windows = [w for w in windows if all(h in w.get("forward_returns", {}) for h in PRICE_HORIZONS)]

        if len(windows) < MIN_TRAINING_SAMPLES:
            raise ValueError(
                f"Only {len(windows)} windows with full forward returns. "
                f"Need at least {MIN_TRAINING_SAMPLES}."
            )

        n = len(windows)
        n_train = int(n * 0.70)
        n_val = int(n * 0.85)

        ml_model = await db.get(MLModel, model_id)
        ml_model.train_samples = n_train
        ml_model.val_samples = n_val - n_train
        ml_model.test_samples = n - n_val
        await db.commit()

    # Train
    try:
        model, history, best_epoch, train_metrics, val_metrics, test_metrics = await asyncio.to_thread(
            _train_price_sync, windows, config,
        )

        model_path, scaler_path = save_model(
            model, None, "price_predictor", version,
            metadata={"config": config, "horizons": list(PRICE_HORIZONS)},
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
            run.best_val_metric = val_metrics.get("avg_dir_accuracy")
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            f"Price predictor v{version} trained in {elapsed:.0f}s. "
            f"Test avg dir acc: {test_metrics.get('avg_dir_accuracy', 0):.4f}"
        )
        return model_id

    except Exception as e:
        logger.error(f"Price predictor training failed: {e}", exc_info=True)
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


def _train_price_sync(windows, config):
    """Synchronous training for price predictor."""
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    n = len(windows)
    n_train = int(n * 0.70)
    n_val = int(n * 0.85)

    train_ds = OHLCVWindowDataset(windows[:n_train], task="price")
    val_ds = OHLCVWindowDataset(windows[n_train:n_val], task="price")
    test_ds = OHLCVWindowDataset(windows[n_val:], task="price")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    # Input dim is 6 channels (OHLCV + returns) since the dataset permutes to (seq, channels)
    in_channels = windows[0]["tensor"].shape[0]  # typically 6

    model = PricePredictorNet(
        input_dim=in_channels,
        hidden_dim=config.get("hidden_dim", PRICE_HIDDEN),
        dropout=config.get("dropout", DEFAULT_DROPOUT),
        horizons=PRICE_HORIZONS,
    )

    criterion = PricePredictionLoss(horizons=PRICE_HORIZONS)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=DEFAULT_WEIGHT_DECAY)

    trainer = PriceTrainer()
    model, history, best_epoch = trainer.train_loop(
        model, train_loader, val_loader, criterion, optimizer, epochs,
    )

    train_metrics = trainer.compute_metrics(model, train_loader)
    val_metrics = trainer.compute_metrics(model, val_loader)
    test_metrics = trainer.compute_metrics(model, test_loader)

    return model, history, best_epoch, train_metrics, val_metrics, test_metrics
