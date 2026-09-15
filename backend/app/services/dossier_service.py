from __future__ import annotations

import io
import json
import logging
import random
import re
from datetime import date, datetime

from fastapi import HTTPException, UploadFile

from app.schemas.create_dossier import (
    CreateDossierPayload,
    CreateDossierResponse,
    StoredDossierRecord,
    StoredFileMeta,
)
from app.schemas.dossier import Dossier, DossierListResponse
from app.services import dossier_store, file_validation, kafka_publisher, minio_storage

logger = logging.getLogger(__name__)

ALLOWED_CONTENT = {
    "application/pdf",
    "application/x-pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
}
ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")

_PRESET_SECTORS = {
    "Transport",
    "Immobilier",
    "BTP",
    "Santé",
    "Industrie",
    "Commerce",
    "Agriculture",
    "Tourisme",
    "Tech & Services",
    "Énergie",
    "Automobile",
    "Éducation",
}


def _sector_fields(secteur: str) -> tuple[str, str | None, str | None]:
    raw = (secteur or "").strip()
    if not raw:
        return "", None, None
    if raw in _PRESET_SECTORS:
        return raw, raw, None
    return raw, None, None


def _store_sector(secteur: str) -> str:
    raw, _norm, _code = _sector_fields(secteur)
    return raw


def list_dossiers(status: str | None, q: str | None) -> DossierListResponse:
    items = [dossier_store.to_list_item(r) for r in dossier_store.list_created()]
    if status and status != "all":
        items = [d for d in items if d.status == status]
    if q:
        needle = q.lower().strip()
        items = [
            d
            for d in items
            if needle in d.id.lower()
            or needle in d.name.lower()
            or needle in d.sector.lower()
            or needle in d.analyst.lower()
            or needle in (d.noDemande or "").lower()
            or needle in (d.noPv or "").lower()
        ]
    return DossierListResponse(items=items, total=len(items))


def get_dossier(dossier_id: str) -> Dossier:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier_store.to_list_item(record)


def get_dossier_detail(dossier_id: str) -> StoredDossierRecord:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return record


def _make_ref(raison: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", raison.upper())[:3].ljust(3, "X")
    year = date.today().year
    seq = random.randint(1000, 9999)
    return f"{letters}-{year}-{seq}"


def _detect_file_kind(data: bytes, filename: str) -> str | None:
    name = (filename or "").lower()
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".png"):
        return "png"
    if name.endswith((".jpg", ".jpeg")):
        return "jpeg"
    return None


def _validate_upload(file: UploadFile, data: bytes) -> None:
    file_validation.validate_upload(file.filename or "file", data, file.content_type)


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    data = await file.read()
    _validate_upload(file, data)
    return data, file.filename or "file"


