from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.settings import SettingOut, SettingUpdate
from app.services.settings_service import get_all_settings, get_setting, update_setting

router = APIRouter()


@router.get("", response_model=list[SettingOut])
async def list_settings(db: AsyncSession = Depends(get_db)):
    return await get_all_settings(db)


@router.get("/{key}", response_model=SettingOut)
async def get_setting_by_key(key: str, db: AsyncSession = Depends(get_db)):
    setting = await get_setting(db, key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting


@router.put("/{key}", response_model=SettingOut)
async def update_setting_by_key(
    key: str, body: SettingUpdate, db: AsyncSession = Depends(get_db)
):
    setting = await update_setting(db, key, body.value)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting
