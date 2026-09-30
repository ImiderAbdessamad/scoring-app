"""Catalogue des sources de données sectorielles.

Règles anti-conflit
-------------------
1. Chaque source a un ``id`` stable (hcp, apsf, internal) et un namespace de codes
   de branches distinct (ex. HCP_*). On ne réutilise jamais un code d'une source
   dans une autre.
2. La source active pour l'analyse est **épinglée par dossier**
   (``sectorSourceId``). Le défaut global ne s'applique qu'aux dossiers sans pin
   et aux nouveaux dossiers — jamais un écrasement silencieux de tous les dossiers.
3. Changer de source sur un dossier **invalide** le mapping manuel
   (``benchmarkSectorCode``) et force un re-mapping : les taxonomies ne sont pas
   interchangeables.
4. Les observations SQLite restent liées à ``source_id`` via ``sector_datasets`` :
   plusieurs caches peuvent coexister sans se écraser.
5. Une source non implémentée peut être listée / activée en config, mais ne peut
   pas servir d'analyse VA tant que ``implemented`` et la capability
   ``VALUE_ADDED_ANALYSIS`` ne sont pas remplies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sector.domain import SectorMappingResult
from app.sector.mapping import HCP_BRANCHES, mapping_from_hcp_code, resolve_mapping_for_record
from app.sector.providers.worldbank import (
    HCP_TO_WORLDBANK,
    WB_DATASET_CURRENT,
    WB_DATASET_VOLUME,
    WORLDBANK_BRANCHES,
)
from app.sector.registry import HCP_DATASETS


@dataclass(frozen=True)
class SectorSourceDefinition:
    id: str
    code: str
    label: str
    short_label: str
    provider_type: str
    description: str
    capabilities: tuple[str, ...]
    dataset_roles: dict[str, str] = field(default_factory=dict)
    branch_catalog: str = "none"
    implemented: bool = False
    default_enabled: bool = False
    notes: str = ""

    @property
    def supports_va_analysis(self) -> bool:
        return self.implemented and "VALUE_ADDED_ANALYSIS" in self.capabilities


SECTOR_SOURCES: dict[str, SectorSourceDefinition] = {
    "hcp": SectorSourceDefinition(
        id="hcp",
        code="HCP",
        label="Haut Commissariat au Plan (open data)",
        short_label="HCP",
        provider_type="hcp_ckan",
        description=(
            "Comptes nationaux Base 2014 — valeur ajoutée annuelle et trimestrielle "
            "par branche d’activité (data.gov.ma / CKAN)."
        ),
        capabilities=("VALUE_ADDED_ANALYSIS", "OPEN_DATA_SYNC"),
        dataset_roles={
            role: definition.dataset_id
            for role, definition in HCP_DATASETS.items()
            if definition.enabled
        },
        branch_catalog="hcp",
        implemented=True,
        default_enabled=True,
        notes="Source par défaut. Mapping branches HCP_*.",
    ),
    "worldbank": SectorSourceDefinition(
        id="worldbank",
        code="WORLDBANK",
        label="Banque mondiale — comptes nationaux (WDI)",
        short_label="Banque mondiale",
        provider_type="worldbank_api",
        description=(
            "Valeur ajoutée du Maroc par grand secteur (agriculture, industrie, "
            "manufacturier, services), prix courants et constants, séries annuelles."
        ),
        capabilities=("VALUE_ADDED_ANALYSIS", "OPEN_DATA_SYNC"),
        dataset_roles={
            "annual_va_current": WB_DATASET_CURRENT,
            "annual_va_volume": WB_DATASET_VOLUME,
        },
        branch_catalog="worldbank",
        implemented=True,
        default_enabled=True,
        notes="Granularité plus large que HCP (4 grands secteurs). Mapping branches WB_*.",
    ),
    "apsf": SectorSourceDefinition(
        id="apsf",
        code="APSF",
        label="APSF — marché du crédit-bail",
        short_label="APSF",
        provider_type="apsf",
        description=(
            "Indicateurs de contexte marché leasing (APSF). "
            "Métrique distincte de la VA HCP — non interchangeable."
        ),
        capabilities=("LEASING_MARKET_CONTEXT",),
        dataset_roles={},
        branch_catalog="none",
        implemented=False,
        default_enabled=False,
        notes="Préparé pour une future intégration. Ne remplace pas l’analyse VA.",
    ),
    "internal": SectorSourceDefinition(
        id="internal",
        code="INTERNAL",
        label="Portefeuille interne Wafabail",
        short_label="Interne",
        provider_type="internal_portfolio",
        description=(
            "Benchmarks issus du portefeuille interne (médianes scoring). "
            "Ne fournit pas encore les séries VA pour l’onglet sectoriel."
        ),
        capabilities=("PORTFOLIO_BENCHMARK",),
        dataset_roles={},
        branch_catalog="none",
        implemented=False,
        default_enabled=False,
        notes="Stub. Utilisé côté scoring / comparables, pas comme source VA.",
    ),
}

DEFAULT_SOURCE_ID = "hcp"


def get_source(source_id: str | None) -> SectorSourceDefinition | None:
    if not source_id:
        return None
    return SECTOR_SOURCES.get(str(source_id).strip().lower())


def resolve_source_id(raw: str | None, fallback: str = DEFAULT_SOURCE_ID) -> str:
    key = (raw or "").strip().lower()
    if key in SECTOR_SOURCES:
        return key
    # Accepte aussi les codes legacy (HCP, hcp_open_data, hcp_ckan).
    aliases = {
        "hcp_open_data": "hcp",
        "hcp_ckan": "hcp",
        "haut commissariat au plan": "hcp",
    }
    if key in aliases:
        return aliases[key]
    for src in SECTOR_SOURCES.values():
        if key == src.code.lower() or key == src.provider_type.lower():
            return src.id
    return fallback if fallback in SECTOR_SOURCES else DEFAULT_SOURCE_ID


def branches_for_source(source_id: str) -> dict[str, str]:
    src = get_source(resolve_source_id(source_id))
    if src is None:
        return {}
    if src.branch_catalog == "hcp":
        return dict(HCP_BRANCHES)
    if src.branch_catalog == "worldbank":
        return dict(WORLDBANK_BRANCHES)
    return {}


def dataset_id_for_role(source_id: str, role: str) -> str | None:
    src = get_source(resolve_source_id(source_id))
    if src is None:
        return None
    return src.dataset_roles.get(role)


def mapping_from_code(source_id: str, code: str, raw: str | None = None) -> SectorMappingResult | None:
    """Mapping manuel validé, uniquement si le code appartient à la taxonomie de la source."""
    sid = resolve_source_id(source_id)
    branches = branches_for_source(sid)
    if code not in branches:
        return None
    if sid == "hcp":
        return mapping_from_hcp_code(code, raw)
    return SectorMappingResult(
        raw_activity=raw,
        sector_code=code,
        sector_label=branches[code],
        confidence=1.0,
        status="MATCHED",
        mapping_method="MANUAL",
        validated=True,
    )


def resolve_mapping_for_source(source_id: str, record, identity=None) -> SectorMappingResult:
    """Mapping de l'activité du dossier vers la taxonomie de la source active."""
    sid = resolve_source_id(source_id)
    raw = getattr(record, "sectorRaw", None) or getattr(record, "sector", None)
    src = get_source(sid)
    if src is None or src.branch_catalog == "none":
        return SectorMappingResult(raw_activity=raw, status="UNMATCHED", confidence=0.0)

    manual_code = getattr(record, "benchmarkSectorCode", None)
    if manual_code:
        manual = mapping_from_code(sid, str(manual_code), raw)
        if manual is not None:
            return manual

    if src.branch_catalog == "hcp":
        return resolve_mapping_for_record(record, identity)

    # Autres taxonomies : on passe par le mapping HCP (activité -> branche fine)
    # puis on agrège vers le grand secteur de la source.
    hcp_mapping = resolve_mapping_for_record(record, identity)
    if src.branch_catalog == "worldbank" and hcp_mapping.sector_code in HCP_TO_WORLDBANK:
        code = HCP_TO_WORLDBANK[hcp_mapping.sector_code]
        return SectorMappingResult(
            raw_activity=hcp_mapping.raw_activity or raw,
            normalized_activity=hcp_mapping.normalized_activity,
            sector_code=code,
            sector_label=WORLDBANK_BRANCHES[code],
            confidence=min(hcp_mapping.confidence or 0.0, 0.9),
            status="MATCHED" if hcp_mapping.status == "MATCHED" else "REVIEW_REQUIRED",
            mapping_method="SUGGESTED",
            validated=False,
        )
    return SectorMappingResult(
        raw_activity=hcp_mapping.raw_activity or raw,
        normalized_activity=hcp_mapping.normalized_activity,
        status="REVIEW_REQUIRED" if hcp_mapping.status == "REVIEW_REQUIRED" else "UNMATCHED",
        confidence=0.0,
    )
