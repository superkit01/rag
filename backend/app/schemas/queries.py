from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnswerRequest(BaseModel):
    question: str = Field(min_length=2)
    knowledge_space_id: str | None = None
    knowledge_space_name: str | None = None
    session_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    max_citations: int = Field(default=4, ge=1, le=10)


class CitationRead(BaseModel):
    citation_id: str
    document_id: str
    document_title: str
    fragment_id: str
    section_title: str
    heading_path: list[str]
    page_number: int | None
    quote: str
    score: float


class SourceDocumentRead(BaseModel):
    document_id: str
    title: str
    score: float


class AnswerResponse(BaseModel):
    answer_trace_id: str
    answer: str
    citations: list[CitationRead]
    confidence: float
    source_documents: list[SourceDocumentRead]
    followup_queries: list[str]


class AnswerTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_space_id: str
    session_id: str | None = None
    question: str
    answer: str
    confidence: float
    citations: list[dict]
    source_documents: list[dict]
    followup_queries: list[str]
    created_at: datetime
