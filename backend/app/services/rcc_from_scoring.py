"""Projection des dossiers scoring WFB vers la file RCC."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.analyse import (
    AccountingControlView,
    CompanyInfo,
    DocumentSummary,
    ExtractedField,
    ExtractionSummary,
    IdentityInfo,
    RCC_ELEMENTS,
    SCORING_EXTRA_ELEMENTS,
    ScoringAnalysisResult,
)
from app.services.rcc_dossier_store import RccDossier, rcc_dossier_store
from app.services.rcc_projection import build_identite, clean_activite, project_rcc_result

logger = logging.getLogger(__name__)

_SCORING_STATUS = {
    "pending": "pending",
    "analyzing": "pending",
    "review": "pending",
    "approved": "validated",
    "validated": "validated",
    "rejected": "rejected",
    "escalated": "escalated",
}


def _iso(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value[:19], fmt)
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return datetime.now(timezone.utc).isoformat()


def _liasse_file(record) -> Any:
    files = list(record.files or [])
    for item in files:
        name = (item.name or "").lower()
        if item.category in {"liasse", "documents"} or name.endswith(".pdf"):
            if "proforma" in name:
                continue
            return item
    return files[0] if files else None


def _parse_audit_payload(payload: Any) -> ScoringAnalysisResult | None:
    if not isinstance(payload, dict) or not (payload.get("fields") or payload.get("document")):
        return None
    try:
        return ScoringAnalysisResult.model_validate(payload)
    except Exception:
        return None


def _load_local_audit(record) -> ScoringAnalysisResult | None:
    from app.core.config import settings

    roots = [
        settings.files_dir / "dossiers" / record.id / "audit",
        settings.files_dir / "audit" / record.id,
    ]
    files: list[Any] = []
    for root in roots:
        if root.exists():
            files.extend(root.glob("*v6_full_audit.json"))
    files = sorted(set(files), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        try:
            parsed = _parse_audit_payload(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
    return None


def _load_audit_result(record) -> ScoringAnalysisResult | None:
    from app.db.repositories import analysis_run_repository
    from app.services import minio_storage

    candidates: list[ScoringAnalysisResult] = []
    try:
        runs = analysis_run_repository.list_for_dossier(record.id)
    except Exception:
        runs = []
    for run in runs:
        key = getattr(run, "full_audit_object_key", None)
        if not key:
            continue
        try:
            raw = minio_storage.download_bytes(key)
            parsed = _parse_audit_payload(json.loads(raw.decode("utf-8")))
        except Exception:
            logger.warning("Audit V6 illisible pour %s", record.id)
            parsed = None
        if parsed is not None:
            candidates.append(parsed)
    local = _load_local_audit(record)
    if local is not None:
        candidates.append(local)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: sum(
            1 for field in item.fields if field.value is not None or field.value_n1 is not None
        ),
    )


def scoring_analysis_result(record) -> ScoringAnalysisResult | None:
    from app.services.analyse_job_store import job_store

    candidates: list[ScoringAnalysisResult] = []
    job = job_store.get_for_dossier(record.id)
    if job is not None and job.result is not None:
        candidates.append(job.result)
    audited = _load_audit_result(record)
    if audited is not None:
        candidates.append(audited)
    workspace = result_from_workspace(record)
    if workspace is not None:
        candidates.append(workspace)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: sum(
            1 for field in item.fields if field.value is not None or field.value_n1 is not None
        ),
    )


_FIELD_META = {code: (number, label, source) for number, code, label, source in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)}


def _as_float(value: Any) -> float | None:
    if value in (None, "", "—", "-", "–"):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _statement_rows(analyse: dict[str, Any]) -> list[dict[str, Any]]:
    statements = analyse.get("financialStatements") or {}
    if not isinstance(statements, dict):
        return []
    rows: list[dict[str, Any]] = []
    for value in statements.values():
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, dict))
    return rows


def _sector_candidates(record) -> tuple[Any, ...]:
    analyse = record.analyse or {}
    sector = (analyse.get("sectorAnalysis") or {}).get("sector") or {}
    return (
        record.sectorNormalized,
        sector.get("label"),
        (analyse.get("header") or {}).get("sectorLabel"),
        record.sector,
    )


def result_from_workspace(record) -> ScoringAnalysisResult | None:
    analyse = record.analyse or {}
    rows = _statement_rows(analyse)
    if not rows:
        return None
    fields: list[ExtractedField] = []
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        meta = _FIELD_META.get(code, (0, row.get("label") or code, row.get("source") or ""))
        value = _as_float(row.get("n") if "n" in row else row.get("value"))
        value_n1 = _as_float(row.get("n1") if "n1" in row else row.get("value_n1"))
        status = row.get("nStatus") or row.get("status") or ("confirmed" if value is not None else "missing")
        confidence = row.get("confidence")
        try:
            confidence = float(confidence or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1:
            confidence = min(1.0, confidence / 100.0)
        try:
            fields.append(
                ExtractedField(
                    number=meta[0] or 1,
                    code=code,
                    label=row.get("label") or meta[1],
                    source=row.get("source") or meta[2],
                    value=value,
                    value_n1=value_n1,
                    status=status,
                    confidence=confidence,
                    evidence=[],
                )
            )
        except Exception:
            continue
    if not fields:
        return None
    header = analyse.get("header") or {}
    period = analyse.get("period") or {}
    identity = IdentityInfo(
        identifiant_fiscal=record.identifiantFiscal or None,
        ice=record.ice or None,
        raison_sociale=header.get("companyName") or record.name,
        activite=None,
        secteur=clean_activite(*_sector_candidates(record)),
        period_start=period.get("start"),
        period_end=period.get("end"),
    )
    company = CompanyInfo(
        raison_sociale=identity.raison_sociale,
        ice=identity.ice,
        identifiant_fiscal=identity.identifiant_fiscal,
        rc=record.rc or None,
    )
    controls = []
    for item in analyse.get("controls") or []:
        try:
            controls.append(AccountingControlView.model_validate(item))
        except Exception:
            continue
    return ScoringAnalysisResult(
        document=DocumentSummary(
            filename=_liasse_file(record).name if _liasse_file(record) else f"{record.id}.pdf",
            pages_total=0,
            pages_processed=0,
            pages_skipped=0,
            pages_failed=0,
            company=company,
            identity=identity,
        ),
        extraction=ExtractionSummary(model="v6"),
        fields=fields,
        completeness_pct=float((analyse.get("scoring") or {}).get("dossierCompletenessPct") or 0),
        controls=controls,
    )


def _fields_have_values(fields: Any) -> bool:
    for item in fields or []:
        if isinstance(item, dict):
            if item.get("value") is not None or item.get("value_n1") is not None:
                return True
            continue
        if getattr(item, "value", None) is not None or getattr(item, "value_n1", None) is not None:
            return True
    return False


def _stub_result(record) -> ScoringAnalysisResult:
    header = (record.analyse or {}).get("header") or {}
    period = (record.analyse or {}).get("period") or {}
    identity = IdentityInfo(
        identifiant_fiscal=record.identifiantFiscal or None,
        ice=record.ice or None,
        raison_sociale=header.get("companyName") or record.name,
        activite=None,
        secteur=clean_activite(*_sector_candidates(record)),
        period_start=period.get("start"),
        period_end=period.get("end"),
    )
    company = CompanyInfo(
        raison_sociale=identity.raison_sociale,
        ice=identity.ice,
        identifiant_fiscal=identity.identifiant_fiscal,
        rc=record.rc or None,
    )
    return ScoringAnalysisResult(
        document=DocumentSummary(
            filename=_liasse_file(record).name if _liasse_file(record) else f"{record.id}.pdf",
            pages_total=0,
            pages_processed=0,
            pages_skipped=0,
            pages_failed=0,
            company=company,
            identity=identity,
        ),
        extraction=ExtractionSummary(model="v6"),
        fields=[],
        completeness_pct=float(((record.analyse or {}).get("scoring") or {}).get("dossierCompletenessPct") or 0),
    )


def _pdf_bytes(record) -> bytes | None:
    from app.services import minio_storage

    item = _liasse_file(record)
    if item is None:
        return None
    try:
        return minio_storage.download_bytes(item.objectKey)
    except Exception:
        logger.warning("PDF scoring introuvable pour %s", record.id)
        return None


def _fill_dossier(dossier: RccDossier, *, record, result, projected, identite) -> RccDossier:
    dossier.result = projected
    dossier.scoring_result = result
    dossier.identite = identite
    dossier.client_name = identite.get("raison_sociale") or dossier.client_name or record.name
    dossier.ice = identite.get("ice") or dossier.ice or record.ice
    dossier.exercice_date = identite.get("period_end") or dossier.exercice_date
    dossier.sector = identite.get("secteur") or clean_activite(*_sector_candidates(record))
    dossier.completeness_pct = result.completeness_pct
    dossier.updated_at = _iso(None)
    dossier.origin = "scoring"
    return dossier


def import_scoring_record(record) -> RccDossier:
    existing = rcc_dossier_store.get(record.id)
    result = scoring_analysis_result(record) or _stub_result(record)
    projected = project_rcc_result(result)
    identite = projected.get("identite") or build_identite(result)
    identite["activite"] = clean_activite(identite.get("activite"))
    identite["secteur"] = clean_activite(identite.get("secteur"), *_sector_candidates(record))
    projected["identite"] = identite
    if isinstance(projected.get("document"), dict):
        projected["document"]["identity"] = identite
    incoming_has = _fields_have_values(projected.get("fields"))
    existing_has = existing is not None and _fields_have_values((existing.result or {}).get("fields"))
    if existing is not None and existing_has and not incoming_has:
        existing.identite["activite"] = clean_activite(identite.get("activite"), existing.identite.get("activite"))
        existing.identite["secteur"] = clean_activite(identite.get("secteur"), existing.identite.get("secteur"))
        existing.sector = clean_activite(identite.get("secteur"), existing.sector)
        return existing
    if existing is not None:
        return rcc_dossier_store.put(_fill_dossier(existing, record=record, result=result, projected=projected, identite=identite))
    pdf_bytes = _pdf_bytes(record)
    pdf_path = None
    if pdf_bytes:
        pdf_path = str(rcc_dossier_store.save_pdf(record.id, pdf_bytes))
    job = None
    try:
        from app.services.analyse_job_store import job_store

        job = job_store.get_for_dossier(record.id)
    except Exception:
        job = None
    now = _iso(record.date)
    dossier = RccDossier(
        id=record.id,
        job_id=(job.job_id if job else record.analyseJobId),
        client_name=identite.get("raison_sociale") or record.name,
        ice=identite.get("ice") or record.ice,
        credit_amount=record.amount,
        exercice_date=identite.get("period_end"),
        status=_SCORING_STATUS.get(record.status, "pending"),
        created_at=now,
        updated_at=now,
        sector=identite.get("secteur") or clean_activite(*_sector_candidates(record)),
        filename=_liasse_file(record).name if _liasse_file(record) else None,
        pdf_path=pdf_path,
        completeness_pct=result.completeness_pct,
        result=projected,
        scoring_result=result,
        identite=identite,
        origin="scoring",
    )
    rcc_dossier_store.put(dossier)
    return dossier


def scoring_list_summaries() -> list[dict[str, Any]]:
    from app.services import dossier_store

    items = []
    for record in dossier_store.list_created():
        if rcc_dossier_store.get(record.id) is not None:
            continue
        scoring = (record.analyse or {}).get("scoring") or {}
        items.append(
            {
                "id": record.id,
                "job_id": record.analyseJobId,
                "client_name": record.name,
                "ice": record.ice or None,
                "credit_amount": record.amount,
                "exercice_date": ((record.analyse or {}).get("period") or {}).get("end"),
                "status": _SCORING_STATUS.get(record.status, "pending"),
                "status_label": "À réviser" if _SCORING_STATUS.get(record.status, "pending") == "pending" else None,
                "created_at": _iso(record.date),
                "updated_at": _iso(record.date),
                "sector": clean_activite(*_sector_candidates(record)),
                "filename": _liasse_file(record).name if _liasse_file(record) else None,
                "has_document": bool(_liasse_file(record)),
                "completeness_pct": float(scoring.get("dossierCompletenessPct") or 0),
                "override_count": 0,
                "motif": None,
                "comment": None,
                "decided_by": None,
                "decided_at": None,
                "identite": {
                    "raison_sociale": record.name,
                    "ice": record.ice,
                    "identifiant_fiscal": record.identifiantFiscal,
                    "activite": None,
                    "secteur": clean_activite(*_sector_candidates(record)),
                },
                "identifiant_fiscal": record.identifiantFiscal or None,
                "activite": None,
                "origin": "scoring",
            }
        )
        if items[-1]["status_label"] is None:
            from app.services.rcc_dossier_store import STATUS_LABELS

            items[-1]["status_label"] = STATUS_LABELS.get(items[-1]["status"], items[-1]["status"])
    return items


def get_or_import(dossier_id: str) -> RccDossier | None:
    from app.services import dossier_store

    record = dossier_store.get_by_id(dossier_id)
    if record is not None:
        return import_scoring_record(record)
    return rcc_dossier_store.get(dossier_id)
