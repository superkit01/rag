from __future__ import annotations

from app.services.chunking_strategies.base import ChunkingStrategy, PreparedChunk
from app.services.chunking_strategies.fixed_size import FixedSizeStrategy
from app.services.parser import ParsedSection
from app.services.text_utils import estimate_token_count, normalize_whitespace


class ParentChildStrategy(ChunkingStrategy):
    def __init__(
        self,
        parent_chunk_size: int = 900,
        parent_chunk_overlap: int = 150,
        child_chunk_size: int = 250,
        child_chunk_overlap: int = 50,
    ) -> None:
        self.parent_splitter = FixedSizeStrategy(parent_chunk_size, parent_chunk_overlap)
        self.child_splitter = FixedSizeStrategy(child_chunk_size, child_chunk_overlap)

    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        prepared: list[PreparedChunk] = []
        parent_counter = 1
        child_counter = 1

        for section in sections:
            text = normalize_whitespace(section.content)
            if not text:
                continue

            for parent_start, parent_end, parent_content in self.parent_splitter._split_text(text):
                parent_id = f"parent-{parent_counter:04d}"
                prepared.append(
                    PreparedChunk(
                        fragment_id=parent_id,
                        section_title=section.title,
                        heading_path=section.heading_path,
                        page_number=section.page_number,
                        start_offset=parent_start,
                        end_offset=parent_end,
                        token_count=estimate_token_count(parent_content),
                        content=parent_content,
                        chunk_type="parent",
                        parent_id=None,
                    )
                )
                parent_counter += 1

                for child_start, child_end, child_content in self.child_splitter._split_text(parent_content):
                    prepared.append(
                        PreparedChunk(
                            fragment_id=f"child-{child_counter:04d}",
                            section_title=section.title,
                            heading_path=section.heading_path,
                            page_number=section.page_number,
                            start_offset=parent_start + child_start,
                            end_offset=parent_start + child_end,
                            token_count=estimate_token_count(child_content),
                            content=child_content,
                            chunk_type="child",
                            parent_id=parent_id,
                        )
                    )
                    child_counter += 1

        return prepared
