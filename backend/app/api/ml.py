"""ML API endpoints — model management, training, inference, config."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ml import MLModel, MLTrainingRun, MLPrediction
from app.schemas.ml import (
    TrainRequest, MLModelOut, TrainingRunOut, PredictRequest,
    MLConfigOut, MLConfigUpdate, MLDashboardOut,
)
from app.ml.config import MODEL_TYPES

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------

@router.get("/models", response_model=list[MLModelOut])
async def list_models(
    model_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(MLModel).order_by(desc(MLModel.created_at))
    if model_type:
        query = query.where(MLModel.model_type == model_type)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    models = result.scalars().all()
    return [_model_to_out(m) for m in models]


@router.get("/models/{model_id}", response_model=MLModelOut)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(MLModel, model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    return _model_to_out(model)


@router.delete("/models/{model_id}")
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(MLModel, model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    await db.delete(model)
    await db.commit()
    return {"deleted": True}


@router.post("/models/{model_id}/deploy")
async def deploy_model(model_id: int, db: AsyncSession = Depends(get_db)):
    from app.ml.registry import deploy_model as _deploy
    from app.ml.inference.signal_inference import clear_cache
    ok = await _deploy(db, model_id)
    if not ok:
        raise HTTPException(404, "Model not found")
    clear_cache()
    return {"deployed": True}


@router.post("/models/{model_id}/archive")
async def archive_model(model_id: int, db: AsyncSession = Depends(get_db)):
    model = await db.get(MLModel, model_id)
    if not model:
        raise HTTPException(404, "Model not found")
    model.status = "archived"
    model.is_active = False
    await db.commit()
    return {"archived": True}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

@router.post("/train")
async def train_model(req: TrainRequest, db: AsyncSession = Depends(get_db)):
    """Launch model training in background."""
    if req.model_type == "signal_scorer":
        from app.ml.training.signal_trainer import train_signal_scorer

        config = {
            "date_from": req.date_from or "2024-01-01",
            "date_to": req.date_to or "2025-12-31",
            "name": req.name,
        }
        if req.epochs:
            config["epochs"] = req.epochs
        if req.batch_size:
            config["batch_size"] = req.batch_size
        if req.lr:
            config["lr"] = req.lr
        if req.hidden_dim:
            config["hidden_dim"] = req.hidden_dim
        if req.dropout is not None:
            config["dropout"] = req.dropout

        # Launch in background
        task = asyncio.create_task(_run_training(train_signal_scorer, config))
        return {"status": "training_started", "model_type": req.model_type}
    else:
        raise HTTPException(501, f"Training for {req.model_type} not yet implemented")


async def _run_training(train_fn, config: dict):
    """Wrapper to run training and catch errors."""
    try:
        model_id = await train_fn(config)
        logger.info(f"Training completed: model_id={model_id}")
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)


@router.post("/backfill-outcomes")
async def backfill_signal_outcomes(
    target_pct: float = Query(5.0, description="Target gain %"),
    target_days: int = Query(20, description="Max days to hold"),
    max_drawdown_pct: float = Query(3.0, description="Stop-loss %"),
    db: AsyncSession = Depends(get_db),
):
    """Backfill outcome labels on existing signals using forward OHLCV data.

    This gives the signal scorer training data without needing to run backtests.
    Uses signal_date close price as entry price.
    """
    from app.models.signal import Signal
    from app.models.ohlcv import OHLCVDaily

    # Get signals without real outcomes (pending or NULL)
    result = await db.execute(
        select(Signal).where(
            (Signal.outcome.is_(None)) | (Signal.outcome == "pending")
        ).order_by(Signal.signal_date)
    )
    signals = list(result.scalars().all())

    if not signals:
        return {"message": "No signals to backfill", "updated": 0}

    updated = 0
    for sig in signals:
        # Get entry day close price
        result = await db.execute(
            select(OHLCVDaily).where(
                OHLCVDaily.ticker_id == sig.ticker_id,
                OHLCVDaily.trade_date == sig.signal_date,
            )
        )
        entry_bar = result.scalar_one_or_none()
        if not entry_bar or not entry_bar.close:
            continue

        entry = float(entry_bar.close)
        if entry <= 0:
            continue

        # Get forward OHLCV bars
        result = await db.execute(
            select(OHLCVDaily)
            .where(
                OHLCVDaily.ticker_id == sig.ticker_id,
                OHLCVDaily.trade_date > sig.signal_date,
            )
            .order_by(OHLCVDaily.trade_date)
            .limit(target_days)
        )
        bars = list(result.scalars().all())

        if not bars:
            continue

        outcome = "timeout"
        actual_return = 0.0
        days_held = len(bars)

        for i, bar in enumerate(bars):
            high = float(bar.high) if bar.high else entry
            low = float(bar.low) if bar.low else entry
            close = float(bar.close) if bar.close else entry

            # Check stop-loss hit
            drawdown = (low - entry) / entry * 100
            if drawdown <= -max_drawdown_pct:
                outcome = "loss"
                actual_return = -max_drawdown_pct
                days_held = i + 1
                break

            # Check target hit
            gain = (high - entry) / entry * 100
            if gain >= target_pct:
                outcome = "win"
                actual_return = target_pct
                days_held = i + 1
                break

            actual_return = (close - entry) / entry * 100

        sig.outcome = outcome
        sig.actual_return = round(actual_return, 4)
        sig.days_to_target = days_held
        updated += 1

    await db.commit()

    # Count outcomes
    result = await db.execute(
        text("SELECT outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL GROUP BY outcome")
    )
    counts = {row[0]: row[1] for row in result.all()}

    return {
        "message": f"Backfilled {updated} signal outcomes",
        "updated": updated,
        "outcomes": counts,
    }


@router.get("/training/{run_id}", response_model=TrainingRunOut)
async def get_training_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(MLTrainingRun, run_id)
    if not run:
        raise HTTPException(404, "Training run not found")
    return _run_to_out(run)


@router.get("/training", response_model=list[TrainingRunOut])
async def list_training_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(MLTrainingRun)
        .order_by(desc(MLTrainingRun.started_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    runs = result.scalars().all()
    return [_run_to_out(r) for r in runs]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@router.get("/config", response_model=MLConfigOut)
async def get_ml_config(db: AsyncSession = Depends(get_db)):
    from app.services.settings_service import get_setting_value
    scoring_mode = await get_setting_value(db, "scoring_mode", "rule_based")
    nn_weight = float(await get_setting_value(db, "nn_weight", "0.5"))

    # Get active models
    active_models = {}
    for mt in MODEL_TYPES:
        result = await db.execute(
            select(MLModel.id, MLModel.version).where(
                MLModel.model_type == mt, MLModel.is_active == True
            )
        )
        row = result.first()
        if row:
            active_models[mt] = {"id": row[0], "version": row[1]}

    return MLConfigOut(scoring_mode=scoring_mode, nn_weight=nn_weight, active_models=active_models)


@router.put("/config", response_model=MLConfigOut)
async def update_ml_config(req: MLConfigUpdate, db: AsyncSession = Depends(get_db)):
    from app.services.settings_service import update_setting
    if req.scoring_mode is not None:
        await update_setting(db, "scoring_mode", req.scoring_mode)
    if req.nn_weight is not None:
        await update_setting(db, "nn_weight", str(req.nn_weight))
    return await get_ml_config(db)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=MLDashboardOut)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    config = await get_ml_config(db)

    # All models
    result = await db.execute(
        select(MLModel).order_by(desc(MLModel.created_at)).limit(20)
    )
    models = [_model_to_out(m) for m in result.scalars().all()]

    # Recent training runs
    result = await db.execute(
        select(MLTrainingRun).order_by(desc(MLTrainingRun.started_at)).limit(10)
    )
    runs = [_run_to_out(r) for r in result.scalars().all()]

    # Total models
    total = (await db.execute(select(func.count(MLModel.id)))).scalar() or 0

    return MLDashboardOut(
        models=models,
        active_models=config.active_models,
        recent_training_runs=runs,
        scoring_mode=config.scoring_mode,
        nn_weight=config.nn_weight,
        total_models=total,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _model_to_out(m: MLModel) -> MLModelOut:
    return MLModelOut(
        id=m.id,
        model_type=m.model_type,
        version=m.version,
        name=m.name,
        status=m.status,
        is_active=m.is_active,
        architecture=m.architecture,
        hyperparameters=m.hyperparameters,
        train_samples=m.train_samples,
        val_samples=m.val_samples,
        test_samples=m.test_samples,
        train_date_from=m.train_date_from,
        train_date_to=m.train_date_to,
        train_metrics=m.train_metrics,
        val_metrics=m.val_metrics,
        test_metrics=m.test_metrics,
        training_time_seconds=float(m.training_time_seconds) if m.training_time_seconds else None,
        inference_time_ms=float(m.inference_time_ms) if m.inference_time_ms else None,
        file_size_mb=float(m.file_size_mb) if m.file_size_mb else None,
        created_at=m.created_at,
    )


def _run_to_out(r: MLTrainingRun) -> TrainingRunOut:
    return TrainingRunOut(
        id=r.id,
        ml_model_id=r.ml_model_id,
        status=r.status,
        progress=r.progress,
        current_epoch=r.current_epoch,
        total_epochs=r.total_epochs,
        epoch_history=r.epoch_history,
        best_epoch=r.best_epoch,
        best_val_loss=float(r.best_val_loss) if r.best_val_loss else None,
        best_val_metric=float(r.best_val_metric) if r.best_val_metric else None,
        error_message=r.error_message,
        started_at=r.started_at,
        finished_at=r.finished_at,
    )
