from __future__ import annotations

from dataclasses import dataclass

from app.services.parser import ParsedSection
from app.services.text_utils import estimate_token_count, normalize_whitespace


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


class HierarchicalChunker:
    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 100) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        prepared: list[PreparedChunk] = []
        counter = 1
        for section in sections:
            text = normalize_whitespace(section.content)
            if not text:
                continue
            for start, end, snippet in self._split_text(text):
                prepared.append(
                    PreparedChunk(
                        fragment_id=f"frag-{counter:04d}",
                        section_title=section.title,
                        heading_path=section.heading_path,
                        page_number=section.page_number,
                        start_offset=start,
                        end_offset=end,
                        token_count=estimate_token_count(snippet),
                        content=snippet,
                    )
                )
                counter += 1
        return prepared

    def _split_text(self, text: str) -> list[tuple[int, int, str]]:
        if len(text) <= self.chunk_size:
            return [(0, len(text), text)]

        windows: list[tuple[int, int, str]] = []
        start = 0
        while start < len(text):
            tentative_end = min(start + self.chunk_size, len(text))
            end = tentative_end
            if tentative_end < len(text):
                breakpoint = text.rfind("。", start, tentative_end)
                if breakpoint == -1:
                    breakpoint = text.rfind(" ", start, tentative_end)
                if breakpoint > start + int(self.chunk_size * 0.6):
                    end = breakpoint + 1
            snippet = text[start:end].strip()
            if snippet:
                windows.append((start, end, snippet))
            if end >= len(text):
                break
            start = max(end - self.chunk_overlap, start + 1)
        return windows

