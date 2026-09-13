"""Ingestion des dossiers PVC → store WFB + lancement du moteur v10."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, UploadFile

from app.schemas.create_dossier import StoredDossierRecord
from app.schemas.pvc import (
    PartnerAnalyseResponse,
    PartnerRatioItem,
    PvcDossierPv,
)
from app.services import dossier_service, dossier_store, kafka_publisher
from app.services.analyse_job_store import job_store

logger = logging.getLogger(__name__)


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fr_date(raw: str | None) -> str:
    if not raw:
        return datetime.now().strftime("%d/%m/%Y")
    text = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:26].replace("Z", ""), fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    if "T" in text:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
    return datetime.now().strftime("%d/%m/%Y")


def _liasse_name(filename: str) -> str:
    name = (filename or "liasse.pdf").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    lowered = name.lower()
    if "liasse" in lowered or "bilan" in lowered or "cpc" in lowered:
        return name
    return f"liasse-{name}"


def _map_etat(neuf_occasion: str | None) -> str:
    raw = (neuf_occasion or "").strip().lower()
    if raw in {"occasion", "occassion", "occasionnel", "used", "false", "0"}:
        return "occasion"
    return "neuf"


def parse_pvc_payload(data: str) -> PvcDossierPv:
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON data invalide : {exc}") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="data doit être un objet JSON (DossierPv).")
    if "noDemande" not in raw and isinstance(raw.get("dossier"), dict):
        raw = {**raw["dossier"], **{k: v for k, v in raw.items() if k != "dossier"}}
    try:
        return PvcDossierPv.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Payload PVC invalide : {exc}") from exc


def pvc_to_record(
    payload: PvcDossierPv,
    files: list,
    *,
    existing: StoredDossierRecord | None = None,
) -> StoredDossierRecord:
    no_demande = payload.noDemande.strip()
    simulation = payload.simulations[0] if payload.simulations else None
    biens = list(simulation.biens) if simulation else []
    if not biens:
        for item in payload.simulations:
            biens.extend(item.biens)
    bien = biens[0] if biens else None
    duration = int(round(_num(simulation.duree if simulation else None, 0)))
    amount = int(round(_num(payload.montantTotal, 0)))
    valeur_ht = sum(_num(b.montantHT) for b in biens) if biens else _num(payload.montantTotal)
    valeur_ttc = _num(payload.montantTotal, valeur_ht)
    secteur = (payload.activite or payload.segmentMarche or payload.segmentationWafabail or "").strip()
    rc = (payload.rcAnalytique or "").strip()
    if payload.villeRC and rc and payload.villeRC not in rc:
        rc = f"{rc}/{payload.villeRC}" if "/" not in rc else rc
    now = datetime.now()
    record = StoredDossierRecord(
        id=existing.id if existing else no_demande,
        name=(payload.nomClient or "").strip() or no_demande,
        sector=dossier_service._store_sector(secteur),
        amount=amount,
        duration=duration,
        score=existing.score if existing else 0,
        status=existing.status if existing and existing.status not in {"pending"} else "pending",
        analyst=(payload.commercialNom or "").strip() or "PVC",
        receivedDaysAgo=0,
        date=_fr_date(payload.dateReceptionEbail or payload.dateCreation),
        urgency="haute" if payload.enRAC else "normale",
        receivedLabel=f"PVC {now.strftime('%H:%M')}",
        ice=existing.ice if existing else "",
        rc=rc,
        nature="mobilier",
        valeurBien=valeur_ttc or valeur_ht,
        apport=0,
        fournisseur=(payload.fournisseur or "").strip(),
        proformaReference=(simulation.noContrat if simulation else "") or "",
        natureBien=(bien.description if bien else "") or "",
        etat=_map_etat(bien.neufOccasion if bien else None),
        valeurHt=valeur_ht,
        valeurTtc=valeur_ttc,
        files=files,
        analyseJobId=existing.analyseJobId if existing else None,
        analyseStatus=existing.analyseStatus if existing else None,
        analyse=existing.analyse if existing else None,
        source="pvc",
        noDemande=no_demande,
        noPv=payload.noPv,
        pvcId=str(payload.id) if payload.id is not None else None,
        pvc=payload.model_dump(mode="json"),
    )
    if existing and existing.status in {"approved", "rejected", "reserved"}:
        record = record.model_copy(update={"status": existing.status, "decisionDate": existing.decisionDate})
    return record


async def ingest_pvc_dossier(
    data: str,
    liasse: UploadFile,
    extras: list[UploadFile] | None = None,
) -> StoredDossierRecord:
    payload = parse_pvc_payload(data)
    no_demande = payload.noDemande.strip()
    if not no_demande:
        raise HTTPException(status_code=400, detail="noDemande est obligatoire.")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{3,80}", no_demande):
        raise HTTPException(
            status_code=400,
            detail="noDemande invalide (3-80 caractères : lettres, chiffres, . _ : -).",
        )
    if liasse is None or not (liasse.filename or "").strip():
        raise HTTPException(status_code=400, detail="Fichier PDF liasse obligatoire (champ liasse).")

    existing = dossier_store.get_by_no_demande(no_demande)
    stored_files = []
    uploads = [(liasse, True)]
    for extra in extras or []:
        if extra is not None and (extra.filename or "").strip():
            uploads.append((extra, False))

    try:
        for file, is_primary in uploads:
            raw, name = await dossier_service._read_upload(file)
            if not raw.startswith(b"%PDF"):
                raise HTTPException(
                    status_code=422,
                    detail=f"{name} n'est pas un PDF valide (liasse fiscale attendue).",
                )
            stored_name = _liasse_name(name)
            if is_primary and "liasse" not in stored_name.lower() and "bilan" not in stored_name.lower():
                stored_name = _liasse_name(stored_name)
            stored_files.append(
                dossier_service._put_bytes(
                    dossier_id=no_demande,
                    category="entreprise",
                    filename=stored_name,
                    data=raw,
                    content_type=file.content_type or "application/pdf",
                )
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload PVC impossible pour %s", no_demande)
        raise HTTPException(status_code=503, detail=f"Stockage fichiers indisponible : {exc}") from exc

    if existing:
        kept = [f for f in existing.files if f.category != "entreprise"]
        stored_files = stored_files + kept

    record = pvc_to_record(payload, stored_files, existing=existing)
    dossier_store.prepend(record)
    kafka_publisher.publish_dossier_created(
        {
            "id": record.id,
            "noDemande": record.noDemande,
            "noPv": record.noPv,
            "name": record.name,
            "source": "pvc",
            "amount": record.amount,
            "duration": record.duration,
            "status": record.status,
            "files": [f.model_dump() for f in record.files],
        }
    )
    return record


def partner_poll_path(no_demande: str) -> str:
    encoded = quote(no_demande, safe="")
    return f"/api/v1/partners/pvc/dossiers/{encoded}"


def build_partner_analyse(record: StoredDossierRecord) -> PartnerAnalyseResponse:
    job = job_store.get_for_dossier(record.id)
    job_status = job.status if job else (record.analyseStatus or "pending")
    workspace = record.analyse or {}
    scoring = workspace.get("scoring") or {}
    attention = scoring.get("attention") or {}
    header = workspace.get("header") or {}
    ratios_block = workspace.get("ratios") or {}
    documents = workspace.get("documents") or {}
    extractions = documents.get("extractions") or {}
    ice = record.ice or None
    rc = record.rc or None
    exercise = None
    for extraction in extractions.values():
        for field in extraction.get("fields") or []:
            label = (field.get("label") or "").lower()
            if label == "ice" and field.get("value") not in (None, "—"):
                ice = ice or str(field.get("value"))
            if label == "rc" and field.get("value") not in (None, "—"):
                rc = rc or str(field.get("value"))
            if label in {"période", "exercice"} and field.get("value") not in (None, "—"):
                exercise = str(field.get("value"))

    ratios = [
        PartnerRatioItem(
            label=item.get("label") or "",
            value=item.get("value"),
            status=item.get("status"),
        )
        for item in (ratios_block.get("items") or [])
        if item.get("label")
    ]

    message = None
    error = None
    if job_status in {"queued", "processing"}:
        message = "Analyse en file d'attente ou en cours."
    elif job_status == "failed":
        error = (job.error if job else None) or "L'analyse a échoué."
        message = error
    elif not scoring.get("score") and not record.score:
        message = "Aucune analyse n'a encore été exécutée sur ce dossier."
        job_status = job_status or "pending"

    completeness = scoring.get("dossierCompletenessPct")
    try:
        completeness_pct = float(completeness) if completeness is not None else None
    except (TypeError, ValueError):
        completeness_pct = None

    return PartnerAnalyseResponse(
        noDemande=record.noDemande or record.id,
        noPv=record.noPv,
        id=record.pvcId,
        wfb_id=record.id,
        nomClient=record.name,
        status=record.status if job_status == "completed" else (
            "analyzing" if job_status in {"queued", "processing"} else record.status
        ),
        analyseStatus=job_status,
        job_id=job.job_id if job else record.analyseJobId,
        progress_pct=job.progress_pct if job else None,
        message=message,
        score=int(round(float(scoring.get("score")))) if scoring.get("score") is not None else record.score or None,
        classe=scoring.get("classe") or header.get("classe"),
        decision=scoring.get("riskLabel"),
        recommandation=scoring.get("recommendation"),
        points_forts=list(attention.get("pointsForts") or []),
        points_vigilance=list(attention.get("pointsVigilance") or []),
        score_final=attention.get("scoreFinal"),
        ice=ice,
        rc=rc,
        exercise=exercise,
        year_labels=list(workspace.get("yearLabels") or []),
        completeness_pct=completeness_pct,
        ratios=ratios,
        dossier=record.pvc or {},
        stream_url=f"/api/v1/analyse/jobs/{job.job_id}/stream" if job else None,
        result_url=f"/api/v1/analyse/jobs/{job.job_id}/result" if job else None,
        error=error,
    )
