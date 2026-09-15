"""Alias spec : sector_refresh_service → SectorSyncService existant."""
from app.services.sector_sync_service import (
    freshness_for,
    schedule_background_refresh,
    sector_sync_loop,
    sector_sync_service,
)


async def refresh_if_stale() -> list[dict]:
    return await sector_sync_service.sync_all()


async def refresh_all(force: bool = False) -> list[dict]:
    return await sector_sync_service.sync_all(force=force)


__all__ = [
    "freshness_for",
    "refresh_all",
    "refresh_if_stale",
    "schedule_background_refresh",
    "sector_sync_loop",
    "sector_sync_service",
]
