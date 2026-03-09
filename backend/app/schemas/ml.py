"""Pydantic schemas for ML endpoints."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrainRequest(BaseModel):
    model_type: str = Field(..., pattern=r"^(signal_scorer|pattern_recognizer|price_predictor|strategy_selector)$")
    name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    epochs: Optional[int] = Field(None, ge=5, le=500)
    batch_size: Optional[int] = Field(None, ge=8, le=512)
    lr: Optional[float] = Field(None, gt=0, lt=1)
    hidden_dim: Optional[int] = Field(None, ge=32, le=512)
    dropout: Optional[float] = Field(None, ge=0, le=0.9)


class MLModelOut(BaseModel):
    id: int
    model_type: str
    version: int
    name: Optional[str] = None
    status: str
    is_active: bool
    architecture: Optional[dict] = None
    hyperparameters: Optional[dict] = None
    train_samples: Optional[int] = None
    val_samples: Optional[int] = None
    test_samples: Optional[int] = None
    train_date_from: Optional[str] = None
    train_date_to: Optional[str] = None
    train_metrics: Optional[dict] = None
    val_metrics: Optional[dict] = None
    test_metrics: Optional[dict] = None
    training_time_seconds: Optional[float] = None
    inference_time_ms: Optional[float] = None
    file_size_mb: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TrainingRunOut(BaseModel):
    id: int
    ml_model_id: int
    status: str
    progress: Optional[str] = None
    current_epoch: Optional[int] = None
    total_epochs: Optional[int] = None
    epoch_history: Optional[list] = None
    best_epoch: Optional[int] = None
    best_val_loss: Optional[float] = None
    best_val_metric: Optional[float] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PredictRequest(BaseModel):
    model_type: str = "signal_scorer"
    ticker_symbols: Optional[list[str]] = None
    prediction_date: Optional[str] = None


class MLConfigOut(BaseModel):
    scoring_mode: str
    nn_weight: float
    active_models: dict


class MLConfigUpdate(BaseModel):
    scoring_mode: Optional[str] = Field(None, pattern=r"^(rule_based|nn_only|ensemble)$")
    nn_weight: Optional[float] = Field(None, ge=0, le=1)


class MLDashboardOut(BaseModel):
    models: list[MLModelOut]
    active_models: dict
    recent_training_runs: list[TrainingRunOut]
    scoring_mode: str
    nn_weight: float
    total_models: int
