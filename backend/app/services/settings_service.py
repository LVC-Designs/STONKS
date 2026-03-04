import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting

logger = logging.getLogger(__name__)


async def get_all_settings(db: AsyncSession) -> list[Setting]:
    result = await db.execute(select(Setting).order_by(Setting.key))
    return list(result.scalars().all())


async def get_setting(db: AsyncSession, key: str) -> Setting | None:
    result = await db.execute(select(Setting).where(Setting.key == key))
    return result.scalar_one_or_none()


async def get_setting_value(db: AsyncSession, key: str, default: Any = None) -> Any:
    setting = await get_setting(db, key)
    if setting:
        return setting.value
    return default


async def update_setting(db: AsyncSession, key: str, value: Any) -> Setting | None:
    setting = await get_setting(db, key)
    if not setting:
        return None
    setting.value = value
    await db.commit()
    await db.refresh(setting)
    logger.info(f"Updated setting: {key}")
    return setting


async def seed_default_settings(db: AsyncSession):
    """Seed default settings if they don't exist."""
    defaults = [
        ("polygon_api_key", "", "Polygon.io API key"),
        ("finnhub_api_key", "", "Finnhub API key"),
        ("signal_target_pct", 5.0, "Signal success target: price increase %"),
        ("signal_target_days", 20, "Signal success target: max trading days"),
        ("signal_max_drawdown_pct", -3.0, "Signal success target: max drawdown %"),
        ("screener_min_dollar_volume", 100000, "Minimum average dollar volume for screener"),
        ("screener_min_price", 1.0, "Minimum price for screener"),
        ("schedule_daily_cron", "0 18 * * 1-5", "Daily refresh cron schedule (ET)"),
        ("schedule_hourly_enabled", True, "Enable hourly refresh for liquid tickers"),
    ]

    for key, value, description in defaults:
        existing = await get_setting(db, key)
        if not existing:
            db.add(Setting(key=key, value=value, description=description))

    await db.commit()
    logger.info("Default settings seeded")
