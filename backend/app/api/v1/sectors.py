from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.sector.mapping import HCP_BRANCHES, mapping_from_hcp_code
from app.services import dossier_store
from app.services.sector_analysis_service import sector_analysis_service
from app.services.sector_refresh_service import schedule_background_refresh, sector_sync_service

router = APIRouter(prefix="/sectors", tags=["sectors"])
dossier_router = APIRouter(tags=["dossiers"])


class RefreshBody(BaseModel):
    force: bool = False


class SectorMappingBody(BaseModel):
    hcpSectorCode: str
    reason: str = Field(min_length=1)


@router.get("/sources/status")
def sources_status() -> dict:
    payload = sector_sync_service.status_payload()
    datasets = payload.get("datasets") or []
    has_obs = any(int(item.get("observations") or 0) > 0 for item in datasets)
    last_checked = next((item.get("lastCheckedAt") for item in datasets if item.get("lastCheckedAt")), None)
    last_updated = next((item.get("lastUpdatedAt") for item in datasets if item.get("lastUpdatedAt")), None)
    return {
        "sources": [
            {
                "code": "HCP_OPEN_DATA",
                "status": "AVAILABLE" if has_obs else "NO_DATA",
                "lastCheckedAt": last_checked,
                "lastUpdatedAt": last_updated,
                "datasets": datasets,
            }
        ]
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


@dossier_router.get("/dossiers/{dossier_id}/sector-analysis")
async def get_sector_analysis(
    dossier_id: str,
    refresh: Literal["auto", "false", "force"] = Query(default="auto"),
) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if refresh == "force":
        if settings.sector_data_enabled:
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
    return analysis.model_dump(mode="json")


@dossier_router.put("/dossiers/{dossier_id}/sector-mapping")
def put_sector_mapping(dossier_id: str, body: SectorMappingBody) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    mapped = mapping_from_hcp_code(body.hcpSectorCode, record.sectorRaw or record.sector)
    if mapped is None:
        raise HTTPException(status_code=422, detail="Code HCP inconnu")
    updated = dossier_store.update_analyse(
        dossier_id,
        benchmark_sector_code=mapped.sector_code,
        sector_normalized=mapped.sector_label,
    )
    analysis = sector_analysis_service.analyze(
        record=updated or record,
        result=_result_from_record(updated or record),
        trigger_refresh=False,
    )
    return {
        "originalActivity": record.sectorRaw or record.sector,
        "automaticMapping": None,
        "finalMapping": mapped.model_dump(),
        "actor": "analyste",
        "reason": body.reason,
        "analysis": analysis.model_dump(mode="json"),
        "hcpBranches": HCP_BRANCHES,
    }
