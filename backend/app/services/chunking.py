from __future__ import annotations

from app.services.chunking_strategies.base import PreparedChunk
from app.services.chunking_strategies.fixed_size import FixedSizeStrategy

HierarchicalChunker = FixedSizeStrategy

__all__ = ["FixedSizeStrategy", "HierarchicalChunker", "PreparedChunk"]
