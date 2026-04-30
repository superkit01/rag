from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.chunking_strategies import ChunkingStrategy, FixedSizeStrategy, ParentChildStrategy

logger = logging.getLogger(__name__)


class ChunkingStrategyFactory:
    @staticmethod
    def create(settings: Settings) -> ChunkingStrategy:
        try:
            if settings.chunking_strategy == "fixed-size":
                return FixedSizeStrategy(settings.chunk_size, settings.chunk_overlap)
            if settings.chunking_strategy == "parent-child":
                return ParentChildStrategy(
                    parent_chunk_size=settings.parent_chunk_size,
                    parent_chunk_overlap=settings.parent_chunk_overlap,
                    child_chunk_size=settings.child_chunk_size,
                    child_chunk_overlap=settings.child_chunk_overlap,
                )
            raise ValueError(f"Unknown chunking strategy: {settings.chunking_strategy}")
        except Exception:
            logger.exception("Failed to create chunking strategy; falling back to fixed-size.")
            return FixedSizeStrategy(settings.chunk_size, settings.chunk_overlap)
