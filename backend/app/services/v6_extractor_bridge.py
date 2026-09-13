"""Charge l'extracteur V6 sans le modifier, et en exécute le pipeline."""
from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

logger = logging.getLogger(__name__)

_EXTRACTOR_MODULE: ModuleType | None = None
EXTRACTOR_FILENAME = "financial_pdf_extractor-V6_corrected.py"

_TESSERACT_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path.home() / r"AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    Path.home() / r"scoop\apps\tesseract\current\tesseract.exe",
)


def resolve_tesseract_cmd(explicit: str | None = None) -> str:
    """Tesseract est requis pour les liasses scannées (V6). PATH Windows souvent incomplet."""
    from app.core.config import settings

    names: list[str] = []
    for value in (explicit, os.getenv("TESSERACT_CMD"), settings.tesseract_cmd, "tesseract", "tesseract.exe"):
        if value and value not in names:
            names.append(value)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
        path = Path(name)
        if path.is_file():
            return str(path.resolve())
    for path in _TESSERACT_CANDIDATES:
        if path.is_file():
            return str(path)
    raise RuntimeError(
        "Tesseract introuvable. Installez Tesseract-OCR (fra+eng) "
        "ou définissez TESSERACT_CMD vers tesseract.exe."
    )


def extractor_path() -> Path:
    env = os.getenv("WFB_V6_EXTRACTOR", "").strip()
    here = Path(__file__).resolve()
    candidates = []
    if env:
        candidates.append(Path(env))
    # Local : WFB/financial_pdf_extractor-V6_corrected.py
    # Docker : /app/financial_pdf_extractor-V6_corrected.py (WORKDIR /app)
    candidates.extend(
        [
            here.parents[3] / EXTRACTOR_FILENAME,
            here.parents[2] / EXTRACTOR_FILENAME,
            Path("/app") / EXTRACTOR_FILENAME,
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"Extracteur V6 introuvable ({EXTRACTOR_FILENAME}). "
        "Définissez WFB_V6_EXTRACTOR ou placez le fichier à la racine WFB."
    )


def load_extractor() -> ModuleType:
    global _EXTRACTOR_MODULE
    if _EXTRACTOR_MODULE is not None:
        return _EXTRACTOR_MODULE
    path = extractor_path()
    if not path.is_file():
        raise FileNotFoundError(f"Extracteur V6 introuvable : {path}")
    spec = importlib.util.spec_from_file_location("financial_pdf_extractor_v6", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _EXTRACTOR_MODULE = module
    return module


def run_v6_extractor(
    pdf_path: Path,
    *,
    pages: list[int] | None = None,
    ollama_url: str | None = None,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Exécute FinancialPDFExtractor.extract tel quel (jobs=1 dans l'API)."""
    module = load_extractor()
    tesseract_cmd = resolve_tesseract_cmd()
    tessdata_candidates = [
        Path(os.getenv("TESSDATA_PREFIX", "")),
        Path(tesseract_cmd).resolve().parent / "tessdata",
        Path("/usr/share/tesseract-ocr/5/tessdata"),
        Path("/usr/share/tesseract-ocr/4.00/tessdata"),
        Path("/usr/share/tesseract-ocr/tessdata"),
    ]
    for tessdata in tessdata_candidates:
        if tessdata and tessdata.is_dir():
            os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))
            break
    config_kwargs: dict[str, Any] = {"ocr": "auto", "tesseract_cmd": tesseract_cmd}
    if ollama_url:
        config_kwargs["ollama_url"] = ollama_url
    config = module.Config(**config_kwargs)
    logger.info("Extracteur V6 — Tesseract %s", tesseract_cmd)
    root = Path(output_root) if output_root else Path(tempfile.mkdtemp(prefix="wfb-v6-"))
    extractor = module.FinancialPDFExtractor(output_root=root, config=config, jobs=1)
    logger.info("Extracteur V6 — %s (pages=%s)", pdf_path.name, pages or "toutes")
    return extractor.extract(Path(pdf_path), pages=pages)


def run_v6_from_bytes(
    pdf_bytes: bytes,
    filename: str,
    *,
    max_pages: int | None = None,
    ollama_url: str | None = None,
    progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    import fitz

    def publish(event: str, data: dict[str, Any]) -> None:
        if progress is not None:
            progress(event, data)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        tmp.write(pdf_bytes)
        tmp.close()
        pdf_path = Path(tmp.name)
        with fitz.open(pdf_path) as doc:
            page_count = len(doc)
        selected = None
        if max_pages is not None:
            selected = list(range(1, min(max_pages, page_count) + 1))
        publish(
            "pages_rendered",
            {
                "filename": filename,
                "pages_total": len(selected) if selected else page_count,
                "count": len(selected) if selected else page_count,
            },
        )
        publish(
            "page_extracted",
            {
                "page": 1,
                "pages_total": len(selected) if selected else page_count,
                "page_type": "LIASSE",
                "message": "Extraction financière",
            },
        )
        result = run_v6_extractor(
            pdf_path,
            pages=selected,
            ollama_url=ollama_url,
        )
        result["_source_filename"] = filename
        result["_pages_total"] = page_count
        return result
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except OSError:
            logger.warning("PDF temporaire V6 non supprimé : %s", tmp.name)
