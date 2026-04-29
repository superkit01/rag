from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    knowledge_space_id: str
    name: str | None = None


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    knowledge_space_id: str
    created_at: datetime
    updated_at: datetime


class SessionUpdate(BaseModel):
    name: str | None = None
