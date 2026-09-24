from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.sector.mapping import mapping_from_hcp_code
from app.sector.sources_catalog import (
    DEFAULT_SOURCE_ID,
    branches_for_source,
    get_source,
    resolve_source_id,
)
from app.services import dossier_store
from app.services import sector_source_config
from app.services.sector_analysis_service import sector_analysis_service
from app.services.sector_refresh_service import sector_sync_service

router = APIRouter(prefix="/sectors", tags=["sectors"])
dossier_router = APIRouter(tags=["dossiers"])


class RefreshBody(BaseModel):
    force: bool = False


class SectorMappingBody(BaseModel):
    hcpSectorCode: str
    reason: str = Field(default="Modification manuelle du secteur par l'analyste", min_length=1)


class DefaultSourceBody(BaseModel):
    sourceId: str
    actor: str | None = None


class SourceFlagsBody(BaseModel):
    enabled: bool | None = None
    selectable: bool | None = None
    actor: str | None = None


class DossierSectorSourceBody(BaseModel):
    sourceId: str
    reason: str = Field(
        default="Changement de source de données sectorielles par l'analyste",
        min_length=1,
    )


def _sync_status_by_code() -> dict[str, dict]:
    payload = sector_sync_service.status_payload()
    datasets = payload.get("datasets") or []
    has_obs = any(int(item.get("observations") or 0) > 0 for item in datasets)
    last_checked = next((item.get("lastCheckedAt") for item in datasets if item.get("lastCheckedAt")), None)
    last_updated = next((item.get("lastUpdatedAt") for item in datasets if item.get("lastUpdatedAt")), None)
    return {
        "hcp": {
            "status": "AVAILABLE" if has_obs else "NO_DATA",
            "lastCheckedAt": last_checked,
            "lastUpdatedAt": last_updated,
            "datasets": datasets,
        },
        "HCP": {
            "status": "AVAILABLE" if has_obs else "NO_DATA",
            "lastCheckedAt": last_checked,
            "lastUpdatedAt": last_updated,
        },
        "apsf": {"status": "NOT_IMPLEMENTED"},
        "APSF": {"status": "NOT_IMPLEMENTED"},
        "internal": {"status": "NOT_IMPLEMENTED"},
        "INTERNAL": {"status": "NOT_IMPLEMENTED"},
    }


def _result_from_record(record):
    from app.schemas.analyse import ScoringAnalysisResult

    raw = (record.analyse or {}).get("_result")
    if isinstance(raw, dict):
        try:
            return ScoringAnalysisResult.model_validate(raw)
        except Exception:
            return None
    return None


def _dossier_source_id(record) -> str:
    pinned = getattr(record, "sectorSourceId", None)
    if pinned:
        return resolve_source_id(pinned, DEFAULT_SOURCE_ID)
    return resolve_source_id(sector_source_config.get_default_source_id(), DEFAULT_SOURCE_ID)


def _persist_workspace_analysis(dossier_id: str, record, analysis, *, sector_label: str | None = None):
    if not record.analyse or not isinstance(record.analyse, dict):
        return record
    workspace = dict(record.analyse)
    workspace["sectorAnalysis"] = analysis.model_dump(mode="json")
    if sector_label:
        header = dict(workspace.get("header") or {})
        subtitle = str(header.get("subtitle") or "")
        bits = [part.strip() for part in subtitle.split("·") if part.strip()]
        if bits:
            bits[0] = sector_label
            header["subtitle"] = " · ".join(bits)
        else:
            header["subtitle"] = sector_label
        workspace["header"] = header
        benchmark = dict(workspace.get("benchmark") or {})
        benchmark["sectorLabel"] = sector_label
        workspace["benchmark"] = benchmark
    dossier_store.update_analyse(dossier_id, analyse=workspace)
    return dossier_store.get_by_id(dossier_id) or record


@router.get("/branches")
def list_branches(sourceId: str | None = Query(default=None)) -> dict:
    """Branches de la source demandée (défaut = source globale)."""
    sid = resolve_source_id(sourceId or sector_source_config.get_default_source_id(), DEFAULT_SOURCE_ID)
    branches = branches_for_source(sid)
    src = get_source(sid)
    return {
        "sourceId": sid,
        "sourceLabel": src.short_label if src else sid,
        "items": [{"code": code, "label": label} for code, label in branches.items()],
        "total": len(branches),
    }


@router.get("/sources")
def list_sector_sources() -> dict:
    """Catalogue + configuration des sources (panneau Configuration)."""
    return sector_source_config.list_sources_for_api(status_by_code=_sync_status_by_code())


