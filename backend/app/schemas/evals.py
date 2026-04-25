from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvalCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=2)
    expected_document_ids: list[str] = Field(default_factory=list)
    expected_snippets: list[str] = Field(default_factory=list)


class EvalRunRequest(BaseModel):
    knowledge_space_id: str | None = None
    knowledge_space_name: str | None = None
    cases: list[EvalCaseInput] = Field(default_factory=list)


class EvalCaseResult(BaseModel):
    name: str
    question: str
    returned_document_ids: list[str]
    hit: bool
    confidence: float


class EvalRunResponse(BaseModel):
    id: str
    knowledge_space_id: str
    workflow_id: str | None
    status: str
    attempt_count: int
    error_message: str | None
    total_cases: int
    completed_cases: int
    summary: dict
    created_at: datetime
    completed_at: datetime | None
    results: list[EvalCaseResult]
