from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.services.sector_analysis_service import sector_analysis_service
from app.services.sector_sync_service import schedule_background_refresh, sector_sync_service
from app.services import dossier_store

router = APIRouter(prefix="/sector-data", tags=["sector-data"])


@router.get("/status")
def sector_data_status() -> dict:
    return sector_sync_service.status_payload()


@router.post("/sync")
async def sector_data_sync_all() -> dict:
    if not settings.sector_data_enabled:
        raise HTTPException(status_code=503, detail="Données sectorielles désactivées")
    results = await sector_sync_service.sync_all()
    return {"results": results}


@router.post("/sync/{dataset_id}")
async def sector_data_sync_one(dataset_id: str) -> dict:
    if not settings.sector_data_enabled:
        raise HTTPException(status_code=503, detail="Données sectorielles désactivées")
    return await sector_sync_service.sync_dataset(dataset_id)


dossier_sector_router = APIRouter(tags=["dossiers"])


@dossier_sector_router.get("/dossiers/{dossier_id}/sector-analysis")
def get_sector_analysis(dossier_id: str, refresh: bool = Query(default=False)) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    result = None
    from app.schemas.analyse import ScoringAnalysisResult

    raw = (record.analyse or {}).get("_result")
    if isinstance(raw, dict):
        try:
            result = ScoringAnalysisResult.model_validate(raw)
        except Exception:
            result = None
    analysis = sector_analysis_service.analyze(
        record=record,
        result=result,
        trigger_refresh=refresh,
    )
    return json_ready(analysis)


@dossier_sector_router.post("/dossiers/{dossier_id}/sector-analysis/refresh")
def refresh_sector_analysis(dossier_id: str) -> dict:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    schedule_background_refresh()
    analysis = sector_analysis_service.analyze(record=record, trigger_refresh=True)
    return json_ready(analysis)


def json_ready(model) -> dict:
    return model.model_dump(mode="json")
