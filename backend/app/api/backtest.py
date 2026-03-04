from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.backtest import (
    BacktestConfig,
    BacktestRunOut,
    BacktestRunListResponse,
    BacktestDetailOut,
    BacktestSignalListResponse,
    BatchRequest,
    BatchResponse,
    CompareResponse,
    SweepConfig,
    SweepResponse,
)
from app.services.backtest_service import (
    create_backtest_run,
    create_batch,
    create_sweep,
    list_backtest_runs,
    get_backtest_detail,
    get_backtest_signals,
    get_equity_curve,
    compare_runs,
    delete_backtest_run,
)

router = APIRouter()


@router.post("", response_model=BacktestRunOut)
async def create_backtest(
    config: BacktestConfig,
    db: AsyncSession = Depends(get_db),
):
    """Create and launch a new backtest run."""
    run = await create_backtest_run(db, config.model_dump(mode="json"))
    return {
        "id": run.id,
        "name": run.name,
        "status": run.status,
        "date_from": run.date_from,
        "date_to": run.date_to,
        "config": run.config,
        "results": run.results,
        "diagnostics": run.diagnostics,
        "signal_count": 0,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


@router.post("/batch", response_model=BatchResponse)
async def create_batch_backtests(
    batch: BatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create and launch multiple backtest runs."""
    configs = [c.model_dump(mode="json") for c in batch.configs]
    run_ids = await create_batch(db, configs)
    return {"run_ids": run_ids}


@router.post("/sweep", response_model=SweepResponse)
async def create_sweep_backtests(
    sweep: SweepConfig,
    db: AsyncSession = Depends(get_db),
):
    """Automated strategy sweep — generates a grid of parameter combinations and runs them all."""
    run_ids, total = await create_sweep(db, sweep.model_dump(mode="json"))
    return {"run_ids": run_ids, "total_combinations": total}


@router.get("", response_model=BacktestRunListResponse)
async def list_backtests(
    status: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List backtest runs with optional filters."""
    items, total = await list_backtest_runs(db, status, sort_by, sort_dir, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/compare", response_model=CompareResponse)
async def compare_backtests(
    ids: str = Query(..., description="Comma-separated run IDs"),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple backtest runs side-by-side."""
    try:
        run_ids = [int(x.strip()) for x in ids.split(",")]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated integers")
    runs = await compare_runs(db, run_ids)
    return {"runs": runs}


@router.get("/{backtest_id}", response_model=BacktestDetailOut)
async def get_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full backtest detail including results and portfolio simulation."""
    detail = await get_backtest_detail(db, backtest_id)
    if not detail:
        raise HTTPException(404, "Backtest run not found")
    return detail


@router.get("/{backtest_id}/signals", response_model=BacktestSignalListResponse)
async def get_signals(
    backtest_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated signals for a backtest run."""
    items, total = await get_backtest_signals(db, backtest_id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{backtest_id}/equity")
async def get_equity(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get equity curve data for charting."""
    curve = await get_equity_curve(db, backtest_id)
    return {"equity_curve": curve}


@router.delete("/{backtest_id}")
async def delete_backtest(
    backtest_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a backtest run and all associated data."""
    deleted = await delete_backtest_run(db, backtest_id)
    if not deleted:
        raise HTTPException(404, "Backtest run not found")
    return {"status": "deleted"}
