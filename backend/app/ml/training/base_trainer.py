"""Abstract base trainer with standard train/eval loop."""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import numpy as np
import torch
from torch.utils.data import DataLoader

from app.ml.config import DEVICE, DEFAULT_PATIENCE

logger = logging.getLogger(__name__)


class BaseTrainer(ABC):
    """Base class for ML model trainers.

    Subclasses implement build_dataset, build_model, and compute_metrics.
    """

    def __init__(self, model_type: str):
        self.model_type = model_type
        self.device = DEVICE

    @abstractmethod
    async def build_datasets(self, db, config: dict) -> tuple:
        """Build train/val/test datasets from DB data.

        Returns (train_dataset, val_dataset, test_dataset, scaler, metadata).
        """
        ...

    @abstractmethod
    def build_model(self, config: dict, input_dim: int) -> torch.nn.Module:
        """Instantiate the neural network."""
        ...

    @abstractmethod
    def compute_metrics(self, model, dataloader) -> dict:
        """Compute evaluation metrics on a dataset."""
        ...

    def train_loop(
        self,
        model: torch.nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion,
        optimizer,
        epochs: int,
        patience: int = DEFAULT_PATIENCE,
        progress_callback=None,
    ) -> tuple[torch.nn.Module, list[dict], int]:
        """Standard training loop with early stopping.

        Returns (best_model_state, epoch_history, best_epoch).
        """
        model.to(self.device)
        best_val_loss = float("inf")
        best_state = None
        best_epoch = 0
        patience_counter = 0
        history = []

        for epoch in range(1, epochs + 1):
            # Train
            model.train()
            train_losses = []
            train_correct = 0
            train_total = 0

            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

                train_losses.append(loss.item())
                if batch_y.dim() == 1 and batch_y.dtype == torch.long:
                    preds = outputs.argmax(dim=-1)
                    train_correct += (preds == batch_y).sum().item()
                    train_total += len(batch_y)

            # Validate
            model.eval()
            val_losses = []
            val_correct = 0
            val_total = 0

            with torch.no_grad():
                for batch_x, batch_y in val_loader:
                    batch_x = batch_x.to(self.device)
                    batch_y = batch_y.to(self.device)
                    outputs = model(batch_x)
                    loss = criterion(outputs, batch_y)
                    val_losses.append(loss.item())

                    if batch_y.dim() == 1 and batch_y.dtype == torch.long:
                        preds = outputs.argmax(dim=-1)
                        val_correct += (preds == batch_y).sum().item()
                        val_total += len(batch_y)

            train_loss = float(np.mean(train_losses))
            val_loss = float(np.mean(val_losses))
            train_acc = train_correct / train_total if train_total > 0 else None
            val_acc = val_correct / val_total if val_total > 0 else None

            epoch_data = {
                "epoch": epoch,
                "train_loss": round(train_loss, 6),
                "val_loss": round(val_loss, 6),
            }
            if train_acc is not None:
                epoch_data["train_acc"] = round(train_acc, 4)
                epoch_data["val_acc"] = round(val_acc, 4)

            history.append(epoch_data)

            if progress_callback:
                progress_callback(epoch, epochs, epoch_data)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                best_epoch = epoch
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch} (best: {best_epoch})")
                    break

        # Restore best model
        if best_state:
            model.load_state_dict(best_state)

        return model, history, best_epoch
