"""Model registry — save/load/version management for trained models."""

import json
import logging
import os
import time

import joblib
import torch
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.config import MODELS_DIR, DEVICE
from app.models.ml import MLModel

logger = logging.getLogger(__name__)


async def get_next_version(db: AsyncSession, model_type: str) -> int:
    """Get the next version number for a model type."""
    result = await db.execute(
        select(func.max(MLModel.version)).where(MLModel.model_type == model_type)
    )
    max_v = result.scalar()
    return (max_v or 0) + 1


def save_model(
    model: torch.nn.Module,
    scaler,
    model_type: str,
    version: int,
    metadata: dict | None = None,
) -> tuple[str, str]:
    """Save a trained model and scaler to disk.

    Returns (model_path, scaler_path) relative to MODELS_DIR.
    """
    model_dir = os.path.join(MODELS_DIR, model_type, f"v{version}")
    os.makedirs(model_dir, exist_ok=True)

    model_path = os.path.join(model_dir, "model.pt")
    torch.save(model.state_dict(), model_path)

    scaler_path = os.path.join(model_dir, "scaler.pkl")
    if scaler is not None:
        joblib.dump(scaler, scaler_path)

    if metadata:
        meta_path = os.path.join(model_dir, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    rel_model = os.path.relpath(model_path, MODELS_DIR)
    rel_scaler = os.path.relpath(scaler_path, MODELS_DIR)

    # File size
    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    logger.info(f"Saved {model_type} v{version}: {size_mb:.2f} MB")

    return rel_model, rel_scaler


def load_model(model_class, model_path: str, **kwargs) -> torch.nn.Module:
    """Load a trained model from disk."""
    full_path = os.path.join(MODELS_DIR, model_path)
    model = model_class(**kwargs)
    model.load_state_dict(torch.load(full_path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE)
    model.eval()
    return model


def load_scaler(scaler_path: str):
    """Load a fitted scaler from disk."""
    full_path = os.path.join(MODELS_DIR, scaler_path)
    return joblib.load(full_path)


async def deploy_model(db: AsyncSession, model_id: int) -> bool:
    """Set a model as active (deactivate others of same type)."""
    model = await db.get(MLModel, model_id)
    if not model:
        return False

    # Deactivate existing active model of this type
    existing = await db.execute(
        select(MLModel).where(
            MLModel.model_type == model.model_type,
            MLModel.is_active == True,
        )
    )
    for m in existing.scalars().all():
        m.is_active = False
        m.status = "trained"

    model.is_active = True
    model.status = "deployed"
    await db.commit()
    logger.info(f"Deployed {model.model_type} v{model.version} (id={model_id})")
    return True


async def get_active_model(db: AsyncSession, model_type: str) -> MLModel | None:
    """Get the currently active (deployed) model for a type."""
    result = await db.execute(
        select(MLModel).where(
            MLModel.model_type == model_type,
            MLModel.is_active == True,
        )
    )
    return result.scalars().first()


def get_model_file_size(model_path: str) -> float:
    """Get model file size in MB."""
    full_path = os.path.join(MODELS_DIR, model_path)
    if os.path.exists(full_path):
        return round(os.path.getsize(full_path) / (1024 * 1024), 2)
    return 0
