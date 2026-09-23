"""API RCC — pipeline V6 scoring. Routes protégées par Keycloak (voir api/v1/router.py)."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import config
from app.core.security import get_current_user
from app.jobs.factory import get_job_dispatcher
from app.services.analyse_job_store import job_store
from app.services.rcc_compliance import build_compliance
from app.services.rcc_dossier_store import (
    effective_values,
    export_dossier_clean,
    rcc_dossier_store,
)
from app.services.rcc_from_scoring import get_or_import, scoring_list_summaries
from app.services.rcc_projection import export_rcc_clean, project_rcc_result
from app.services.scoring_lab_pipeline import run_scoring_job

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RCC"])
auth_router = APIRouter(prefix="/auth", tags=["RCC session"])
public_router = APIRouter(tags=["RCC"])

_PIPELINE_LOCK = asyncio.Lock()
MAX_UPLOAD = 25 * 1024 * 1024


async def _run_rcc_job(job_id: str) -> None:
    async with _PIPELINE_LOCK:
        await run_scoring_job(job_id, store=job_store, on_completed=None)


async def _read_pdf(file: UploadFile) -> tuple[bytes, str]:
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Seuls les fichiers PDF sont acceptés.")
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 25 Mo).")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Signature PDF invalide.")
    return content, filename


def dossier_payload(dossier) -> dict[str, Any]:
    return {
        "dossier": dossier.detail(),
        "compliance": build_compliance(dossier).model_dump(),
        "effective_values": effective_values(dossier),
    }


@auth_router.get("/me")
def auth_me(user: dict = Depends(get_current_user)) -> dict:
    return user


@router.get("/rcc/system/ocr-health")
def ocr_health() -> dict:
    return {
        "status": "online",
        "label": "Moteur V6 (WFB scoring)",
        "models_count": 1,
        "latency_ms": 0,
        "pipeline": "financial-extractor-v6",
    }


@public_router.get("/rcc/health")
def rcc_health() -> dict:
    return {"status": "ok", "service": "rcc"}


@router.post("/rcc/jobs")
async def create_rcc_job(
    file: UploadFile = File(...),
    max_pages: Optional[int] = Form(None),
) -> dict:
    if max_pages is not None and (max_pages < 1 or max_pages > config.DIRECT_FINANCIAL_MAX_PAGES):
        raise HTTPException(status_code=422, detail="max_pages invalide")
    content, filename = await _read_pdf(file)
    job = job_store.create(
        dossier_id=f"RCC-{filename[:24]}",
        filename=filename,
        max_pages=max_pages,
        pdf_bytes=content,
    )
    rcc_dossier_store.save_pdf(job.job_id, content)
    await get_job_dispatcher(_run_rcc_job).dispatch_analysis(job.job_id)
    return {
        "job_id": job.job_id,
        "status": "queued",
        "stream_url": f"/api/v1/rcc/jobs/{job.job_id}/stream",
        "result_url": f"/api/v1/rcc/jobs/{job.job_id}/result",
        "export_url": f"/api/v1/rcc/jobs/{job.job_id}/export",
        "filename": filename,
    }


@router.get("/rcc/jobs/{job_id}")
def get_rcc_job(job_id: str) -> dict:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    return job_store.to_progress(job).model_dump()


@router.get("/rcc/jobs/{job_id}/stream")
async def stream_rcc_job(job_id: str) -> StreamingResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    queue = job_store.subscribe(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    async def event_generator() -> AsyncIterator[str]:
        try:
            progress = job_store.to_progress(job)
            yield f"event: job_status\ndata: {progress.model_dump_json()}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    current = job_store.get(job_id)
                    if current is None or current.status in {"completed", "failed"}:
                        break
                    continue
                event_type = event.get("event", "message")
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"event: {event_type}\ndata: {payload}\n\n"
                if event_type in {"result_ready", "job_failed"}:
                    break
        finally:
            job_store.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _completed_job(job_id: str):
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    if job.status == "failed":
        raise HTTPException(status_code=422, detail=job.error or "Le job a échoué.")
    if job.status != "completed" or job.result is None:
        raise HTTPException(status_code=409, detail="Le résultat n'est pas encore disponible.")
    return job


@router.get("/rcc/jobs/{job_id}/result")
def get_rcc_result(job_id: str) -> dict:
    job = _completed_job(job_id)
    return project_rcc_result(job.result)


@router.get("/rcc/jobs/{job_id}/export")
def export_rcc_job(job_id: str) -> JSONResponse:
    job = _completed_job(job_id)
    payload = export_rcc_clean(job.result)
    filename = (job.filename or "rcc").rsplit(".", 1)[0]
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="RCC-{filename}.json"'},
    )


class DossierCreateRequest(BaseModel):
    job_id: str
    client_name: Optional[str] = None
    ice: Optional[str] = None
    credit_amount: Optional[float] = None
    exercice_date: Optional[str] = None
    sector: Optional[str] = None


class DossierPatchRequest(BaseModel):
    status: Optional[str] = None
    motif: Optional[str] = None
    comment: Optional[str] = None
    client_name: Optional[str] = None
    sector: Optional[str] = None
    credit_amount: Optional[float] = None
    exercice_date: Optional[str] = None


class FieldOverrideRequest(BaseModel):
    field_code: str
    corrected_value: Optional[float] = None
    verified: bool = False


class FieldOverrideBatchRequest(BaseModel):
    overrides: list[FieldOverrideRequest] = Field(min_length=1)


@router.get("/rcc/dossiers")
def list_dossiers(
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict:
    local, _, _ = rcc_dossier_store.list_dossiers(
        status="all", search=None, limit=1000, offset=0
    )
    merged = {item["id"]: item for item in scoring_list_summaries()}
    merged.update({item["id"]: item for item in local})
    items = list(merged.values())
    counts = {"pending": 0, "validated": 0, "rejected": 0, "escalated": 0, "all": len(items)}
    for item in items:
        if item.get("status") in counts:
            counts[item["status"]] += 1
    if status and status != "all":
        items = [item for item in items if item.get("status") == status]
    if search:
        needle = search.lower()
        items = [
            item
            for item in items
            if needle in (item.get("id") or "").lower()
            or needle in (item.get("client_name") or "").lower()
            or needle in (item.get("ice") or "").lower()
            or needle in (item.get("identifiant_fiscal") or "").lower()
        ]
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    total = len(items)
    return {"items": items[offset : offset + limit], "total": total, "counts": counts}


@router.post("/rcc/dossiers", status_code=201)
def create_dossier(
    payload: DossierCreateRequest, user: dict = Depends(get_current_user)
) -> dict:
    existing = rcc_dossier_store.find_by_job(payload.job_id)
    if existing is not None:
        return dossier_payload(existing)
    job = _completed_job(payload.job_id)
    pdf_bytes = job.pdf_bytes
    if not pdf_bytes:
        stored = settings_pdf(job.job_id)
        if stored:
            pdf_bytes = stored.read_bytes()
    dossier = rcc_dossier_store.create_from_job(
        job_id=payload.job_id,
        scoring_result=job.result,
        filename=job.filename,
        pdf_bytes=pdf_bytes,
        actor=user["display_name"],
        client_name=payload.client_name,
        ice=payload.ice,
        credit_amount=payload.credit_amount,
        exercice_date=payload.exercice_date,
        sector=payload.sector,
    )
    return dossier_payload(dossier)


def settings_pdf(job_id: str) -> Path | None:
    path = rcc_dossier_store._pdf_dir / f"{job_id}.pdf"
    return path if path.exists() else None


def _dossier_or_404(dossier_id: str):
    dossier = get_or_import(dossier_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    return dossier


@router.get("/rcc/dossiers/{dossier_id}")
def get_dossier(dossier_id: str) -> dict:
    return dossier_payload(_dossier_or_404(dossier_id))


@router.patch("/rcc/dossiers/{dossier_id}")
def patch_dossier(
    dossier_id: str, payload: DossierPatchRequest, user: dict = Depends(get_current_user)
) -> dict:
    dossier = rcc_dossier_store.patch(
        dossier_id, payload.model_dump(exclude_unset=True), user["display_name"]
    )
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    return dossier_payload(dossier)


@router.delete("/rcc/dossiers/{dossier_id}")
def delete_dossier(dossier_id: str) -> dict:
    if not rcc_dossier_store.delete(dossier_id):
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    return {"ok": True}


@router.put("/rcc/dossiers/{dossier_id}/overrides")
def save_overrides(
    dossier_id: str,
    payload: FieldOverrideBatchRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    dossier = rcc_dossier_store.save_overrides(
        dossier_id,
        [item.model_dump() for item in payload.overrides],
        user["display_name"],
    )
    if dossier is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable.")
    return dossier_payload(dossier)


@router.post("/rcc/dossiers/{dossier_id}/attach")
def attach_dossier(
    dossier_id: str, payload: DossierCreateRequest, user: dict = Depends(get_current_user)
) -> dict:
    _dossier_or_404(dossier_id)
    job = _completed_job(payload.job_id)
    pdf_bytes = job.pdf_bytes
    stored = settings_pdf(job.job_id)
    if not pdf_bytes and stored:
        pdf_bytes = stored.read_bytes()
    dossier = rcc_dossier_store.create_from_job(
        job_id=payload.job_id,
        scoring_result=job.result,
        filename=job.filename,
        pdf_bytes=pdf_bytes,
        actor=user["display_name"],
    )
    # Keep requested id: if create made a new one, patch isn't needed — attach should update existing.
    existing = rcc_dossier_store.get(dossier_id)
    if existing and existing.id != dossier.id:
        existing.job_id = job.job_id
        existing.result = dossier.result
        existing.scoring_result = dossier.scoring_result
        existing.filename = dossier.filename
        existing.pdf_path = dossier.pdf_path
        existing.completeness_pct = dossier.completeness_pct
        existing.client_name = existing.client_name or dossier.client_name
        existing.ice = existing.ice or dossier.ice
        existing.exercice_date = existing.exercice_date or dossier.exercice_date
        existing.sector = existing.sector or dossier.sector
        rcc_dossier_store.delete(dossier.id)
        return dossier_payload(existing)
    return dossier_payload(dossier)


@router.get("/rcc/dossiers/{dossier_id}/file")
def dossier_file(dossier_id: str):
    dossier = _dossier_or_404(dossier_id)
    if not dossier.pdf_path or not Path(dossier.pdf_path).exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    return FileResponse(dossier.pdf_path, media_type="application/pdf", filename=dossier.filename)


@router.get("/rcc/dossiers/{dossier_id}/audit")
def dossier_audit(dossier_id: str) -> dict:
    _dossier_or_404(dossier_id)
    items = rcc_dossier_store.audit_for(dossier_id)
    return {"items": items, "total": len(items)}


@router.get("/rcc/dossiers/{dossier_id}/export.json")
def export_dossier_json(dossier_id: str) -> JSONResponse:
    dossier = _dossier_or_404(dossier_id)
    payload = export_dossier_clean(dossier)
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="RCC-{dossier.id}.json"'},
    )


@router.get("/rcc/audit")
def all_audit() -> dict:
    items = rcc_dossier_store.audit_all()
    return {"items": items, "total": len(items)}
