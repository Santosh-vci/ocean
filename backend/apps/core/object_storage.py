from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    size_bytes: int
    checksum_sha256: str


def _bucket_name(bucket: str | None = None) -> str:
    return (
        bucket
        or os.getenv("S3_BUCKET_NAME")
        or os.getenv("AWS_STORAGE_BUCKET_NAME")
        or "coalflow-local"
    )


def _storage_root() -> Path:
    root = os.getenv("EXPORT_STORAGE_ROOT")
    if root:
        return Path(root)
    return Path(tempfile.gettempdir()) / "coalflow_exports"


def _object_path(key: str, bucket: str | None = None) -> Path:
    normalized_key = key.strip("/").replace("\\", "/")
    return _storage_root() / _bucket_name(bucket) / normalized_key


def put_export_object(
    *,
    key: str,
    content: bytes,
    bucket: str | None = None,
) -> StoredObject:
    """
    Phase-1 object-storage seam.

    Docker already provisions an S3-compatible MinIO bucket. This adapter preserves the
    same bucket/key/checksum contract while keeping local/test execution dependency-free.
    A future S3 adapter can swap in behind this module without changing export records
    or API contracts.
    """

    path = _object_path(key, bucket)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return StoredObject(
        bucket=_bucket_name(bucket),
        key=key.strip("/").replace("\\", "/"),
        size_bytes=len(content),
        checksum_sha256=checksum,
    )


def read_export_object(*, key: str, bucket: str | None = None) -> bytes:
    return _object_path(key, bucket).read_bytes()


def export_storage_health() -> dict:
    root = _storage_root()
    bucket_root = root / _bucket_name()
    bucket_root.mkdir(parents=True, exist_ok=True)
    return {
        "root": str(root),
        "bucket": _bucket_name(),
        "writable": os.access(bucket_root, os.W_OK),
    }
