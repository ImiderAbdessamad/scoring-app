"""Alias spec : sector_data_service → repository + sync."""
from app.db.repositories.sector_data_repository import sector_data_repository
from app.services.sector_sync_service import sector_sync_service

__all__ = ["sector_data_repository", "sector_sync_service"]
