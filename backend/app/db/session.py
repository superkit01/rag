from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def build_engine(settings: Settings | None = None):
    current_settings = settings or get_settings()
    connect_args = {"check_same_thread": False} if current_settings.database_url.startswith("sqlite") else {}
    return create_engine(current_settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def build_session_factory(settings: Settings | None = None, engine=None):
    current_engine = engine or build_engine(settings)
    return sessionmaker(bind=current_engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
