"""ML model registry, training runs, and prediction log tables."""

from sqlalchemy import (
    Column, Integer, Numeric, String, Boolean, Date, DateTime, ForeignKey,
    Text, Index, UniqueConstraint,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.sql import func

from app.database import Base


class MLModel(Base):
    """Registry entry for a trained ML model."""
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True)
    model_type = Column(String(50), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    name = Column(String(200))
    status = Column(String(20), default="trained")
    is_active = Column(Boolean, default=False)

    architecture = Column(JSONB)
    hyperparameters = Column(JSONB)
    feature_config = Column(JSONB)

    train_date_from = Column(String(10))
    train_date_to = Column(String(10))
    val_date_from = Column(String(10))
    val_date_to = Column(String(10))
    test_date_from = Column(String(10))
    test_date_to = Column(String(10))

    train_samples = Column(Integer)
    val_samples = Column(Integer)
    test_samples = Column(Integer)

    train_metrics = Column(JSONB)
    val_metrics = Column(JSONB)
    test_metrics = Column(JSONB)

    model_path = Column(String(500))
    scaler_path = Column(String(500))

    training_time_seconds = Column(Numeric(10, 2))
    inference_time_ms = Column(Numeric(8, 2))
    file_size_mb = Column(Numeric(8, 2))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MLTrainingRun(Base):
    """Individual training run with epoch-level metrics."""
    __tablename__ = "ml_training_runs"

    id = Column(Integer, primary_key=True)
    ml_model_id = Column(
        Integer, ForeignKey("ml_models.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    status = Column(String(20), default="running")
    progress = Column(String(300))
    current_epoch = Column(Integer)
    total_epochs = Column(Integer)

    epoch_history = Column(JSONB)
    best_epoch = Column(Integer)
    best_val_loss = Column(Numeric(10, 6))
    best_val_metric = Column(Numeric(10, 6))

    config_snapshot = Column(JSONB)
    error_message = Column(Text)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))


class MLPrediction(Base):
    """Log of NN predictions for auditing and analysis."""
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True)
    ml_model_id = Column(Integer, ForeignKey("ml_models.id", ondelete="SET NULL"), index=True)
    model_type = Column(String(50), nullable=False, index=True)

    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False, index=True)
    prediction_date = Column(Date, nullable=False, index=True)

    prediction = Column(JSONB, nullable=False)
    ensemble_score = Column(Numeric(5, 2))
    rule_based_score = Column(Numeric(5, 2))
    nn_score = Column(Numeric(5, 2))

    actual_outcome = Column(String(20))
    actual_return = Column(Numeric(8, 4))

    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_ml_pred_date", "prediction_date"),
    )
