from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    environment: str
    search_backend: str
    workflow_mode: str


class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    language: str = "zh-CN"


class KnowledgeSpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    language: str
    created_at: datetime
    updated_at: datetime


class RecentQueryRead(BaseModel):
    id: str
    question: str
    confidence: float
    created_at: datetime


class DashboardSummary(BaseModel):
    document_count: int
    chunk_count: int
    trace_count: int
    eval_run_count: int
    recent_queries: list[RecentQueryRead]

