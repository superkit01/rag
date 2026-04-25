from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse

from app.schemas.documents import SourceImportRequest
from app.services.text_utils import normalize_whitespace, strip_html


@dataclass(slots=True)
class ParsedSection:
    title: str
    heading_path: list[str]
    content: str
    page_number: int | None = None


@dataclass(slots=True)
class ParsedDocument:
    title: str
    source_type: str
    source_uri: str
    raw_content: str
    sections: list[ParsedSection]


class CompositeDocumentParser:
    def __init__(self, object_storage_local_root: str | None = None) -> None:
        self.object_storage_local_root = (
            Path(object_storage_local_root).expanduser()
            if object_storage_local_root
            else None
        )

    def parse(self, request: SourceImportRequest) -> ParsedDocument:
        source_type = self._infer_source_type(request)
        if request.inline_content is not None:
            raw_content = request.inline_content
        elif request.uploaded_file_base64 is not None:
            raw_content = self._load_uploaded_content(request, source_type)
        else:
            raw_content = self._load_content(request, source_type)
        sections = self._parse_sections(source_type, raw_content)
        return ParsedDocument(
            title=request.title,
            source_type=source_type,
            source_uri=self._build_source_uri(request),
            raw_content=raw_content,
            sections=sections or [ParsedSection(title=request.title, heading_path=[request.title], content=normalize_whitespace(raw_content))],
        )

    def parse_existing(self, title: str, source_uri: str, source_type: str, raw_content: str) -> ParsedDocument:
        sections = self._parse_sections(source_type, raw_content)
        return ParsedDocument(
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            raw_content=raw_content,
            sections=sections,
        )

    def _infer_source_type(self, request: SourceImportRequest) -> str:
        if request.source_type:
            return request.source_type.lower()
        candidate = request.source_path or request.storage_uri or request.uploaded_file_name or request.title
        suffix = Path(candidate).suffix.lower()
        return {
            ".md": "markdown",
            ".markdown": "markdown",
            ".html": "html",
            ".htm": "html",
            ".txt": "text",
            ".pdf": "pdf",
            ".docx": "docx",
            ".pptx": "pptx",
        }.get(suffix, "markdown")

    def _build_source_uri(self, request: SourceImportRequest) -> str:
        if request.source_path:
            return request.source_path
        if request.storage_uri:
            return request.storage_uri
        if request.uploaded_file_name:
            return f"upload://{request.uploaded_file_name}"
        return f"inline://{request.title}"

    def _load_uploaded_content(self, request: SourceImportRequest, source_type: str) -> str:
        content_bytes = self._decode_uploaded_bytes(request.uploaded_file_base64 or "")
        if source_type in {"markdown", "html", "text"}:
            try:
                return content_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Uploaded text documents must be UTF-8 encoded.") from exc

        filename = Path(request.uploaded_file_name or request.title).name
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / filename
            temp_path.write_bytes(content_bytes)
            return self._parse_via_docling(temp_path)

    def _decode_uploaded_bytes(self, payload: str) -> bytes:
        try:
            return base64.b64decode(payload, validate=True)
        except ValueError as exc:
            raise ValueError("Uploaded file payload is not valid base64.") from exc

    def _load_content(self, request: SourceImportRequest, source_type: str) -> str:
        resolved_path = self._resolve_source_path(request)
        if resolved_path is None:
            raise ValueError("Missing source content.")
        if resolved_path.exists():
            if source_type in {"markdown", "html", "text"}:
                return resolved_path.read_text(encoding="utf-8")
            return self._parse_via_docling(resolved_path)
        source_uri = request.source_path or request.storage_uri or str(resolved_path)
        raise ValueError(f"Source path or storage URI is not readable in the current runtime: {source_uri}")

    def _resolve_source_path(self, request: SourceImportRequest) -> Path | None:
        if request.source_path:
            return Path(request.source_path).expanduser()

        if not request.storage_uri:
            return None

        parsed = urlparse(request.storage_uri)
        if parsed.scheme == "":
            return Path(request.storage_uri).expanduser()
        if parsed.scheme == "file":
            file_path = f"{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path
            return Path(unquote(file_path)).expanduser()
        if parsed.scheme in {"s3", "minio"}:
            if not self.object_storage_local_root:
                raise ValueError("Storage URI resolution requires OBJECT_STORAGE_LOCAL_ROOT to be configured.")
            key = parsed.path.lstrip("/")
            if not parsed.netloc or not key:
                raise ValueError(f"Storage URI must include bucket and key: {request.storage_uri}")
            return self.object_storage_local_root / parsed.netloc / key
        raise ValueError(
            "Unsupported storage URI scheme. Use file://, s3://, minio://, or a readable local path."
        )

    def _parse_sections(self, source_type: str, raw_content: str) -> list[ParsedSection]:
        if source_type == "html":
            return [ParsedSection(title="HTML Content", heading_path=["HTML Content"], content=strip_html(raw_content))]
        if source_type == "text":
            return [ParsedSection(title="Text Content", heading_path=["Text Content"], content=normalize_whitespace(raw_content))]
        if source_type in {"pdf", "docx", "pptx"}:
            markdown = raw_content
            return self._parse_markdown(markdown)
        return self._parse_markdown(raw_content)

    def _parse_markdown(self, raw_content: str) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        heading_stack: list[str] = []
        current_title = "Overview"
        current_lines: list[str] = []

        def flush() -> None:
            content = normalize_whitespace("\n".join(current_lines))
            if content:
                sections.append(
                    ParsedSection(
                        title=current_title,
                        heading_path=heading_stack[:] if heading_stack else [current_title],
                        content=content,
                    )
                )

        for line in raw_content.splitlines():
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
            if heading_match:
                flush()
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
                current_title = title
                current_lines = []
                continue
            current_lines.append(line)

        flush()
        if not sections:
            sections.append(ParsedSection(title="Overview", heading_path=["Overview"], content=normalize_whitespace(raw_content)))
        return sections

    def _parse_via_docling(self, source_path: Path) -> str:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise ValueError(
                "Binary document parsing requires the optional 'docling' dependency. "
                "Install it with 'pip install -e .[docling]'."
            ) from exc

        converter = DocumentConverter()
        result = converter.convert(source_path)
        if hasattr(result.document, "export_to_markdown"):
            return result.document.export_to_markdown()
        raise ValueError(f"Docling could not export markdown for {source_path}")
