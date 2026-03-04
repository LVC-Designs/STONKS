from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import JSON as JSONB
from sqlalchemy.sql import func
from app.database import Base


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True)
    job_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    tickers_processed = Column(Integer, default=0)
    errors = Column(JSONB)
    summary = Column(JSONB)
