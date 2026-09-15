"""Provider APSF — marché du crédit-bail, distinct de la VA HCP. Future / disabled."""

from __future__ import annotations


class ApsfProvider:
    code = "apsf"
    enabled = False
    metric = "LEASING_MARKET_CONTEXT"

    async def check_dataset(self, dataset_id: str):
        raise NotImplementedError("APSF non implémenté")

    async def download_dataset(self, dataset_id: str):
        raise NotImplementedError("APSF non implémenté")

    async def list_supported_datasets(self):
        return []