def _put_bytes(
    *,
    dossier_id: str,
    category: str,
    filename: str,
    data: bytes,
    content_type: str | None,
) -> StoredFileMeta:
    key = minio_storage.upload_file(
        dossier_id=dossier_id,
        category=category,
        filename=filename,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return StoredFileMeta(
        name=filename,
        objectKey=key,
        size=len(data),
        contentType=content_type or "application/octet-stream",
        category=category,
        sha256=file_validation.sha256_bytes(data),
        version=1,
    )


def _parse_payload(data: str) -> CreateDossierPayload:
    try:
        return CreateDossierPayload.model_validate(json.loads(data))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Payload invalide : {exc}") from exc


async def create_dossier(
    data: str,
    documents: list[UploadFile],
    proforma: UploadFile | None,
) -> CreateDossierResponse:
    payload = _parse_payload(data)

    if not documents:
        raise HTTPException(
            status_code=400,
            detail="Au moins un document entreprise est requis",
        )
    if proforma is None or not (proforma.filename or "").strip():
        raise HTTPException(status_code=400, detail="Pièce proforma requise")

    dossier_id = _make_ref(payload.entreprise.raisonSociale)
    now = datetime.now()
    today = now.strftime("%d/%m/%Y")
    received_time = now.strftime("%H:%M")
    stored_files: list[StoredFileMeta] = []

    try:
        for doc in documents:
            raw, name = await _read_upload(doc)
            stored_files.append(
                _put_bytes(
                    dossier_id=dossier_id,
                    category="entreprise",
                    filename=name,
                    data=raw,
                    content_type=doc.content_type,
                )
            )

        raw_pf, name_pf = await _read_upload(proforma)
        stored_files.append(
            _put_bytes(
                dossier_id=dossier_id,
                category="proforma",
                filename=name_pf,
                data=raw_pf,
                content_type=proforma.content_type,
            )
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Échec upload fichiers pour %s", dossier_id)
        raise HTTPException(
            status_code=503,
            detail=f"Stockage fichiers indisponible : {exc}",
        ) from exc

    sector_raw, sector_normalized, benchmark_code = _sector_fields(
        payload.entreprise.secteurRaw or payload.entreprise.secteur
    )
    record = StoredDossierRecord(
        id=dossier_id,
        name=payload.entreprise.raisonSociale.strip(),
        sector=sector_raw or payload.entreprise.secteur,
        sectorRaw=sector_raw,
        sectorNormalized=sector_normalized,
        benchmarkSectorCode=benchmark_code,
        amount=payload.financement.montantDemande,
        duration=payload.financement.dureeMois,
        score=0,
        status="pending",
        analyst="Analyste",
        receivedDaysAgo=0,
        date=today,
        urgency=payload.financement.urgence,
        receivedLabel=f"Auj. {received_time}",
        ice=payload.entreprise.ice.strip(),
        identifiantFiscal=payload.entreprise.identifiantFiscal.strip(),
        rc=payload.entreprise.rc.strip(),
        nature=payload.financement.nature,
        valeurBien=payload.financement.valeurBien,
        apport=payload.financement.apport,
        fournisseur=payload.fournisseurBien.fournisseur.strip(),
        proformaReference=payload.fournisseurBien.proformaReference.strip(),
        natureBien=payload.fournisseurBien.natureBien.strip(),
        etat=payload.fournisseurBien.etat,
        valeurHt=payload.fournisseurBien.valeurHt,
        valeurTtc=payload.fournisseurBien.valeurTtc,
        files=stored_files,
    )
    dossier_store.prepend(record)

    kafka_publisher.publish_dossier_created(
        {
            "id": record.id,
            "name": record.name,
            "sector": record.sector,
            "amount": record.amount,
            "duration": record.duration,
            "status": record.status,
            "ice": record.ice,
            "rc": record.rc,
            "nature": record.nature,
            "apportPct": record.apport,
            "files": [f.model_dump() for f in record.files],
            "createdAt": now.isoformat(timespec="seconds"),
        }
    )

    return CreateDossierResponse(
        id=dossier_id,
        status="pending",
        message=f"Dossier {dossier_id} créé — {len(stored_files)} fichier(s) enregistrés",
    )


def _apply_status(dossier_id: str, status: str) -> Dossier:
    record = dossier_store.update_status(dossier_id, status)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return dossier_store.to_list_item(record)


def approve_dossier(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    from app.services.decision_service import approve

    return approve(dossier_id, reason, comment)


def reject_dossier(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    from app.services.decision_service import reject

    return reject(dossier_id, reason, comment)


def reserve_dossier(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    from app.services.decision_service import reserve

    return reserve(dossier_id, reason, comment)


def cancel_decision(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    from app.services.decision_service import cancel

    return cancel(dossier_id, reason, comment)


async def replace_document(
    dossier_id: str,
    target_name: str,
    file: UploadFile,
) -> StoredDossierRecord:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    slot = target_name.strip()
    if not slot:
        raise HTTPException(status_code=400, detail="Nom de document requis")

    has_slot = any(existing.name == slot for existing in record.files)
    if not has_slot and len(record.files) >= 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 documents autorisés pour ce dossier",
        )

    category = "entreprise"
    for existing in record.files:
        if existing.name == slot:
            category = existing.category
            break
    else:
        lowered = slot.lower()
        if "proforma" in lowered or "facture" in lowered:
            category = "proforma"

    try:
        raw, filename = await _read_upload(file)
        stored_name = slot if has_slot else (filename or slot)
        meta = _put_bytes(
            dossier_id=dossier_id,
            category=category,
            filename=stored_name,
            data=raw,
            content_type=file.content_type,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Échec remplacement document pour %s", dossier_id)
        raise HTTPException(
            status_code=503,
            detail=f"Stockage fichiers indisponible : {exc}",
        ) from exc

    updated = dossier_store.replace_file(dossier_id, slot if has_slot else stored_name, meta)
    if not updated:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    from app.services.workspace_builder import overlay_live_documents

    synced = overlay_live_documents(updated, updated.analyse)
    persisted = dossier_store.update_analyse(dossier_id, analyse=synced)
    return persisted or updated
