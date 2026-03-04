from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class JobRunOut(BaseModel):
    id: int
    job_name: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    tickers_processed: int = 0
    errors: Optional[Any] = None
    summary: Optional[Any] = None

    model_config = {"from_attributes": True}


class JobStatusOut(BaseModel):
    scheduler_running: bool
    next_runs: dict[str, Optional[str]] = {}


class JobTriggerResponse(BaseModel):
    job_run_id: int
    status: str
