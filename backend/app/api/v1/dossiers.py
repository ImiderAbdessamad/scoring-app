from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.v1.analyse import start_analyse_job
from app.db.repositories import analysis_run_repository, memo_repository, risk_repository
from app.schemas.create_dossier import CreateDossierResponse, StoredDossierRecord
from app.schemas.dossier import Dossier, DossierListResponse
from app.services import dossier_service, dossier_store
from app.services.decision_service import DecisionNotEligible, eligibility, history

router = APIRouter()


class DecisionBody(BaseModel):
    reason: str | None = None
    comment: str | None = None


class RiskCheckBody(BaseModel):
    status: str
    rating: int | None = None
    source: str = "MANUAL"
    comment: str | None = None
    checked_by: str | None = None


class MemoCreateBody(BaseModel):
    content: dict[str, Any] = {}
    signed_by: str | None = None
    signed_role: str | None = None


def _decision_http(exc: DecisionNotEligible) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "DECISION_NOT_ELIGIBLE",
            "message": "Le dossier n’est pas éligible à cette décision.",
            "blocking_reasons": exc.result.blocking_reasons,
            "warnings": exc.result.warnings,
        },
    )


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
def approve_dossier(dossier_id: str, body: DecisionBody | None = None) -> Dossier:
    try:
        return dossier_service.approve_dossier(
            dossier_id,
            reason=body.reason if body else None,
            comment=body.comment if body else None,
        )
    except DecisionNotEligible as exc:
        raise _decision_http(exc) from exc


@router.post("/dossiers/{dossier_id}/reject", response_model=Dossier)
def reject_dossier(dossier_id: str, body: DecisionBody | None = None) -> Dossier:
    try:
        return dossier_service.reject_dossier(
            dossier_id,
            reason=body.reason if body else None,
            comment=body.comment if body else None,
        )
    except DecisionNotEligible as exc:
        raise _decision_http(exc) from exc


@router.post("/dossiers/{dossier_id}/reserve", response_model=Dossier)
def reserve_dossier(dossier_id: str, body: DecisionBody | None = None) -> Dossier:
    try:
        return dossier_service.reserve_dossier(
            dossier_id,
            reason=body.reason if body else None,
            comment=body.comment if body else None,
        )
    except DecisionNotEligible as exc:
        raise _decision_http(exc) from exc


@router.post("/dossiers/{dossier_id}/cancel", response_model=Dossier)
def cancel_dossier_decision(dossier_id: str, body: DecisionBody | None = None) -> Dossier:
    return dossier_service.cancel_decision(
        dossier_id,
        reason=body.reason if body else None,
        comment=body.comment if body else None,
    )


@router.get("/dossiers/{dossier_id}/decision-history")
def decision_history(dossier_id: str) -> list[dict]:
    return history(dossier_id)


@router.get("/dossiers/{dossier_id}/decision-eligibility")
def decision_eligibility(dossier_id: str) -> dict:
    return eligibility(dossier_id).model_dump()


@router.put("/dossiers/{dossier_id}/risk-checks/bam")
def put_bam(dossier_id: str, body: RiskCheckBody) -> dict:
    if dossier_store.get_by_id(dossier_id) is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    row = risk_repository.upsert_bam(
        dossier_id,
        status=body.status,
        rating=body.rating,
        source=body.source,
        comment=body.comment,
        checked_by=body.checked_by,
    )
    return {"status": row.status, "rating": row.rating, "source": row.source}


@router.put("/dossiers/{dossier_id}/risk-checks/incidents")
def put_incidents(dossier_id: str, body: RiskCheckBody) -> dict:
    if dossier_store.get_by_id(dossier_id) is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    row = risk_repository.upsert_incidents(
        dossier_id,
        status=body.status,
        source=body.source,
        comment=body.comment,
        checked_by=body.checked_by,
    )
    return {"status": row.status, "source": row.source}


