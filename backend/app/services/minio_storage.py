from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def _use_local() -> bool:
    return settings.storage_backend != "minio"


def _files_root() -> Path:
    root = settings.files_dir
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _local_path(object_key: str) -> Path:
    root = _files_root()
    path = (root / object_key).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Clé de fichier invalide") from exc
    return path


def get_minio():
    global _client
    if _use_local():
        raise RuntimeError("Stockage local actif — MinIO n'est pas utilisé.")
    if _client is None:
        from minio import Minio

        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_bucket() -> None:
    if _use_local():
        _files_root()
        logger.info("Stockage local prêt (%s)", _files_root())
        return
    from minio.error import S3Error

    client = get_minio()
    bucket = settings.minio_bucket
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Bucket MinIO créé : %s", bucket)
    except S3Error as exc:
        logger.warning("Impossible de vérifier/créer le bucket MinIO : %s", exc)


def _safe_name(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE).strip("._")
    return cleaned or "file"


def upload_file(
    *,
    dossier_id: str,
    category: str,
    filename: str,
    data: BinaryIO,
    length: int,
    content_type: str | None,
) -> str:
    safe = _safe_name(filename)
    object_key = f"dossiers/{dossier_id}/{category}/{uuid4().hex}_{safe}"
    if _use_local():
        path = _local_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = data.read() if hasattr(data, "read") else data
        path.write_bytes(payload)
        return object_key

    ensure_bucket()
    get_minio().put_object(
        settings.minio_bucket,
        object_key,
        data,
        length=length,
        content_type=content_type or "application/octet-stream",
    )
    return object_key


def download_bytes(object_key: str) -> bytes:
    if _use_local():
        path = _local_path(object_key)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {object_key}")
        return path.read_bytes()

    response = get_minio().get_object(settings.minio_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def object_url(object_key: str) -> str:
    if _use_local():
        return f"/files/{quote(object_key)}"
    scheme = "https" if settings.minio_secure else "http"
    return (
        f"{scheme}://{settings.minio_public_endpoint}/"
        f"{settings.minio_bucket}/{quote(object_key)}"
    )
