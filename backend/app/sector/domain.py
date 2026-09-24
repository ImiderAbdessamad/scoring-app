from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

MetricKind = Literal["VALUE_ADDED", "GDP", "TURNOVER", "PRODUCTION", "EMPLOYMENT", "INVESTMENT", "LEASING_MARKET_CONTEXT"]
Frequency = Literal["ANNUAL", "QUARTERLY"]
PriceType = Literal["CURRENT", "CHAINED_VOLUME"]
SeasonalAdjustment = Literal["NONE", "CVS"]
PeriodType = Literal["ANNUAL", "QUARTERLY"]
SyncStatus = Literal["STARTED", "UNCHANGED", "UPDATED", "FAILED", "FAILED_SCHEMA"]
MappingMethod = Literal["EXACT", "ALIAS", "KEYWORD", "MANUAL", "SUGGESTED"]
MappingStatus = Literal["MATCHED", "REVIEW_REQUIRED", "UNMATCHED"]
SectorAnalysisStatus = Literal[
    "AVAILABLE",
    "PARTIAL",
    "UNAVAILABLE",
    "MAPPING_REVIEW_REQUIRED",
    "UNMAPPED",
    "NO_DATA",
    "STALE",
    "ERROR",
]
FreshnessStatus = Literal["FRESH", "STALE", "VERY_STALE", "UNAVAILABLE", "REFRESHING", "ERROR"]
SectorScoringStatus = Literal["NOT_CALIBRATED", "AVAILABLE", "INSUFFICIENT_DATA"]
MomentumStatus = Literal["ACCELERATING", "STABLE", "SLOWING", "CONTRACTING"]


class SectorDatasetDefinition(BaseModel):
    key: str
    dataset_id: str
    name: str
    metric: MetricKind
    frequency: Frequency
    price_type: PriceType
    base_year: int | None = 2014
    seasonal_adjustment: SeasonalAdjustment = "NONE"
    unit_hint: str | None = None
    enabled: bool = True
    notes: str | None = None


class RemoteResource(BaseModel):
    resource_id: str
    name: str
    format: str | None = None
    url: str
    size: int | None = None
    last_modified: str | None = None
    mimetype: str | None = None


class RemoteDatasetMetadata(BaseModel):
    dataset_id: str
    title: str | None = None
    notes: str | None = None
    metadata_modified: str | None = None
    metadata_created: str | None = None
    resources: list[RemoteResource] = Field(default_factory=list)
    organization: str | None = None


class DownloadedDataset(BaseModel):
    dataset_id: str
    metadata: RemoteDatasetMetadata
    resource: RemoteResource
    content: bytes
    sha256: str
    retrieved_at: datetime


class ParsedObservation(BaseModel):
    sector_code: str
    sector_label: str
    period_type: PeriodType
    year: int
    quarter: int | None = None
    value: Decimal
    unit: str
    metric: MetricKind
    price_type: PriceType
    base_year: int | None = None


class ParsedWorkbook(BaseModel):
    observations: list[ParsedObservation]
    unit: str
    header_labels: list[str]
    title: str | None = None
    rows_read: int = 0


class SectorMappingResult(BaseModel):
    raw_activity: str | None = None
    normalized_activity: str | None = None
    sector_code: str | None = None
    sector_label: str | None = None
    confidence: float = 0.0
    status: MappingStatus = "UNMATCHED"
    mapping_method: MappingMethod | None = None
    validated: bool = False


class SectorSeriesPoint(BaseModel):
    year: int
    quarter: int | None = None
    value: float | None = None
    unit: str = "M MAD"
    growthYoy: float | None = None


class CompanyAnnualPoint(BaseModel):
    year: int
    va: float | None = None
    ca: float | None = None
    ebe: float | None = None
    resultatExploitation: float | None = None
    resultatNet: float | None = None
    caf: float | None = None
    unit: str = "MAD"
    vaUsable: bool = False
    caUsable: bool = False


class NormalizedSectorPoint(BaseModel):
    year: int
    companyIndex: float | None = None
    sectorIndex: float | None = None


