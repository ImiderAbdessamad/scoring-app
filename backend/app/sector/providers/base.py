from __future__ import annotations

from typing import Protocol

from app.sector.domain import DownloadedDataset, RemoteDatasetMetadata


class SectorDataProvider(Protocol):
    code: str

    async def check_dataset(self, dataset_id: str) -> RemoteDatasetMetadata: ...

    async def download_dataset(self, dataset_id: str) -> DownloadedDataset: ...

    async def list_supported_datasets(self) -> list[RemoteDatasetMetadata]: ...

    async def discover_datasets(self) -> list[RemoteDatasetMetadata]: ...

    async def fetch_metadata(self, dataset_code: str) -> RemoteDatasetMetadata: ...

    async def download_resource(self, dataset: RemoteDatasetMetadata | str) -> DownloadedDataset: ...
