from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.db.repositories.sector_data_repository import sector_data_repository
from app.sector.providers.hcp_ckan import HcpCkanProvider
from app.sector.providers.hcp_parser import HcpWorkbookParser, SchemaValidationError
from app.sector.registry import ENABLED_HCP_DATASETS, definition_by_dataset_id

logger = logging.getLogger(__name__)

_refresh_lock = asyncio.Lock()


class SectorSyncService:
    def __init__(self, provider: HcpCkanProvider | None = None, parser: HcpWorkbookParser | None = None) -> None:
        self.provider = provider or HcpCkanProvider()
        self.parser = parser or HcpWorkbookParser()

    async def sync_dataset(self, dataset_id: str, force: bool = False) -> dict:
        definition = definition_by_dataset_id(dataset_id)
        if definition is None or not definition.enabled:
            return {"status": "FAILED", "error": "dataset inconnu ou désactivé", "dataset_id": dataset_id}
        source = sector_data_repository.ensure_hcp_source()
        dataset = sector_data_repository.get_or_create_dataset(
            source_id=source.id,
            external_dataset_id=definition.dataset_id,
            name=definition.name,
            metric=definition.metric,
            frequency=definition.frequency,
            price_type=definition.price_type,
            base_year=definition.base_year,
            unit=definition.unit_hint or "M MAD",
        )
        run = sector_data_repository.add_sync_run(
            dataset_id=dataset.id,
            external_dataset_id=dataset_id,
            status="STARTED",
            previous_hash=dataset.resource_sha256,
        )
        logger.info("sector_sync_start dataset_id=%s", dataset_id)
        try:
            metadata = await self.provider.check_dataset(dataset_id)
            resource = self.provider.select_xlsx(metadata)
            sector_data_repository.touch_checked(
                dataset.id,
                resource_id=resource.resource_id,
                resource_name=resource.name,
                source_created_at=metadata.metadata_created,
                source_updated_at=metadata.metadata_modified,
            )
            fingerprint = f"{resource.resource_id}:{resource.last_modified}:{resource.size}"
            unchanged = bool(dataset.resource_sha256) and (
                dataset.source_updated_at == metadata.metadata_modified
                and dataset.resource_id == resource.resource_id
            )
            downloaded = None
            if unchanged and not force:
                logger.info(
                    "sector_sync_unchanged dataset_id=%s resource_id=%s hash=%s",
                    dataset_id,
                    resource.resource_id,
                    dataset.resource_sha256,
                )
                sector_data_repository.finish_sync_run(
                    run.id,
                    status="UNCHANGED",
                    remote_updated_at=metadata.metadata_modified,
                    new_hash=dataset.resource_sha256,
                    rows_read=0,
                )
                return {"status": "UNCHANGED", "dataset_id": dataset_id, "hash": dataset.resource_sha256}

            downloaded = await self.provider.download_dataset(dataset_id)
            if dataset.resource_sha256 and downloaded.sha256 == dataset.resource_sha256 and not force:
                logger.info(
                    "sector_sync_unchanged dataset_id=%s resource_id=%s hash=%s",
                    dataset_id,
                    downloaded.resource.resource_id,
                    downloaded.sha256,
                )
                sector_data_repository.touch_checked(dataset.id, last_successful_sync_at=datetime.utcnow())
                sector_data_repository.finish_sync_run(
                    run.id,
                    status="UNCHANGED",
                    remote_updated_at=metadata.metadata_modified,
                    new_hash=downloaded.sha256,
                )
                return {"status": "UNCHANGED", "dataset_id": dataset_id, "hash": downloaded.sha256}

            parsed = self.parser.parse(downloaded.content, definition)
            object_key = None
            if settings.sector_data_store_raw_files:
                from app.services import minio_storage

                object_key = f"external-data/hcp/{dataset_id}/{downloaded.sha256}.xlsx"
                minio_storage.put_bytes(
                    object_key,
                    downloaded.content,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            inserted, updated = sector_data_repository.replace_observations(
                dataset_pk=dataset.id,
                observations=parsed.observations,
                resource_sha256=downloaded.sha256,
                source_version=fingerprint,
            )
            sector_data_repository.touch_checked(
                dataset.id,
                resource_id=downloaded.resource.resource_id,
                resource_name=downloaded.resource.name,
                resource_sha256=downloaded.sha256,
                resource_size=len(downloaded.content),
                object_key=object_key,
                source_updated_at=metadata.metadata_modified,
                last_downloaded_at=datetime.utcnow(),
                last_successful_sync_at=datetime.utcnow(),
                unit=parsed.unit,
            )
            logger.info(
                "sector_sync_updated dataset_id=%s resource_id=%s hash=%s rows=%s inserted=%s updated=%s",
                dataset_id,
                downloaded.resource.resource_id,
                downloaded.sha256,
                parsed.rows_read,
                inserted,
                updated,
            )
            sector_data_repository.finish_sync_run(
                run.id,
                status="UPDATED",
                remote_updated_at=metadata.metadata_modified,
                new_hash=downloaded.sha256,
                rows_read=parsed.rows_read,
                rows_inserted=inserted,
                rows_updated=updated,
            )
            return {
                "status": "UPDATED",
                "dataset_id": dataset_id,
                "hash": downloaded.sha256,
                "rows_read": parsed.rows_read,
                "rows_inserted": inserted,
                "rows_updated": updated,
            }
        except SchemaValidationError as exc:
            logger.warning("sector_sync_failed dataset_id=%s error=%s", dataset_id, exc)
            sector_data_repository.finish_sync_run(
                run.id, status="FAILED_SCHEMA", error=str(exc)
            )
            return {"status": "FAILED_SCHEMA", "dataset_id": dataset_id, "error": str(exc)}
        except Exception as exc:
            logger.warning("sector_sync_failed dataset_id=%s error=%s", dataset_id, exc)
            sector_data_repository.finish_sync_run(run.id, status="FAILED", error=str(exc))
            return {"status": "FAILED", "dataset_id": dataset_id, "error": str(exc)}

    async def sync_all(self, force: bool = False) -> list[dict]:
        results = []
        for definition in ENABLED_HCP_DATASETS.values():
            results.append(await self.sync_dataset(definition.dataset_id, force=force))
        return results

    def status_payload(self) -> dict:
        datasets = []
        for definition in ENABLED_HCP_DATASETS.values():
            row = sector_data_repository.get_dataset_by_external(definition.dataset_id)
            count = sector_data_repository.observation_count(row.id) if row else 0
            freshness = freshness_for(row)
            datasets.append(
                {
                    "id": definition.dataset_id,
                    "name": definition.name,
                    "metric": definition.metric,
                    "status": freshness,
                    "lastCheckedAt": row.last_checked_at.isoformat() if row and row.last_checked_at else None,
                    "lastUpdatedAt": row.last_successful_sync_at.isoformat()
                    if row and row.last_successful_sync_at
                    else None,
                    "observations": count,
                    "sha256": row.resource_sha256 if row else None,
                }
            )
        return {"provider": "HCP", "datasets": datasets}


def freshness_for(row) -> str:
    if row is None or not row.resource_sha256:
        return "UNAVAILABLE"
    stamp = row.last_successful_sync_at or row.last_checked_at
    if stamp is None:
        return "STALE"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - stamp
    hours = settings.sector_metadata_ttl_hours
    if age <= timedelta(hours=hours):
        return "FRESH"
    if age <= timedelta(hours=max(hours, settings.sector_data_refresh_hours) * 3):
        return "STALE"
    return "VERY_STALE"


sector_sync_service = SectorSyncService()


async def sector_sync_loop() -> None:
    if not settings.sector_data_enabled or not settings.sector_data_auto_sync:
        return
    interval = max(1, settings.sector_data_refresh_hours) * 3600
    await asyncio.sleep(2)
    while True:
        try:
            async with _refresh_lock:
                await sector_sync_service.sync_all()
        except Exception as exc:
            logger.warning("sector_sync_failed loop error=%s", exc)
        await asyncio.sleep(interval)


def schedule_background_refresh() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run():
        async with _refresh_lock:
            await sector_sync_service.sync_all()

    loop.create_task(_run())
