from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile

from app.api.v1.analyse import start_analyse_job
from app.schemas.create_dossier import CreateDossierResponse, StoredDossierRecord
from app.schemas.dossier import Dossier, DossierListResponse
from app.services import dossier_service

router = APIRouter()


@router.get("/dossiers", response_model=DossierListResponse)
def list_dossiers(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> DossierListResponse:
    return dossier_service.list_dossiers(status, q)


@router.post("/dossiers", response_model=CreateDossierResponse, status_code=201)
async def create_dossier(
    background_tasks: BackgroundTasks,
    data: str = Form(...),
    documents: list[UploadFile] = File(default=[]),
    proforma: UploadFile | None = File(default=None),
) -> CreateDossierResponse:
    created = await dossier_service.create_dossier(data, documents, proforma)
    try:
        job = await start_analyse_job(created.id, background_tasks)
    except HTTPException:
        return created
    return CreateDossierResponse(
        id=created.id,
        status="analyzing",
        message=(
            f"Dossier {created.id} créé — analyse lancée en file d'attente "
            f"(job {job.job_id}). Les dossiers suivants seront traités à tour de rôle."
        ),
        job_id=job.job_id,
        stream_url=job.stream_url,
        result_url=job.result_url,
        synthese_url=f"/api/v1/dossiers/{created.id}/synthese",
        filename=job.filename,
    )


@router.get("/dossiers/{dossier_id}", response_model=Dossier)
def get_dossier(dossier_id: str) -> Dossier:
    return dossier_service.get_dossier(dossier_id)


@router.get("/dossiers/{dossier_id}/detail", response_model=StoredDossierRecord)
def get_dossier_detail(dossier_id: str) -> StoredDossierRecord:
    return dossier_service.get_dossier_detail(dossier_id)


@router.post("/dossiers/{dossier_id}/approve", response_model=Dossier)
def approve_dossier(dossier_id: str) -> Dossier:
    return dossier_service.approve_dossier(dossier_id)


@router.post("/dossiers/{dossier_id}/reject", response_model=Dossier)
def reject_dossier(dossier_id: str) -> Dossier:
    return dossier_service.reject_dossier(dossier_id)


@router.post("/dossiers/{dossier_id}/reserve", response_model=Dossier)
def reserve_dossier(dossier_id: str) -> Dossier:
    return dossier_service.reserve_dossier(dossier_id)


@router.post("/dossiers/{dossier_id}/cancel", response_model=Dossier)
def cancel_dossier_decision(dossier_id: str) -> Dossier:
    return dossier_service.cancel_decision(dossier_id)


@router.post("/dossiers/{dossier_id}/documents/replace", response_model=StoredDossierRecord)
async def replace_dossier_document(
    dossier_id: str,
    name: str = Form(...),
    file: UploadFile = File(...),
) -> StoredDossierRecord:
    return await dossier_service.replace_document(dossier_id, name, file)
