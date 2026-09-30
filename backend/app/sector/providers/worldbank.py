"""Provider Banque mondiale (WDI) — valeur ajoutée du Maroc par grand secteur.

Séries annuelles en monnaie locale (MAD), prix courants (.CN) et prix constants (.KN).
Taxonomie propre (WB_*), jamais mélangée aux branches HCP.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import httpx

from app.core.config import settings
from app.sector.domain import ParsedObservation

WB_API_BASE = "https://api.worldbank.org/v2"
WB_COUNTRY = "MAR"

WORLDBANK_BRANCHES: dict[str, str] = {
    "WB_AGRICULTURE": "Agriculture, sylviculture et pêche",
    "WB_INDUSTRY": "Industrie (y.c. extraction, énergie et construction)",
    "WB_MANUFACTURING": "Industries manufacturières",
    "WB_SERVICES": "Services",
}

# branche -> (indicateur prix courants, indicateur prix constants)
WB_INDICATORS: dict[str, tuple[str, str]] = {
    "WB_AGRICULTURE": ("NV.AGR.TOTL.CN", "NV.AGR.TOTL.KN"),
    "WB_INDUSTRY": ("NV.IND.TOTL.CN", "NV.IND.TOTL.KN"),
    "WB_MANUFACTURING": ("NV.IND.MANF.CN", "NV.IND.MANF.KN"),
    "WB_SERVICES": ("NV.SRV.TOTL.CN", "NV.SRV.TOTL.KN"),
}

WB_DATASET_CURRENT = "wb_va_current"
WB_DATASET_VOLUME = "wb_va_volume"

WB_DATASETS: dict[str, dict] = {
    WB_DATASET_CURRENT: {
        "name": "Banque mondiale — valeur ajoutée par secteur, prix courants (MAD)",
        "price_type": "CURRENT",
        "column": 0,
    },
    WB_DATASET_VOLUME: {
        "name": "Banque mondiale — valeur ajoutée par secteur, prix constants (MAD)",
        "price_type": "CHAINED_VOLUME",
        "column": 1,
    },
}

_MILLION = Decimal(1_000_000)


class WorldBankProvider:
    code = "worldbank"

    async def _fetch_indicator(self, client: httpx.AsyncClient, indicator: str) -> tuple[list[dict], str | None]:
        url = f"{WB_API_BASE}/country/{WB_COUNTRY}/indicator/{indicator}"
        response = await client.get(url, params={"format": "json", "per_page": 200})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            raise ValueError(f"Réponse Banque mondiale inattendue pour {indicator}")
        meta = payload[0] if isinstance(payload[0], dict) else {}
        return payload[1], meta.get("lastupdated")

    async def fetch_dataset(self, dataset_id: str) -> dict:
        """Retourne observations + empreinte (sha256) + date de mise à jour distante."""
        spec = WB_DATASETS.get(dataset_id)
        if spec is None:
            raise ValueError(f"Dataset Banque mondiale inconnu : {dataset_id}")
        column = spec["column"]
        observations: list[ParsedObservation] = []
        raw_by_indicator: dict[str, list] = {}
        last_updated: str | None = None
        timeout = httpx.Timeout(settings.sector_data_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for branch, indicators in WB_INDICATORS.items():
                indicator = indicators[column]
                rows, updated = await self._fetch_indicator(client, indicator)
                last_updated = max(filter(None, [last_updated, updated]), default=None)
                raw_by_indicator[indicator] = [(r.get("date"), r.get("value")) for r in rows]
                for row in rows:
                    value = row.get("value")
                    year = str(row.get("date") or "")
                    if value is None or not year.isdigit():
                        continue
                    observations.append(
                        ParsedObservation(
                            sector_code=branch,
                            sector_label=WORLDBANK_BRANCHES[branch],
                            period_type="ANNUAL",
                            year=int(year),
                            quarter=None,
                            value=Decimal(str(value)) / _MILLION,
                            unit="M MAD",
                            metric="VALUE_ADDED",
                            price_type=spec["price_type"],
                            base_year=None,
                        )
                    )
        fingerprint = hashlib.sha256(
            json.dumps(raw_by_indicator, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return {
            "observations": observations,
            "sha256": fingerprint,
            "last_updated": last_updated,
            "name": spec["name"],
            "price_type": spec["price_type"],
        }


# Rapprochement branche HCP -> grand secteur Banque mondiale (mapping automatique).
HCP_TO_WORLDBANK: dict[str, str] = {
    "HCP_AGRICULTURE": "WB_AGRICULTURE",
    "HCP_PECHE": "WB_AGRICULTURE",
    "HCP_EXTRACTION": "WB_INDUSTRY",
    "HCP_ENERGIE_EAU": "WB_INDUSTRY",
    "HCP_CONSTRUCTION": "WB_INDUSTRY",
    "HCP_MANUFACTURIER": "WB_MANUFACTURING",
    "HCP_ALIMENTAIRE": "WB_MANUFACTURING",
    "HCP_TEXTILE": "WB_MANUFACTURING",
    "HCP_BOIS_PAPIER": "WB_MANUFACTURING",
    "HCP_COKE_RAFFINAGE": "WB_MANUFACTURING",
    "HCP_CHIMIE": "WB_MANUFACTURING",
    "HCP_PHARMA": "WB_MANUFACTURING",
    "HCP_CAOUTCHOUC": "WB_MANUFACTURING",
    "HCP_METALLURGIE": "WB_MANUFACTURING",
    "HCP_ELECTRONIQUE": "WB_MANUFACTURING",
    "HCP_EQUIPEMENTS_ELECTRIQUES": "WB_MANUFACTURING",
    "HCP_MACHINES": "WB_MANUFACTURING",
    "HCP_MATERIEL_TRANSPORT": "WB_MANUFACTURING",
    "HCP_AUTRES_FAB": "WB_MANUFACTURING",
    "HCP_COMMERCE": "WB_SERVICES",
    "HCP_TRANSPORTS": "WB_SERVICES",
    "HCP_HEBERGEMENT": "WB_SERVICES",
    "HCP_INFORMATION": "WB_SERVICES",
    "HCP_FINANCE": "WB_SERVICES",
    "HCP_IMMOBILIER": "WB_SERVICES",
    "HCP_SERVICES_ENTREPRISES": "WB_SERVICES",
    "HCP_ADMIN": "WB_SERVICES",
    "HCP_EDUCATION_SANTE": "WB_SERVICES",
    "HCP_AUTRES_SERVICES": "WB_SERVICES",
}
