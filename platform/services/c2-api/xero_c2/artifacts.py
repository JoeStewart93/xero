from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from xero_c2.models import Artifact

ARTIFACT_BACKEND_FILESYSTEM = "filesystem"
ARTIFACT_BACKEND_S3 = "s3"


class ArtifactStorageError(RuntimeError):
    pass


class ArtifactNotFound(ArtifactStorageError):
    pass


class ArtifactStore(Protocol):
    backend: str

    def ensure_ready(self) -> None:
        ...

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        ...

    def get(self, key: str) -> bytes:
        ...

    def head(self, key: str) -> bool:
        ...

    def delete(self, key: str) -> None:
        ...


def normalize_object_key(*parts: str | None) -> str:
    cleaned: list[str] = []
    for part in parts:
        if not part:
            continue
        for segment in str(part).replace("\\", "/").split("/"):
            normalized = segment.strip()
            if normalized in {"", ".", ".."}:
                continue
            cleaned.append(normalized)
    return "/".join(cleaned)


def safe_filesystem_path(root: Path, key: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / normalize_object_key(key)).resolve()
    if resolved_root != path and resolved_root not in path.parents:
        raise ArtifactStorageError("Artifact object key escapes filesystem root")
    return path


class FilesystemArtifactStore:
    backend = ARTIFACT_BACKEND_FILESYSTEM

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        if not self.root.is_absolute():
            self.root = Path.cwd() / self.root

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        del content_type
        self.ensure_ready()
        path = safe_filesystem_path(self.root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, key: str) -> bytes:
        path = safe_filesystem_path(self.root, key)
        if not path.is_file():
            raise ArtifactNotFound("Artifact object not found")
        return path.read_bytes()

    def head(self, key: str) -> bool:
        return safe_filesystem_path(self.root, key).is_file()

    def delete(self, key: str) -> None:
        safe_filesystem_path(self.root, key).unlink(missing_ok=True)


class S3ArtifactStore:
    backend = ARTIFACT_BACKEND_S3

    def __init__(self, settings) -> None:
        self.bucket = settings.artifact_s3_bucket
        self.region = settings.artifact_s3_region
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.artifact_s3_endpoint_url,
            aws_access_key_id=settings.artifact_s3_access_key,
            aws_secret_access_key=settings.artifact_s3_secret_key,
            region_name=settings.artifact_s3_region,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_ready(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code not in {"404", "NoSuchBucket", "NotFound"} and status_code != 404:
                raise ArtifactStorageError(str(exc)) from exc
            params: dict[str, object] = {"Bucket": self.bucket}
            if self.region != "us-east-1":
                params["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            self.client.create_bucket(**params)

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        self.ensure_ready()
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if _is_missing_s3_error(exc):
                raise ArtifactNotFound("Artifact object not found") from exc
            raise ArtifactStorageError(str(exc)) from exc
        return response["Body"].read()

    def head(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if _is_missing_s3_error(exc):
                return False
            raise ArtifactStorageError(str(exc)) from exc

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def _is_missing_s3_error(exc: ClientError) -> bool:
    code = str(exc.response.get("Error", {}).get("Code", ""))
    status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status_code == 404


def artifact_store_for_settings(settings) -> ArtifactStore:
    backend = settings.artifact_storage_backend.lower()
    if backend == ARTIFACT_BACKEND_FILESYSTEM:
        return FilesystemArtifactStore(settings.artifact_filesystem_dir)
    if backend == ARTIFACT_BACKEND_S3:
        return S3ArtifactStore(settings)
    raise ArtifactStorageError(f"Unsupported artifact storage backend: {settings.artifact_storage_backend}")


def artifact_object_key(settings, namespace: str, owner_id, filename: str) -> str:
    return normalize_object_key(settings.artifact_s3_prefix, namespace, str(owner_id), filename)


def put_artifact(
    session: Session,
    settings,
    *,
    namespace: str,
    owner_type: str,
    owner_id,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> Artifact:
    digest = hashlib.sha256(content).hexdigest()
    key = artifact_object_key(settings, namespace, owner_id, filename)
    store = artifact_store_for_settings(settings)
    store.put(key, content, content_type=content_type)
    artifact = Artifact(
        namespace=namespace,
        owner_type=owner_type,
        owner_id=owner_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        sha256=digest,
        storage_backend=store.backend,
        bucket=getattr(settings, "artifact_s3_bucket", None) if store.backend == ARTIFACT_BACKEND_S3 else None,
        object_key=key,
    )
    session.add(artifact)
    session.flush()
    return artifact


def artifact_is_available(settings, artifact: Artifact | None) -> bool:
    if artifact is None:
        return False
    return artifact_store_for_settings(settings).head(artifact.object_key)


def read_artifact(settings, artifact: Artifact) -> bytes:
    return artifact_store_for_settings(settings).get(artifact.object_key)
