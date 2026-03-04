"""API endpoints for quant backtesting framework."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.quant_backtest import (
    QuantSweepRequest,
    QuantBacktestOut,
    QuantBacktestListResponse,
    QuantBacktestDetailOut,
)
from app.services.quant_backtest_service import (
    create_quant_backtest,
    list_quant_backtests,
    get_quant_backtest_detail,
    delete_quant_backtest,
)

router = APIRouter()


@router.post("", response_model=QuantBacktestOut)
async def create_quant_sweep(
    req: QuantSweepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Launch a disciplined quant backtest sweep.

    Workflow: optimize on TRAIN → select top K → evaluate on VAL → run winner on OOS.
    Supports single split mode and walk-forward rolling windows.
    """
    config = req.model_dump(mode="json")
    qb = await create_quant_backtest(db, config)
    return {
        "id": qb.id,
        "name": qb.name,
        "mode": qb.mode,
        "status": qb.status,
        "config": qb.config,
        "selected_config": qb.selected_config,
        "objective": qb.objective,
        "stability_score": None,
        "results": qb.results,
        "diagnostics": qb.diagnostics,
        "warnings": qb.warnings,
        "candidates_count": qb.candidates_count or 0,
        "progress": qb.progress,
        "created_at": qb.created_at,
        "finished_at": qb.finished_at,
    }


@router.get("", response_model=QuantBacktestListResponse)
async def list_quant(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List quant backtest runs."""
    items, total = await list_quant_backtests(db, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{qb_id}", response_model=QuantBacktestDetailOut)
async def get_quant_detail(
    qb_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full quant backtest detail including all candidates."""
    detail = await get_quant_backtest_detail(db, qb_id)
    if not detail:
        raise HTTPException(404, "Quant backtest not found")
    return detail


@router.delete("/{qb_id}")
async def delete_quant(
    qb_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a quant backtest and all its candidates."""
    deleted = await delete_quant_backtest(db, qb_id)
    if not deleted:
        raise HTTPException(404, "Quant backtest not found")
    return {"status": "deleted"}
