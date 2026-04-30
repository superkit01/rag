from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.parser import ParsedSection


@dataclass(slots=True)
class PreparedChunk:
    fragment_id: str
    section_title: str
    heading_path: list[str]
    page_number: int | None
    start_offset: int
    end_offset: int
    token_count: int
    content: str
    chunk_type: str = "fixed"
    parent_id: str | None = None


class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        """Split parsed document sections into persisted chunks."""