@router.post("/dossiers/{dossier_id}/memos")
def create_memo(dossier_id: str, body: MemoCreateBody) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    import json

    row = memo_repository.create(
        dossier_id=dossier_id,
        content_json=json.dumps(body.content, ensure_ascii=False),
        score_snapshot_json=json.dumps((record.analyse or {}).get("scoring") or {}, default=str),
        quality_snapshot_json=json.dumps((record.analyse or {}).get("quality") or {}, default=str),
        analysis_fingerprint=(record.analyse or {}).get("analysisFingerprint") or "",
        status="DRAFT",
    )
    return {"id": row.id, "status": row.status, "version": row.version}


@router.get("/dossiers/{dossier_id}/memos")
def list_memos(dossier_id: str) -> list[dict]:
    if dossier_store.get_by_id(dossier_id) is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return [
        {
            "id": row.id,
            "status": row.status,
            "version": row.version,
            "signedBy": row.signed_by,
            "signedAt": row.signed_at.isoformat() if row.signed_at else None,
        }
        for row in memo_repository.list_for_dossier(dossier_id)
    ]


@router.get("/dossiers/{dossier_id}/memos/{memo_id}")
def get_memo(dossier_id: str, memo_id: str) -> dict:
    row = memo_repository.get(memo_id)
    if row is None or row.dossier_id != dossier_id:
        raise HTTPException(status_code=404, detail="Mémo introuvable")
    import json

    return {
        "id": row.id,
        "status": row.status,
        "version": row.version,
        "content": json.loads(row.content_json or "{}"),
        "signedBy": row.signed_by,
        "signedAt": row.signed_at.isoformat() if row.signed_at else None,
        "contentHash": row.content_hash,
    }


@router.post("/dossiers/{dossier_id}/memos/{memo_id}/sign")
def sign_memo(dossier_id: str, memo_id: str, body: MemoCreateBody) -> dict:
    import hashlib
    import json

    row = memo_repository.get(memo_id)
    if row is None or row.dossier_id != dossier_id:
        raise HTTPException(status_code=404, detail="Mémo introuvable")
    digest = hashlib.sha256((row.content_json or "").encode("utf-8")).hexdigest()
    signed = memo_repository.sign(
        memo_id,
        signed_by=body.signed_by or "Analyste",
        signed_role=body.signed_role or "analyste",
        content_hash=digest,
    )
    return {"id": signed.id if signed else memo_id, "status": signed.status if signed else "SIGNED", "contentHash": digest}


@router.get("/dossiers/{dossier_id}/analyses/{run_id}/fields")
def analysis_fields(dossier_id: str, run_id: str) -> list[dict]:
    run = analysis_run_repository.get(run_id)
    if run is None or run.dossier_id != dossier_id:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    record = dossier_store.get_by_id(dossier_id)
    fields = ((record.analyse or {}).get("financialStatements") or {})
    # Projection légère : champs du dernier workspace, pas l'audit V6 complet.
    result = []
    for group in ("actif", "passif", "cpc", "esg"):
        for row in fields.get(group) or []:
            result.append(
                {
                    "code": row.get("label"),
                    "label": row.get("label"),
                    "current": {
                        "observedValue": row.get("n"),
                        "usableValue": row.get("n") if row.get("nStatus") not in {"suspect", "conflicting", "missing"} else None,
                        "status": row.get("nStatus"),
                    },
                    "previous": {
                        "observedValue": row.get("n1"),
                        "usableValue": row.get("n1") if row.get("n1Status") not in {"suspect", "conflicting", "missing"} else None,
                        "status": row.get("n1Status"),
                    },
                }
            )
    return result


@router.post("/dossiers/{dossier_id}/documents/replace", response_model=StoredDossierRecord)
async def replace_dossier_document(
    dossier_id: str,
    name: str = Form(...),
    file: UploadFile = File(...),
) -> StoredDossierRecord:
    return await dossier_service.replace_document(dossier_id, name, file)
