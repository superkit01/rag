from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
import uuid

from minio import Minio

from app.core.config import Settings


class ObjectStorage(Protocol):
    def store_uploaded_file(self, *, filename: str, payload: bytes, knowledge_space_id: str | None) -> str:
        ...


@dataclass(slots=True)
class LocalObjectStorage:
    local_root: Path
    bucket: str

    def store_uploaded_file(self, *, filename: str, payload: bytes, knowledge_space_id: str | None) -> str:
        object_key = build_object_key(filename=filename, knowledge_space_id=knowledge_space_id)
        target = self.local_root / self.bucket / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return f"s3://{self.bucket}/{object_key}"


class MinioObjectStorage:
    def __init__(self, settings: Settings) -> None:
        parsed = urlparse(settings.object_storage_endpoint)
        secure = parsed.scheme == "https"
        endpoint = parsed.netloc or parsed.path
        self.bucket = settings.object_storage_bucket
        self.client = Minio(
            endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            secure=secure,
        )

    def store_uploaded_file(self, *, filename: str, payload: bytes, knowledge_space_id: str | None) -> str:
        object_key = build_object_key(filename=filename, knowledge_space_id=knowledge_space_id)
        self._ensure_bucket()
        self.client.put_object(
            self.bucket,
            object_key,
            data=BytesIO(payload),
            length=len(payload),
            content_type=guess_content_type(filename),
        )
        return f"s3://{self.bucket}/{object_key}"

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)


def build_object_storage(settings: Settings) -> LocalObjectStorage | MinioObjectStorage:
    if settings.object_storage_backend == "minio":
        return MinioObjectStorage(settings)
    return LocalObjectStorage(Path(settings.object_storage_local_root).expanduser(), settings.object_storage_bucket)


def build_object_key(*, filename: str, knowledge_space_id: str | None) -> str:
    now = datetime.now(UTC)
    safe_name = Path(filename).name or "upload.bin"
    namespace = knowledge_space_id or "unassigned"
    return "/".join(
        [
            "uploads",
            namespace,
            now.strftime("%Y"),
            now.strftime("%m"),
            f"{uuid.uuid4()}-{safe_name}",
        ]
    )


def guess_content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix, "application/octet-stream")
