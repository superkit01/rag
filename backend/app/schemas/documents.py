from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceImportRequest(BaseModel):
    knowledge_space_id: str | None = None
    knowledge_space_name: str | None = None
    title: str = Field(min_length=1, max_length=255)
    uploaded_file_name: str | None = None
    uploaded_file_base64: str | None = None
    source_type: str | None = None
    connector_id: str | None = None
    visibility_scope: str = "internal"
    source_acl_refs: list[str] = Field(default_factory=list)
    source_metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_source(self) -> "SourceImportRequest":
        if not self.uploaded_file_base64:
            raise ValueError("uploaded_file_base64 must be provided.")
        if not self.uploaded_file_name:
            raise ValueError("uploaded_file_name must be provided when uploaded_file_base64 is used.")
        return self


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_space_id: str
    job_kind: str
    source_uri: str
    workflow_id: str | None
    status: str
    attempt_count: int
    error_message: str | None
    imported_document_id: str | None
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    fragment_id: str
    chunk_type: str = "fixed"
    parent_id: str | None = None
    section_title: str
    heading_path: list[str]
    page_number: int | None
    start_offset: int
    end_offset: int
    token_count: int
    content: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_space_id: str
    title: str
    source_type: str
    source_uri: str
    storage_uri: str | None
    visibility_scope: str
    source_acl_refs: list[str]
    connector_id: str | None
    ingestion_job_id: str | None
    status: str
    checksum: str | None
    source_metadata: dict
    created_at: datetime
    updated_at: datetime
    chunks: list[ChunkRead] = Field(default_factory=list)


class DocumentListItem(BaseModel):
    id: str
    title: str
    source_type: str
    status: str
    chunk_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]


class SourceImportResponse(BaseModel):
    ingestion_job: IngestionJobRead
    document: DocumentRead | None = None


class ReindexResponse(BaseModel):
    ingestion_job: IngestionJobRead
    document: DocumentRead | None = None


class FragmentRead(BaseModel):
    document_id: str
    fragment_id: str
    chunk_type: str = "fixed"
    parent_id: str | None = None
    section_title: str
    heading_path: list[str]
    page_number: int | None
    content: str


class DocumentDeleteResponse(BaseModel):
    id: str
    title: str
