from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.runtime_schema import ensure_runtime_schema
from app.db.session import build_engine, build_session_factory
import app.models  # noqa: F401
from app.services.container import build_container
from app.workflows.orchestrator import build_workflow_orchestrator


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(settings, engine=engine)
    orchestrator = build_workflow_orchestrator(settings, session_factory=session_factory)
    container = build_container(settings, orchestrator=orchestrator)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await container.orchestrator.connect()
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
        with session_factory() as db:
            container.ingestion_service.ensure_knowledge_space(db)
            container.bootstrap_index(db)
        try:
            yield
        finally:
            await container.orchestrator.shutdown()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
