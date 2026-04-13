from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError

try:
    import boto3
    from botocore.config import Config as BotoConfig
except Exception:  # pragma: no cover - optional dependency for local-first setups
    boto3 = None
    BotoConfig = None


@dataclass(slots=True)
class StorageObject:
    key: str
    content: bytes
    content_type: str | None
    size_bytes: int


class StorageBackend:
    backend_name: str = "unknown"

    async def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        raise NotImplementedError

    async def get_bytes(self, *, key: str) -> StorageObject | None:
        raise NotImplementedError

    async def delete(self, *, key: str) -> None:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    backend_name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        normalized_key = str(key or "").strip().replace("\\", "/")
        if not normalized_key:
            raise ValidationError("storage key is required")

        safe_key = PurePosixPath("/" + normalized_key).relative_to("/")
        resolved = (self._root / safe_key.as_posix()).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise ValidationError("storage key is invalid")
        return resolved

    async def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        del metadata
        target = self._resolve_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StorageObject(
            key=key,
            content=content,
            content_type=content_type,
            size_bytes=len(content),
        )

    async def get_bytes(self, *, key: str) -> StorageObject | None:
        target = self._resolve_path(key)
        if not target.exists() or not target.is_file():
            return None
        content = target.read_bytes()
        return StorageObject(
            key=key,
            content=content,
            content_type=None,
            size_bytes=len(content),
        )

    async def delete(self, *, key: str) -> None:
        target = self._resolve_path(key)
        if target.exists() and target.is_file():
            target.unlink()


class S3StorageBackend(StorageBackend):
    backend_name = "s3"

    def __init__(self, settings: Settings) -> None:
        if boto3 is None or BotoConfig is None:
            raise ValidationError("S3 storage backend is configured, but boto3 is not installed")

        bucket = str(settings.storage_s3_bucket or "").strip()
        if not bucket:
            raise ValidationError("storage_s3_bucket is required for S3 backend")

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=(str(settings.storage_s3_endpoint_url).strip() or None),
            region_name=settings.storage_s3_region,
            aws_access_key_id=(str(settings.storage_s3_access_key_id).strip() or None),
            aws_secret_access_key=(str(settings.storage_s3_secret_access_key).strip() or None),
            config=BotoConfig(
                s3={"addressing_style": "path" if settings.storage_s3_force_path_style else "auto"},
            ),
        )

    async def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise ValidationError("storage key is required")

        extra_args: dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=normalized_key,
            Body=content,
            **extra_args,
        )
        return StorageObject(
            key=normalized_key,
            content=content,
            content_type=content_type,
            size_bytes=len(content),
        )

    async def get_bytes(self, *, key: str) -> StorageObject | None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return None

        def _load() -> StorageObject | None:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=normalized_key)
            except Exception as exc:
                error_code = (
                    getattr(getattr(exc, "response", {}), "get", lambda *_: None)("Error", {})
                    .get("Code", "")
                    .strip()
                )
                if error_code in {"NoSuchKey", "404", "NotFound"}:
                    return None
                raise

            body = response.get("Body")
            if body is None:
                return None
            content = body.read()
            content_type = str(response.get("ContentType") or "").strip() or None
            return StorageObject(
                key=normalized_key,
                content=content,
                content_type=content_type,
                size_bytes=len(content),
            )

        return await asyncio.to_thread(_load)

    async def delete(self, *, key: str) -> None:
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=normalized_key)


class StorageService:
    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    async def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        return await self._backend.put_bytes(
            key=key,
            content=content,
            content_type=content_type,
            metadata=metadata,
        )

    async def get_bytes(self, *, key: str) -> StorageObject | None:
        return await self._backend.get_bytes(key=key)

    async def delete(self, *, key: str) -> None:
        await self._backend.delete(key=key)


def _can_use_s3(settings: Settings) -> bool:
    return bool(str(settings.storage_s3_bucket or "").strip())


def build_storage_service(settings: Settings) -> StorageService:
    backend = settings.storage_backend
    if backend == "s3":
        return StorageService(S3StorageBackend(settings))
    if backend == "local":
        return StorageService(LocalStorageBackend(settings.storage_local_root))
    if _can_use_s3(settings):
        return StorageService(S3StorageBackend(settings))
    return StorageService(LocalStorageBackend(settings.storage_local_root))


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    return build_storage_service(get_settings())


__all__ = [
    "StorageObject",
    "StorageService",
    "build_storage_service",
    "get_storage_service",
]
