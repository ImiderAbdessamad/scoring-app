from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.sector.domain import DownloadedDataset, RemoteDatasetMetadata, RemoteResource
from app.sector.registry import ENABLED_HCP_DATASETS

logger = logging.getLogger(__name__)

ALLOWED_HOSTS = {"data.gov.ma", "www.data.gov.ma"}


class HcpCkanProvider:
    code = "hcp_ckan"

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def _base(self) -> str:
        return settings.hcp_ckan_base_url.rstrip("/")

    def _assert_url(self, url: str) -> None:
        host = (urlparse(url).hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            raise ValueError(f"URL HCP non autorisée : {host}")

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._assert_url(url)
        timeout = settings.sector_data_request_timeout_seconds
        retries = max(1, settings.sector_data_max_retries)
        delays = [1, 2, 4][:retries]
        last_exc: Exception | None = None
        client = self._client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        close = self._client is None
        try:
            for attempt, delay in enumerate([0, *delays]):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    response = await client.request(
                        method,
                        url,
                        headers={"User-Agent": "WafabailSectorSync/1.0 (local; contact=dev)"},
                        **kwargs,
                    )
                except httpx.HTTPError as exc:
                    last_exc = exc
                    logger.warning("sector_sync_failed network dataset_url=%s error=%s", url, exc)
                    continue
                if response.status_code >= 500:
                    last_exc = RuntimeError(f"HTTP {response.status_code}")
                    continue
                response.raise_for_status()
                return response
            raise RuntimeError(str(last_exc) if last_exc else "échec CKAN")
        finally:
            if close:
                await client.aclose()

    def parse_package(self, payload: dict) -> RemoteDatasetMetadata:
        result = payload.get("result") or payload
        resources = []
        for item in result.get("resources") or []:
            resources.append(
                RemoteResource(
                    resource_id=str(item.get("id") or ""),
                    name=str(item.get("name") or ""),
                    format=str(item.get("format") or ""),
                    url=str(item.get("url") or ""),
                    size=item.get("size"),
                    last_modified=item.get("last_modified") or item.get("metadata_modified"),
                    mimetype=item.get("mimetype"),
                )
            )
        org = result.get("organization") or {}
        return RemoteDatasetMetadata(
            dataset_id=str(result.get("name") or result.get("id") or ""),
            title=result.get("title_fr") or result.get("title"),
            notes=result.get("notes_fr") or result.get("notes"),
            metadata_modified=result.get("metadata_modified"),
            metadata_created=result.get("metadata_created"),
            resources=resources,
            organization=org.get("title") or org.get("name") or "HCP",
        )

    def select_xlsx(self, metadata: RemoteDatasetMetadata) -> RemoteResource:
        xlsx = [
            r
            for r in metadata.resources
            if (r.format or "").upper() == "XLSX"
            or (r.name or "").lower().endswith(".xlsx")
            or (r.mimetype or "").endswith("sheet")
        ]
        if not xlsx:
            raise ValueError("Aucune ressource XLSX dans le dataset CKAN")
        return xlsx[0]

    async def check_dataset(self, dataset_id: str) -> RemoteDatasetMetadata:
        url = f"{self._base()}/package_show"
        response = await self._request("GET", url, params={"id": dataset_id})
        payload = response.json()
        if payload.get("success"):
            return self.parse_package(payload)
        search_url = f"{self._base()}/package_search"
        search = await self._request("GET", search_url, params={"q": dataset_id, "rows": 5})
        body = search.json()
        if not body.get("success"):
            raise RuntimeError("package_show success=false")
        results = ((body.get("result") or {}).get("results") or [])
        match = next((item for item in results if item.get("name") == dataset_id or item.get("id") == dataset_id), None)
        if match is None and results:
            match = results[0]
        if match is None:
            raise RuntimeError("package_show success=false")
        return self.parse_package({"success": True, "result": match})

    async def discover_datasets(self) -> list[RemoteDatasetMetadata]:
        return await self.list_supported_datasets()

    async def fetch_metadata(self, dataset_code: str) -> RemoteDatasetMetadata:
        return await self.check_dataset(dataset_code)

    async def download_resource(self, dataset: RemoteDatasetMetadata | str) -> DownloadedDataset:
        dataset_id = dataset if isinstance(dataset, str) else dataset.dataset_id
        return await self.download_dataset(dataset_id)

    async def download_dataset(self, dataset_id: str) -> DownloadedDataset:
        metadata = await self.check_dataset(dataset_id)
        resource = self.select_xlsx(metadata)
        self._assert_url(resource.url)
        response = await self._request("GET", resource.url)
        content = response.content
        if len(content) > settings.sector_data_max_xlsx_bytes:
            raise ValueError("Fichier XLSX trop volumineux")
        if content[:2] != b"PK":
            raise ValueError("Signature XLSX (ZIP) invalide")
        digest = hashlib.sha256(content).hexdigest()
        return DownloadedDataset(
            dataset_id=dataset_id,
            metadata=metadata,
            resource=resource,
            content=content,
            sha256=digest,
            retrieved_at=datetime.now(timezone.utc),
        )

    async def list_supported_datasets(self) -> list[RemoteDatasetMetadata]:
        out: list[RemoteDatasetMetadata] = []
        for definition in ENABLED_HCP_DATASETS.values():
            try:
                out.append(await self.check_dataset(definition.dataset_id))
            except Exception as exc:
                logger.warning("sector_sync_failed dataset_id=%s error=%s", definition.dataset_id, exc)
        return out
