from __future__ import annotations

import hashlib
import io
import re
from typing import Protocol

from fastapi import HTTPException
from PIL import Image

from app.core.config import settings


class MalwareScanner(Protocol):
    def scan(self, data: bytes, filename: str) -> str:
        ...


class NoOpMalwareScanner:
    def scan(self, data: bytes, filename: str) -> str:
        return "NOT_CONFIGURED"


_scanner = NoOpMalwareScanner()


def sanitize_filename(name: str) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1]
    return re.sub(r"[^\w.\- ()àâçéèêëïîôùûüÿñÀÂÇÉÈÊËÏÎÔÙÛÜŸÑ]+", "_", base)[:180] or "file"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_upload(filename: str, data: bytes, content_type: str | None = None) -> str:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if not data:
        raise HTTPException(status_code=400, detail=f"Fichier vide : {filename}")
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail=f"Fichier trop volumineux (max {settings.max_upload_size_mb} Mo)")
    name = (filename or "").lower()
    kind = None
    if data.startswith(b"%PDF") or name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=400, detail="Extension PDF mais signature fichier invalide")
        try:
            import fitz

            fitz.open(stream=data, filetype="pdf").close()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF illisible : {exc}") from exc
        kind = "pdf"
    elif data.startswith(b"\x89PNG\r\n\x1a\n") or name.endswith(".png"):
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(status_code=400, detail="PNG invalide")
        Image.open(io.BytesIO(data)).verify()
        kind = "png"
    elif (len(data) >= 3 and data[:3] == b"\xff\xd8\xff") or name.endswith((".jpg", ".jpeg")):
        if not (len(data) >= 3 and data[:3] == b"\xff\xd8\xff"):
            raise HTTPException(status_code=400, detail="JPEG invalide")
        Image.open(io.BytesIO(data)).verify()
        kind = "jpeg"
    else:
        raise HTTPException(status_code=400, detail="Seuls PDF, PNG et JPEG sont acceptés")
    _scanner.scan(data, filename)
    return kind