class GrowthComparisonPoint(BaseModel):
    year: int
    companyGrowth: float | None = None
    sectorGrowth: float | None = None
    gapPp: float | None = None
    companyAvailable: bool = False


class SectorComparableIndicator(BaseModel):
    code: str
    label: str
    companyValue: float | None = None
    sectorValue: float | None = None
    unit: str
    gap: float | None = None
    comparable: bool
    reason: str | None = None
    source: str | None = None


class SectorInsight(BaseModel):
    code: str
    severity: Literal["INFO", "WARNING"] = "INFO"
    text: str


class SectorMomentum(BaseModel):
    trend: MomentumStatus | Literal["EXPANDING_ACCELERATING", "EXPANDING_SLOWING", "INSUFFICIENT_DATA"] | None = None
    latestRealGrowth: float | None = None
    previousRealGrowth: float | None = None
    realGrowthAcceleration: float | None = None


class CompanySectorMetrics(BaseModel):
    companyVaGrowth: float | None = None
    companyCaGrowth: float | None = None
    vaOverCa: float | None = None
    ebeOverVa: float | None = None
    operatingMargin: float | None = None
    netMargin: float | None = None
    cafMargin: float | None = None


class SectorHeadline(BaseModel):
    latestSectorVa: float | None = None
    latestYear: int | None = None
    latestUnit: str = "M MAD"
    latestQuarterlyPeriod: str | None = None
    nominalGrowthYoy: float | None = None
    realGrowthYoy: float | None = None
    cagr3y: float | None = None


class SectorDataFreshness(BaseModel):
    status: FreshnessStatus = "UNAVAILABLE"
    lastSyncAt: str | None = None
    lastCheckedAt: str | None = None
    latestObservationPeriod: str | None = None
    source: str = "HCP"
    datasetVersions: list[dict[str, Any]] = Field(default_factory=list)
    cached: bool = False


class SectorScoringInfo(BaseModel):
    status: SectorScoringStatus = "NOT_CALIBRATED"
    includedInFinalScore: bool = False
    score: float | None = None
    note: str = "Non intégrée au score — politique sectorielle non calibrée."


class SectorInfo(BaseModel):
    rawActivity: str | None = None
    code: str | None = None
    label: str | None = None
    mappingConfidence: float | None = None
    mappingStatus: MappingStatus = "UNMATCHED"
    mappingType: MappingMethod | None = None
    validated: bool = False
    sourceId: str | None = None
    sourceLabel: str | None = None
    sourceCode: str | None = None


class SectorAnalysisResult(BaseModel):
    status: SectorAnalysisStatus = "UNAVAILABLE"
    sector: SectorInfo = Field(default_factory=SectorInfo)
    dataFreshness: SectorDataFreshness = Field(default_factory=SectorDataFreshness)
    headline: SectorHeadline = Field(default_factory=SectorHeadline)
    sectorAnnualCurrent: list[SectorSeriesPoint] = Field(default_factory=list)
    sectorAnnualReal: list[SectorSeriesPoint] = Field(default_factory=list)
    sectorQuarterly: list[SectorSeriesPoint] = Field(default_factory=list)
    companyAnnual: list[CompanyAnnualPoint] = Field(default_factory=list)
    normalizedComparison: list[NormalizedSectorPoint] = Field(default_factory=list)
    growthComparison: list[GrowthComparisonPoint] = Field(default_factory=list)
    comparableIndicators: list[SectorComparableIndicator] = Field(default_factory=list)
    insights: list[SectorInsight] = Field(default_factory=list)
    momentum: SectorMomentum = Field(default_factory=SectorMomentum)
    companyMetrics: CompanySectorMetrics = Field(default_factory=CompanySectorMetrics)
    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    scoring: SectorScoringInfo = Field(default_factory=SectorScoringInfo)
    realGrowthNote: str = (
        "La croissance réelle sectorielle est affichée comme indicateur de "
        "conjoncture et n'est pas directement soustraite à la croissance nominale "
        "de l'entreprise."
    )


class InternalPortfolioSectorProvider:
    enabled = False

    def analyze(self, *_args, **_kwargs):
        raise NotImplementedError("WAFABAIL_INTERNAL désactivé — pas de taux de défaut inventé.")
