"""Signal Scorer training pipeline."""

import asyncio
import logging
import time
from collections import Counter
from datetime import date, datetime, timezone

import numpy as np
import torch
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader

from app.database import async_session_factory
from app.ml.config import (
    DEVICE, DEFAULT_EPOCHS, DEFAULT_BATCH_SIZE, DEFAULT_LR,
    DEFAULT_WEIGHT_DECAY, DEFAULT_DROPOUT, SIGNAL_SCORER_HIDDEN,
    MIN_TRAINING_SAMPLES,
)
from app.ml.dataset import SignalDataset
from app.ml.features import extract_signal_training_data, fit_scaler
from app.ml.models.signal_scorer import SignalScorerNet
from app.ml.registry import get_next_version, save_model, get_model_file_size
from app.ml.training.base_trainer import BaseTrainer
from app.ml.validation import generate_walk_forward_splits
from app.models.ml import MLModel, MLTrainingRun

logger = logging.getLogger(__name__)

OUTCOME_NAMES = ["win", "loss", "timeout"]


class SignalTrainer(BaseTrainer):
    def __init__(self):
        super().__init__("signal_scorer")

    async def build_datasets(self, db, config):
        date_from = date.fromisoformat(config["date_from"])
        date_to = date.fromisoformat(config["date_to"])

        X, y, feature_names = await extract_signal_training_data(db, date_from, date_to)
        return X, y, feature_names

    def build_model(self, config, input_dim):
        return SignalScorerNet(
            input_dim=input_dim,
            hidden_dim=config.get("hidden_dim", SIGNAL_SCORER_HIDDEN),
            dropout=config.get("dropout", DEFAULT_DROPOUT),
        )

    def compute_metrics(self, model, dataloader):
        model.eval()
        all_preds = []
        all_labels = []
        all_probs = []

        with torch.no_grad():
            for batch_x, batch_y in dataloader:
                batch_x = batch_x.to(self.device)
                outputs = model(batch_x)
                probs = torch.softmax(outputs, dim=-1).cpu()
                preds = outputs.argmax(dim=-1).cpu()
                all_preds.extend(preds.tolist())
                all_labels.extend(batch_y.tolist())
                all_probs.extend(probs.tolist())

        accuracy = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels) if all_labels else 0
        report = classification_report(
            all_labels, all_preds,
            labels=[0, 1, 2],
            target_names=OUTCOME_NAMES,
            output_dict=True,
            zero_division=0,
        )

        return {
            "accuracy": round(accuracy, 4),
            "precision_win": round(report["win"]["precision"], 4),
            "recall_win": round(report["win"]["recall"], 4),
            "f1_win": round(report["win"]["f1-score"], 4),
            "precision_loss": round(report["loss"]["precision"], 4),
            "recall_loss": round(report["loss"]["recall"], 4),
            "f1_loss": round(report["loss"]["f1-score"], 4),
            "samples": len(all_labels),
            "class_distribution": dict(Counter(all_labels)),
        }


async def train_signal_scorer(config: dict) -> int:
    """Full training pipeline for signal scorer. Returns ml_model_id."""
    start_time = time.time()
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    # Create DB records FIRST so progress/errors are always visible
    async with async_session_factory() as db:
        version = await get_next_version(db, "signal_scorer")
        ml_model = MLModel(
            model_type="signal_scorer",
            version=version,
            name=config.get("name", f"Signal Scorer v{version}"),
            status="training",
            architecture={
                "type": "SignalScorerNet",
                "hidden_dim": config.get("hidden_dim", SIGNAL_SCORER_HIDDEN),
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

    # Now extract data and train — errors will update the DB records above
    async with async_session_factory() as db:
        trainer = SignalTrainer()
        X, y, feature_names = await trainer.build_datasets(db, config)

        if len(X) < MIN_TRAINING_SAMPLES:
            raise ValueError(
                f"Only {len(X)} training samples found. Need at least {MIN_TRAINING_SAMPLES}. "
                f"Run more backtests with outcome tracking, or widen the date range."
            )

        # Simple train/val/test split (70/15/15)
        n = len(X)
        n_train = int(n * 0.70)
        n_val = int(n * 0.85)

        X_train, y_train = X[:n_train], y[:n_train]
        X_val, y_val = X[n_train:n_val], y[n_train:n_val]
        X_test, y_test = X[n_val:], y[n_val:]

        # Fit scaler on training data only
        scaler = fit_scaler(X_train)
        X_train = scaler.transform(X_train).astype(np.float32)
        X_val = scaler.transform(X_val).astype(np.float32)
        X_test = scaler.transform(X_test).astype(np.float32)

        # Update model with actual dimensions
        ml_model = await db.get(MLModel, model_id)
        ml_model.architecture["input_dim"] = X_train.shape[1]
        ml_model.feature_config = {"features": feature_names, "scaler": "StandardScaler"}
        ml_model.train_samples = len(X_train)
        ml_model.val_samples = len(X_val)
        ml_model.test_samples = len(X_test)
        await db.commit()

    # Build model and train (CPU-bound, run in thread)
    try:
        model, history, best_epoch, train_metrics, val_metrics, test_metrics = await asyncio.to_thread(
            _train_sync,
            X_train, y_train, X_val, y_val, X_test, y_test,
            config, feature_names,
        )

        # Save model artifacts
        model_path, scaler_path = save_model(
            model, scaler, "signal_scorer", version,
            metadata={"feature_names": feature_names, "config": config},
        )

        elapsed = time.time() - start_time

        # Update DB records
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
            run.best_val_metric = val_metrics.get("accuracy")
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

        logger.info(
            f"Signal scorer v{version} trained in {elapsed:.0f}s. "
            f"Test accuracy: {test_metrics.get('accuracy', 0):.4f}"
        )
        return model_id

    except Exception as e:
        logger.error(f"Signal scorer training failed: {e}", exc_info=True)
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


def _train_sync(X_train, y_train, X_val, y_val, X_test, y_test, config, feature_names):
    """Synchronous training function (runs in thread)."""
    epochs = config.get("epochs", DEFAULT_EPOCHS)
    batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
    lr = config.get("lr", DEFAULT_LR)

    train_ds = SignalDataset(X_train, y_train)
    val_ds = SignalDataset(X_val, y_val)
    test_ds = SignalDataset(X_test, y_test)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    input_dim = X_train.shape[1]
    model = SignalScorerNet(
        input_dim=input_dim,
        hidden_dim=config.get("hidden_dim", SIGNAL_SCORER_HIDDEN),
        dropout=config.get("dropout", DEFAULT_DROPOUT),
    )

    # Class weights for imbalanced data
    class_counts = np.bincount(y_train, minlength=3).astype(np.float32)
    class_weights = 1.0 / (class_counts + 1)
    class_weights = class_weights / class_weights.sum() * 3
    criterion = torch.nn.CrossEntropyLoss(
        weight=torch.tensor(class_weights, device=DEVICE)
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=DEFAULT_WEIGHT_DECAY)

    trainer = SignalTrainer()
    model, history, best_epoch = trainer.train_loop(
        model, train_loader, val_loader, criterion, optimizer, epochs,
    )

    # Compute final metrics
    train_metrics = trainer.compute_metrics(model, train_loader)
    val_metrics = trainer.compute_metrics(model, val_loader)
    test_metrics = trainer.compute_metrics(model, test_loader)

    return model, history, best_epoch, train_metrics, val_metrics, test_metrics
