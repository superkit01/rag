from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.chunking_strategies.base import ChunkingStrategy, PreparedChunk
from app.services.chunking_strategies.fixed_size import FixedSizeStrategy
from app.services.indexing import EmbeddingProvider, cosine_similarity
from app.services.parser import ParsedSection
from app.services.text_utils import estimate_token_count, normalize_whitespace


@dataclass(slots=True)
class SemanticUnit:
    content: str
    start_offset: int
    end_offset: int


@dataclass(slots=True)
class SemanticWindow:
    content: str
    first_unit_index: int


class SemanticStrategy(ChunkingStrategy):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        max_chunk_size: int = 500,
        similarity_threshold: float = 0.75,
        window_size: int = 300,
        overlap_ratio: float = 0.3,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.max_chunk_size = max(20, max_chunk_size)
        self.similarity_threshold = similarity_threshold
        self.window_size = max(20, window_size)
        self.overlap_ratio = min(0.89, max(0.0, overlap_ratio))
        self.long_unit_splitter = FixedSizeStrategy(self.max_chunk_size, 0)

    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        prepared: list[PreparedChunk] = []
        counter = 1

        for section in sections:
            text = normalize_whitespace(section.content)
            if not text:
                continue

            units = self._split_units(text)
            boundaries = self._find_semantic_boundaries(text, units)
            for start, end, content in self._assemble_chunks(text, units, boundaries):
                prepared.append(
                    PreparedChunk(
                        fragment_id=f"semantic-{counter:04d}",
                        section_title=section.title,
                        heading_path=section.heading_path,
                        page_number=section.page_number,
                        start_offset=start,
                        end_offset=end,
                        token_count=estimate_token_count(content),
                        content=content,
                        chunk_type="fixed",
                        parent_id=None,
                    )
                )
                counter += 1

        return prepared

    def _split_units(self, text: str) -> list[SemanticUnit]:
        units: list[SemanticUnit] = []
        for match in re.finditer(r".+?(?:[。！？；.!?;]+|$)", text):
            content = match.group(0)
            if not content:
                continue
            leading_trimmed = len(content) - len(content.lstrip())
            trailing_trimmed = len(content.rstrip())
            start = match.start() + leading_trimmed
            end = match.start() + trailing_trimmed
            snippet = text[start:end]
            if snippet:
                units.append(SemanticUnit(content=snippet, start_offset=start, end_offset=end))
        return units

    def _find_semantic_boundaries(self, source_text: str, units: list[SemanticUnit]) -> set[int]:
        windows = self._build_windows(source_text, units)
        if len(windows) < 2:
            return set()

        embeddings = self.embedding_provider.embed_many([window.content for window in windows])
        if len(embeddings) != len(windows):
            raise ValueError(
                "Embedding provider returned a different number of embeddings than requested."
            )

        boundaries: set[int] = set()
        for index in range(len(windows) - 1):
            similarity = cosine_similarity(embeddings[index], embeddings[index + 1])
            if similarity < self.similarity_threshold:
                boundaries.add(windows[index + 1].first_unit_index)
        return boundaries

    def _build_windows(self, source_text: str, units: list[SemanticUnit]) -> list[SemanticWindow]:
        windows: list[SemanticWindow] = []
        if not units:
            return windows

        step_size = max(1, int(self.window_size * (1 - self.overlap_ratio)))
        unit_index = 0
        while unit_index < len(units):
            content_parts: list[str] = []
            end_index = unit_index
            accumulated_length = 0
            while end_index < len(units) and (accumulated_length < self.window_size or not content_parts):
                next_length = len(units[end_index].content)
                content_parts.append(units[end_index].content)
                accumulated_length += next_length
                end_index += 1

            content = source_text[units[unit_index].start_offset : units[end_index - 1].end_offset]
            windows.append(SemanticWindow(content=content, first_unit_index=unit_index))
            if end_index >= len(units):
                break

            next_offset = units[unit_index].start_offset + step_size
            next_index = unit_index + 1
            while next_index < len(units) and units[next_index].end_offset <= next_offset:
                next_index += 1
            unit_index = max(unit_index + 1, next_index)

        return windows

    def _assemble_chunks(
        self,
        source_text: str,
        units: list[SemanticUnit],
        boundaries: set[int],
    ) -> list[tuple[int, int, str]]:
        chunks: list[tuple[int, int, str]] = []
        current_units: list[SemanticUnit] = []

        def flush() -> None:
            if not current_units:
                return
            start = current_units[0].start_offset
            end = current_units[-1].end_offset
            content = source_text[start:end]
            chunks.append((start, end, content))
            current_units.clear()

        for index, unit in enumerate(units):
            if index in boundaries:
                flush()

            if len(unit.content) > self.max_chunk_size:
                flush()
                for start, end, _ in self.long_unit_splitter._split_text(unit.content):
                    absolute_start = unit.start_offset + start
                    absolute_end = unit.start_offset + end
                    chunks.append((absolute_start, absolute_end, source_text[absolute_start:absolute_end]))
                continue

            if current_units:
                current_start = current_units[0].start_offset
                if unit.end_offset - current_start > self.max_chunk_size:
                    flush()
            current_units.append(unit)

        flush()
        return chunks
