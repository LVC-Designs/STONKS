from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class SettingOut(BaseModel):
    key: str
    value: Any
    description: Optional[str] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: Any
