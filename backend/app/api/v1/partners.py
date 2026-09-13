"""API partenaire PVC — envoi d'un dossier + liasse, consultation par noDemande."""
from __future__ import annotations

import hmac
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile

from app.api.v1.analyse import start_analyse_job
from app.core.config import settings
from app.schemas.pvc import PartnerAnalyseResponse, PartnerIngestResponse
from app.services import dossier_store
from app.services.pvc_partner import (
    build_partner_analyse,
    ingest_pvc_dossier,
    partner_poll_path,
)

router = APIRouter(prefix="/partners/pvc", tags=["partenaire PVC"])


def require_pvc_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str:
    expected = (settings.pvc_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="PVC_API_KEY n'est pas configurée sur le serveur WFB.",
        )
    provided = (x_api_key or "").strip()
    if not provided and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            provided = value.strip()
    provided_b = provided.encode("utf-8")
    expected_b = expected.encode("utf-8")
    if len(provided_b) != len(expected_b) or not hmac.compare_digest(provided_b, expected_b):
        raise HTTPException(
            status_code=401,
            detail="Clé API invalide. Envoyez l'en-tête X-API-Key.",
        )
    return provided


@router.post("/dossiers", response_model=PartnerIngestResponse, status_code=202)
async def ingest_pvc(
    background_tasks: BackgroundTasks,
    data: str = Form(..., description="JSON DossierPv (mêmes colonnes PVC)"),
    liasse: UploadFile = File(..., description="PDF de la liasse fiscale"),
    liasses: list[UploadFile] = File(default=[], description="PDF supplémentaires (N-1 / N-2)"),
    max_pages: Optional[int] = None,
    _: str = Depends(require_pvc_api_key),
) -> PartnerIngestResponse:
    record = await ingest_pvc_dossier(data, liasse, liasses)
    try:
        job = await start_analyse_job(record.id, background_tasks, max_pages=max_pages)
    except HTTPException as exc:
        poll = partner_poll_path(record.noDemande or record.id)
        return PartnerIngestResponse(
            noDemande=record.noDemande or record.id,
            noPv=record.noPv,
            id=record.pvcId,
            wfb_id=record.id,
            nomClient=record.name,
            status=record.status,
            message=str(exc.detail),
            poll_url=poll,
            analyse_url=poll,
        )
    poll = partner_poll_path(record.noDemande or record.id)
    return PartnerIngestResponse(
        noDemande=record.noDemande or record.id,
        noPv=record.noPv,
        id=record.pvcId,
        wfb_id=record.id,
        nomClient=record.name,
        status="analyzing",
        message=(
            f"Dossier {record.noDemande} enregistré — analyse lancée "
            f"(job {job.job_id}). Interrogez poll_url jusqu'à analyseStatus=completed."
        ),
        job_id=job.job_id,
        stream_url=job.stream_url,
        result_url=job.result_url,
        poll_url=poll,
        analyse_url=poll,
        filename=job.filename,
    )


@router.get("/dossiers/{noDemande}", response_model=PartnerAnalyseResponse)
def get_pvc_analyse(
    noDemande: str,
    _: str = Depends(require_pvc_api_key),
) -> PartnerAnalyseResponse:
    record = dossier_store.get_by_no_demande(noDemande)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Aucun dossier PVC pour noDemande={noDemande}")
    return build_partner_analyse(record)