@router.put("/sources/default")
def put_default_source(body: DefaultSourceBody) -> dict:
    try:
        sector_source_config.set_default_source(body.sourceId, actor=body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return sector_source_config.list_sources_for_api(status_by_code=_sync_status_by_code())


@router.put("/sources/{source_id}")
def put_source_flags(source_id: str, body: SourceFlagsBody) -> dict:
    try:
        sector_source_config.update_source_flags(
            source_id,
            enabled=body.enabled,
            selectable=body.selectable,
            actor=body.actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return sector_source_config.list_sources_for_api(status_by_code=_sync_status_by_code())


@router.get("/sources/status")
def sources_status() -> dict:
    by_code = _sync_status_by_code()
    catalog = sector_source_config.list_sources_for_api(status_by_code=by_code)
    return {
        "defaultSourceId": catalog["defaultSourceId"],
        "sources": [
            {
                "id": item["id"],
                "code": item["code"],
                "status": item.get("syncStatus") or ("AVAILABLE" if item["implemented"] else "NOT_IMPLEMENTED"),
                "lastCheckedAt": item.get("lastSyncAt"),
                "lastUpdatedAt": item.get("lastSyncAt"),
                "enabled": item["enabled"],
                "selectable": item["selectable"],
                "isDefault": item["isDefault"],
                "supportsVaAnalysis": item["supportsVaAnalysis"],
            }
            for item in catalog["items"]
        ],
    }


@router.post("/refresh")
async def refresh_sources(body: RefreshBody | None = None) -> dict:
    if not settings.sector_data_enabled:
        raise HTTPException(status_code=503, detail="Données sectorielles désactivées")
    started = datetime.now(timezone.utc)
    results = await sector_sync_service.sync_all(force=bool(body.force) if body else False)
    completed = datetime.now(timezone.utc)
    changed = sum(1 for item in results if item.get("status") == "UPDATED")
    upserted = sum(int(item.get("rows_inserted") or 0) + int(item.get("rows_updated") or 0) for item in results)
    return {
        "status": "completed",
        "checked": len(results),
        "changed": changed,
        "updatedObservations": upserted,
        "startedAt": started.isoformat(),
        "completedAt": completed.isoformat(),
        "force": bool(body.force) if body else False,
        "results": results,
        "sourceId": "hcp",
    }


@dossier_router.get("/dossiers/{dossier_id}/sector-analysis")
async def get_sector_analysis(
    dossier_id: str,
    refresh: Literal["auto", "false", "force"] = Query(default="auto"),
) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if refresh == "force":
        if settings.sector_data_enabled and _dossier_source_id(record) == "hcp":
            await sector_sync_service.sync_all(force=True)
        trigger = False
    elif refresh == "auto":
        trigger = True
    else:
        trigger = False
    analysis = sector_analysis_service.analyze(
        record=record,
        result=_result_from_record(record),
        trigger_refresh=trigger,
    )
    payload = analysis.model_dump(mode="json")
    payload["sectorSourceId"] = _dossier_source_id(record)
    payload["defaultSourceId"] = sector_source_config.get_default_source_id()
    return payload


@dossier_router.put("/dossiers/{dossier_id}/sector-source")
def put_dossier_sector_source(dossier_id: str, body: DossierSectorSourceBody) -> dict:
    """Épingle une source sur le dossier. Change de taxonomie → mapping effacé."""
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    sid = resolve_source_id(body.sourceId, DEFAULT_SOURCE_ID)
    src = get_source(sid)
    if src is None:
        raise HTTPException(status_code=422, detail="Source inconnue")
    if not sector_source_config.is_source_enabled(sid):
        raise HTTPException(status_code=422, detail=f"La source « {src.short_label} » est désactivée.")
    if not src.supports_va_analysis:
        raise HTTPException(
            status_code=422,
            detail=(
                f"« {src.short_label} » n’est pas encore prête pour l’analyse VA. "
                "Activez HCP ou une source compatible."
            ),
        )
    if not sector_source_config.is_source_selectable(sid):
        raise HTTPException(
            status_code=422,
            detail=f"« {src.short_label} » n’est pas sélectionnable (voir Configuration).",
        )

    previous = _dossier_source_id(record)
    mapping_cleared = previous != sid

    patch: dict = {"sector_source_id": sid}
    if mapping_cleared:
        # Évite d'appliquer un code HCP_* (ou autre) à une taxonomie différente.
        patch["benchmark_sector_code"] = None

    updated = dossier_store.update_analyse(dossier_id, **patch)
    current = updated or record
    analysis = sector_analysis_service.analyze(
        record=current,
        result=_result_from_record(current),
        trigger_refresh=False,
    )
    current = _persist_workspace_analysis(dossier_id, current, analysis)

    return {
        "dossierId": dossier_id,
        "previousSourceId": previous,
        "sectorSourceId": sid,
        "sourceLabel": src.short_label,
        "mappingCleared": mapping_cleared,
        "reason": body.reason,
        "analysis": analysis.model_dump(mode="json"),
        "message": (
            "Source mise à jour. Remappez le secteur (branche) pour recalculer l’analyse."
            if mapping_cleared
            else "Source inchangée."
        ),
    }


@dossier_router.put("/dossiers/{dossier_id}/sector-mapping")
def put_sector_mapping(dossier_id: str, body: SectorMappingBody) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    sid = _dossier_source_id(record)
    src = get_source(sid)
    if src is None or not src.supports_va_analysis:
        raise HTTPException(
            status_code=422,
            detail="La source épinglée ne permet pas le mapping de branches VA.",
        )
    branches = branches_for_source(sid)
    if body.hcpSectorCode not in branches:
        raise HTTPException(
            status_code=422,
            detail=f"Code branche inconnu pour la source {src.short_label}.",
        )

    mapped = mapping_from_hcp_code(body.hcpSectorCode, record.sectorRaw or record.sector)
    if mapped is None:
        raise HTTPException(status_code=422, detail="Code branche inconnu")

    updated = dossier_store.update_analyse(
        dossier_id,
        sector=mapped.sector_label,
        benchmark_sector_code=mapped.sector_code,
        sector_normalized=mapped.sector_label,
        sector_source_id=sid,
    )
    current = updated or record
    analysis = sector_analysis_service.analyze(
        record=current,
        result=_result_from_record(current),
        trigger_refresh=False,
    )
    current = _persist_workspace_analysis(
        dossier_id, current, analysis, sector_label=mapped.sector_label
    )

    return {
        "originalActivity": record.sectorRaw or record.sector,
        "automaticMapping": None,
        "finalMapping": mapped.model_dump(),
        "actor": "analyste",
        "reason": body.reason,
        "analysis": analysis.model_dump(mode="json"),
        "branches": branches,
        "hcpBranches": branches,
        "sector": mapped.sector_label,
        "benchmarkSectorCode": mapped.sector_code,
        "sectorSourceId": sid,
        "sourceLabel": src.short_label,
    }
