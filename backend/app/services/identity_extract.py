"""Extraction d'identité depuis le bilan (V6), sans lancer tout le pipeline tables."""
from __future__ import annotations

import io
import os
import re
from typing import Any

from app.services.v6_result_mapper import identity_from_v6

_RC_PATTERNS = (
    r"(?:N[°ºo]?\s*)?(?:R\.?\s*C\.?|Registre\s+(?:de|du)\s+commerce)\s*[:\-]?\s*([0-9]{2,8}(?:\s*/\s*[A-Za-zÀ-ÿ\-]+)?)",
    r"\bRC\s*[:\-]\s*([0-9]{2,8}(?:\s*/\s*[A-Za-zÀ-ÿ\-]+)?)",
    r"\bR\.?\s*C\.?\s+(?:n[°ºo]?\s*)?([0-9]{3,8}(?:\s*/\s*[A-Za-zÀ-ÿ\-]+)?)",
)


def _merge_identity(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key, value in incoming.items():
        if key == "evidence" or value in (None, ""):
            continue
        if base.get(key) in (None, ""):
            base[key] = value
    return base


def _extract_rc(text: str) -> str | None:
    src = text.replace("\u00a0", " ")
    for pattern in _RC_PATTERNS:
        match = re.search(pattern, src, re.I)
        if match:
            value = re.sub(r"\s+", "", match.group(1).strip())
            if value and not re.fullmatch(r"\d{15}", value):
                return value
    return None


def _identity_incomplete(data: dict[str, Any]) -> bool:
    return not data.get("ice") or not data.get("raison_sociale")


def extract_identity_from_pdf_bytes(pdf_bytes: bytes, *, max_pages: int = 5) -> dict[str, Any]:
    """Lit l'en-tête du bilan (pages d'identification) via le parseur V6."""
    import fitz

    from app.services.v6_extractor_bridge import load_extractor

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Le fichier n'est pas un PDF.")
    module = load_extractor()
    merged: dict[str, Any] = {}
    rc = None
    with fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as doc:
        limit = min(len(doc), max(1, max_pages))
        for index in range(limit):
            text = doc[index].get_text("text") or ""
            secondary = module.clean_identity(text)
            merged = _merge_identity(merged, secondary)
            rc = rc or _extract_rc(text)
    if _identity_incomplete(merged):
        merged, rc = _ocr_identity_with_tesseract(pdf_bytes, module, merged, rc, max_pages=min(2, max_pages))
    identity = identity_from_v6(merged)
    payload = identity.model_dump()
    payload["rc"] = rc
    return payload


def _ocr_identity_with_tesseract(
    pdf_bytes: bytes,
    module: Any,
    merged: dict[str, Any],
    rc: str | None,
    *,
    max_pages: int,
) -> tuple[dict[str, Any], str | None]:
    """OCR Tesseract des pages d'en-tête (liasses scannées), sans pipeline tables V6."""
    import fitz
    import numpy as np

    from app.services.v6_extractor_bridge import resolve_ocr_language, resolve_tesseract_cmd, resolve_tessdata_dir

    cmd = resolve_tesseract_cmd()
    tessdata = resolve_tessdata_dir(cmd)
    if tessdata is not None:
        os.environ["TESSDATA_PREFIX"] = str(tessdata)
    config = module.Config(
        tesseract_cmd=cmd,
        dpi=220,
        ocr="force",
        ocr_language=resolve_ocr_language(cmd, tessdata),
    )
    module.tesseract_info(config)
    with fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf") as doc:
        limit = min(len(doc), max(1, max_pages))
        for index in range(limit):
            pix = doc[index].get_pixmap(dpi=config.dpi, colorspace=fitz.csGRAY, alpha=False)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
            words = module.tesseract(image, config, psm=11)
            text = module.words_text(words)
            merged = _merge_identity(merged, module.clean_identity(text))
            rc = rc or _extract_rc(text)
            if not _identity_incomplete(merged) and rc:
                break
    return merged, rc
