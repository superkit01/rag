from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.answering import AnswerService
from app.services.chunking_factory import ChunkingStrategyFactory
from app.services.evaluation import EvaluationService
from app.services.indexing import InMemorySearchBackend, OpenSearchSearchBackend
from app.services.ingestion import IngestionService
from app.services.llm import build_answer_provider, build_embedding_provider
from app.services.object_storage import build_object_storage
from app.services.parser import CompositeDocumentParser


@dataclass(slots=True)
class UnconfiguredWorkflowOrchestrator:
    mode: str = "unconfigured"

    async def connect(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


class ServiceContainer:
    def __init__(self, settings: Settings, orchestrator: object | None = None) -> None:
        self.settings = settings
        self.embedding_provider = build_embedding_provider(settings)
        self.search_backend = build_search_backend(settings, self.embedding_provider)
        self.chunker = ChunkingStrategyFactory.create(settings)
        self.parser = CompositeDocumentParser(settings.object_storage_local_root)
        self.object_storage = build_object_storage(settings)
        self.answer_provider = build_answer_provider(settings)
        self.orchestrator = orchestrator or UnconfiguredWorkflowOrchestrator()
        self.ingestion_service = IngestionService(
            self.parser,
            self.chunker,
            self.search_backend,
            self.embedding_provider,
            self.object_storage,
        )
        self.answer_service = AnswerService(settings, self.ingestion_service, self.search_backend, self.answer_provider)
        self.evaluation_service = EvaluationService(self.ingestion_service, self.answer_service)

    def bootstrap_index(self, db: Session) -> None:
        bootstrap = getattr(self.search_backend, "bootstrap_from_database", None)
        if callable(bootstrap):
            bootstrap(db)


def build_container(settings: Settings, orchestrator: object | None = None) -> ServiceContainer:
    return ServiceContainer(settings, orchestrator=orchestrator)


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def build_search_backend(settings: Settings, embedding_provider: object) -> InMemorySearchBackend | OpenSearchSearchBackend:
    if settings.search_backend == "memory":
        return InMemorySearchBackend(embedding_provider)
    if settings.search_backend == "opensearch":
        return OpenSearchSearchBackend(
            embedding_provider,
            base_url=settings.opensearch_url,
            index_name=settings.opensearch_index,
        )
    raise ValueError("Unsupported SEARCH_BACKEND. Expected one of: memory, opensearch.")
