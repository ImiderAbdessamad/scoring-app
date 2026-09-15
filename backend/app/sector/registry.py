from __future__ import annotations

from app.sector.domain import SectorDatasetDefinition

HCP_DATASETS: dict[str, SectorDatasetDefinition] = {
    "annual_va_current": SectorDatasetDefinition(
        key="annual_va_current",
        dataset_id="data_12_29",
        name="Valeurs ajoutées à prix courants — annuelle — Base 2014",
        metric="VALUE_ADDED",
        frequency="ANNUAL",
        price_type="CURRENT",
        base_year=2014,
        unit_hint="M MAD",
        enabled=True,
    ),
    "annual_va_volume": SectorDatasetDefinition(
        key="annual_va_volume",
        dataset_id="data_12_28",
        name="Valeurs ajoutées en volume aux prix de l’année précédente chaînés — annuelle — Base 2014",
        metric="VALUE_ADDED",
        frequency="ANNUAL",
        price_type="CHAINED_VOLUME",
        base_year=2014,
        unit_hint="M MAD",
        enabled=True,
    ),
    "quarterly_va_current": SectorDatasetDefinition(
        key="quarterly_va_current",
        dataset_id="data_12_41",
        name="Valeurs ajoutées CVS aux prix courants par branche — trimestrielle — Base 2014",
        metric="VALUE_ADDED",
        frequency="QUARTERLY",
        price_type="CURRENT",
        seasonal_adjustment="CVS",
        base_year=2014,
        enabled=True,
    ),
    "quarterly_va_volume": SectorDatasetDefinition(
        key="quarterly_va_volume",
        dataset_id="data_12_40",
        name="Valeurs ajoutées CVS en volume / prix chaînés par branche — trimestrielle — Base 2014",
        metric="VALUE_ADDED",
        frequency="QUARTERLY",
        price_type="CHAINED_VOLUME",
        seasonal_adjustment="CVS",
        base_year=2014,
        enabled=True,
    ),
    "annual_gdp_current": SectorDatasetDefinition(
        key="annual_gdp_current",
        dataset_id="data_12_26",
        name="PIB par secteur d’activité à prix courants — annuelle — Base 2014",
        metric="GDP",
        frequency="ANNUAL",
        price_type="CURRENT",
        base_year=2014,
        enabled=False,
        notes="Ne jamais mélanger PIB et VA. Dataset enregistré, non utilisé dans l’analyse VA.",
    ),
}

ENABLED_HCP_DATASETS = {k: v for k, v in HCP_DATASETS.items() if v.enabled}


def definition_by_dataset_id(dataset_id: str) -> SectorDatasetDefinition | None:
    for item in HCP_DATASETS.values():
        if item.dataset_id == dataset_id:
            return item
    return None
