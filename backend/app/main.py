from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables from ORM models (SQLite-compatible, no Alembic needed)
    from app.database import engine, Base
    import app.models  # noqa: F401 — ensure all models are registered on Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default settings
    from app.database import async_session_factory
    from app.services.settings_service import seed_default_settings

    async with async_session_factory() as db:
        await seed_default_settings(db)

    # Start scheduler
    from app.jobs.scheduler import start_scheduler, stop_scheduler

    await start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="North America Market Analyzer",
    description="Screen tickers, compute technical indicators, and generate ranked bullish signals.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
from app.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
