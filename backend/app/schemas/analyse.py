"""Schémas jobs d'analyse scoring — extracteur V6 + ratios + workspace UI."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled", "interrupted"]

RCC_ELEMENTS: list[tuple[int, str, str, str]] = [
    (1, "ACTIFS_IMMOBILISES", "Actifs immobilisés", "Bilan Actif"),
    (2, "TOTAL_BILAN", "Total bilan", "Bilan Actif"),
    (3, "CHIFFRE_AFFAIRES", "Chiffre d'affaires", "CPC"),
    (4, "CA_EXPORT", "Chiffre d'affaires à l'export", "CPC"),
    (5, "DETTES_BANCAIRES_MLT", "Dettes bancaires MLT", "Bilan Passif"),
    (6, "DETTES_BANCAIRES_CT", "Dettes bancaires CT", "Bilan Passif"),
    (7, "PASSIF_CIRCULANT", "Passif circulant", "Bilan Passif"),
    (8, "DETTES_FOURNISSEURS", "Dettes fournisseurs", "Bilan Passif"),
    (9, "COMPTE_COURANT_ASSOCIES", "Compte courant d'associés", "Bilan"),
    (10, "TRESORERIE_PASSIF", "Trésorerie passif", "Bilan Passif"),
    (11, "ACTIF_CIRCULANT", "Actif circulant", "Bilan Actif"),
    (12, "CREANCES_CLIENTS", "Créances clients", "Bilan Actif"),
    (13, "TRESORERIE_ACTIF", "Trésorerie actif", "Bilan Actif"),
    (14, "CAISSE", "Caisse actif", "Bilan Actif"),
    (15, "ACHATS_REVENDUS", "Achats revendus", "CPC"),
    (16, "ACHATS_CONSOMMES", "Achats consommés", "CPC"),
    (17, "AUTRES_CHARGES_EXTERNES", "Autres charges externes", "CPC"),
    (18, "CHARGES_INTERETS", "Charges d'intérêts", "CPC"),
    (19, "RESULTAT_NET", "Résultat net", "CPC"),
    (20, "TYPE_RESULTAT", "Type de résultat", "Dérivé"),
]

SCORING_EXTRA_ELEMENTS: list[tuple[int, str, str, str]] = [
    (21, "FONDS_PROPRES", "Fonds propres", "Bilan Passif"),
    (22, "STOCKS", "Stocks", "Bilan Actif"),
    (23, "RESULTAT_EXPLOITATION", "Résultat d'exploitation", "CPC"),
    (24, "DOTATIONS_EXPLOITATION", "Dotations d'exploitation", "CPC"),
    (25, "DETTES_FINANCIERES", "Dettes financières (MLT+CT)", "Dérivé"),
    (26, "ENDETTEMENT_TERME", "Endettement à terme", "Dérivé"),
    (27, "TRESORERIE_NETTE", "Trésorerie nette", "Dérivé"),
    (28, "FDR", "Fonds de roulement", "Dérivé"),
    (29, "BFR", "Besoin en fonds de roulement", "Dérivé"),
    (30, "CAF", "Capacité d'autofinancement", "Dérivé"),
    (31, "VALEUR_AJOUTEE", "Valeur ajoutée", "ESG"),
    (32, "EBE", "Excédent brut d'exploitation", "ESG"),
]


class IdentityInfo(BaseModel):
    identifiant_fiscal: str | None = None
    ice: str | None = None
    raison_sociale: str | None = None
    taxe_professionnelle: str | None = None
    ville: str | None = None
    adresse: str | None = None
    activite: str | None = None
    secteur: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    declaration_date: str | None = None
    declaration_time: str | None = None
    reference: str | None = None


class CompanyInfo(BaseModel):
    raison_sociale: str | None = None
    identifiant_fiscal: str | None = None
    ice: str | None = None
    rc: str | None = None
    taxe_professionnelle: str | None = None
    adresse: str | None = None
    ville: str | None = None
    activite: str | None = None
    secteur: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    declaration_date: str | None = None
    declaration_time: str | None = None
    reference: str | None = None


class IaClientMatch(BaseModel):
    """Client Wafabail renvoyé par GET /ia-clients/search."""

    ice: str | None = None
    tiers: str | None = None
    rc: str | None = None
    identifiant_fiscal: str | None = None
    raison_sociale: str | None = None


class ClientLookup(BaseModel):
    """Enrichissement post-OCR : rapprochement du n° tiers via l'API IA."""

    status: Literal["MATCHED", "MULTIPLE", "NOT_FOUND", "SKIPPED", "ERROR"] = "SKIPPED"
    query: dict[str, str] = Field(default_factory=dict)
    matches: list[IaClientMatch] = Field(default_factory=list)
    primary: IaClientMatch | None = None
    message: str | None = None


class ExerciseInfo(BaseModel):
    debut: str | None = None
    fin: str | None = None
    label: str | None = None


class FinancialPageAudit(BaseModel):
    page_number: int
    detected_type: str
    orientation: int = 0
    extraction_status: str = "empty"
    extraction_strategy: str = ""
    candidates_count: int = 0
    error: str | None = None


class DocumentSummary(BaseModel):
    filename: str
    pages_total: int
    pages_processed: int
    pages_skipped: int
    pages_failed: int
    document_type: str = "LIASSE_FISCALE"
    company: CompanyInfo = Field(default_factory=CompanyInfo)
    identity: IdentityInfo = Field(default_factory=IdentityInfo)
    exercise: ExerciseInfo = Field(default_factory=ExerciseInfo)


class ExtractionSummary(BaseModel):
    model: str
    page_audit: list[FinancialPageAudit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


FieldQualityStatus = Literal[
    "confirmed",
    "cross_checked",
    "validated_by_equation",
    "validated_by_repeated_source",
    "ambiguous",
    "suspect",
    "conflicting",
    "missing",
    "blank_on_form",
    "derived",
]

ReadinessStatus = Literal["ready", "review_required", "insufficient_data", "blocked"]
ControlPeriod = Literal["current", "previous"]
ControlStatus = Literal["passed", "failed", "not_evaluable"]

_USABLE_STATUSES = {
    "confirmed",
    "cross_checked",
    "validated_by_equation",
    "validated_by_repeated_source",
    "derived",
}


class FieldEvidence(BaseModel):
    page_number: Optional[int] = None
    raw_label: Optional[str] = None
    raw_value: Optional[str] = None
    column_name: Optional[str] = None
    page_type: Optional[str] = None
    confidence: Optional[float] = None
    source_excerpt: Optional[str] = None
    period: Optional[str] = None


class PeriodFieldValue(BaseModel):
    observed_value: Optional[float] = None
    usable_value: Optional[float] = None
    status: FieldQualityStatus = "missing"
    usable: bool = False
    confidence: Optional[float] = None
    period_status: Optional[str] = None
    accounting_status: Optional[str] = None
    evidence: list[FieldEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExtractedField(BaseModel):
    number: int
    code: str
    label: str
    source: str
    current: PeriodFieldValue = Field(default_factory=PeriodFieldValue)
    previous: PeriodFieldValue | None = None
    unit: str = "MAD"
    note: Optional[str] = None
    value: Optional[float] = None
    value_n1: Optional[float] = None
    status: str = "missing"
    confidence: float = 0.0
    evidence: list[FieldEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def _project_legacy_and_periods(self) -> "ExtractedField":
        if (
            self.current.status == "missing"
            and self.current.observed_value is None
            and self.current.usable_value is None
            and (self.value is not None or self.status not in {"missing", ""})
        ):
            status: FieldQualityStatus
            if self.status in {
                "confirmed",
                "cross_checked",
                "validated_by_equation",
                "validated_by_repeated_source",
                "ambiguous",
                "suspect",
                "conflicting",
                "missing",
                "blank_on_form",
                "derived",
            }:
                status = self.status  # type: ignore[assignment]
            else:
                status = "confirmed"
            usable = status in _USABLE_STATUSES and self.value is not None
            self.current = PeriodFieldValue(
                observed_value=self.value,
                usable_value=self.value if usable else None,
                status=status,
                usable=usable,
                confidence=self.confidence,
                evidence=list(self.evidence),
            )
        if self.previous is None and self.value_n1 is not None:
            prev_usable = self.current.usable and self.current.status in _USABLE_STATUSES
            self.previous = PeriodFieldValue(
                observed_value=self.value_n1,
                usable_value=self.value_n1 if prev_usable else None,
                status=self.current.status if prev_usable else "ambiguous",
                usable=bool(prev_usable),
                confidence=self.confidence,
            )
        self.value = self.current.observed_value
        self.status = self.current.status
        self.confidence = float(self.current.confidence or 0.0)
        if self.previous is not None:
            self.value_n1 = self.previous.observed_value
        if self.current.evidence and not self.evidence:
            self.evidence = list(self.current.evidence)
        return self


class AccountingControlView(BaseModel):
    code: str
    label: str
    period: ControlPeriod | None = None
    period_label: Optional[str] = None
    status: ControlStatus = "not_evaluable"
    expected: Optional[float] = None
    observed: Optional[float] = None
    difference: Optional[float] = None
    tolerance: Optional[float] = None
    affected_fields: list[str] = Field(default_factory=list)
    message: str = ""
    severity: Literal["CRITICAL", "WARNING", "INFO"] = "WARNING"
    affects_scoring: bool = False


class ExtractionQuality(BaseModel):
    observed_current_count: int = 0
    usable_current_count: int = 0
    observed_previous_count: int = 0
    usable_previous_count: int = 0
    suspect_count: int = 0
    conflict_count: int = 0
    cross_checked_count: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    not_evaluable_checks: int = 0
    presence_completeness_pct: float = 0.0
    usable_completeness_pct: float = 0.0
    scoring_input_completeness_pct: float = 0.0


class ScoringReadiness(BaseModel):
    ready_for_automatic_scoring: bool = False
    status: ReadinessStatus = "insufficient_data"
    blocking_reasons: list[str] = Field(default_factory=list)
    scoring_inputs_required: int = 0
    scoring_inputs_available: int = 0
    scoring_inputs_usable: int = 0
    critical_conflicts: int = 0
    critical_suspects: int = 0
    accounting_failures: int = 0
    quality_status: Literal["valid", "warning", "review_required", "blocked"] = "review_required"
    current_period_blockers: list[str] = Field(default_factory=list)
    historical_period_blockers: list[str] = Field(default_factory=list)


class AmountQuality(BaseModel):
    value: Optional[float] = None
    status: FieldQualityStatus = "missing"
    usable: bool = False
    confidence: Optional[float] = None
    evidence: list[FieldEvidence] = Field(default_factory=list)


class FiscalLine(BaseModel):
    label: str
    amount: Optional[float] = None
    evidence: list[FieldEvidence] = Field(default_factory=list)


class FiscalBlock(BaseModel):
    total: Optional[float] = None
    details: list[FiscalLine] = Field(default_factory=list)


class FiscalAnalysis(BaseModel):
    available: bool = False
    resultat_net_comptable: AmountQuality = Field(default_factory=AmountQuality)
    reintegrations: FiscalBlock = Field(default_factory=FiscalBlock)
    deductions: FiscalBlock = Field(default_factory=FiscalBlock)
    resultat_brut_fiscal: AmountQuality = Field(default_factory=AmountQuality)
    reports_deficitaires: AmountQuality = Field(default_factory=AmountQuality)
    resultat_net_fiscal: AmountQuality = Field(default_factory=AmountQuality)
    validation_status: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class AssociateRow(BaseModel):
    name: Optional[str] = None
    identifier: Optional[str] = None
    identifier_type: Optional[str] = None
    titres_previous: Optional[float] = None
    titres_current: Optional[float] = None
    nominal_value: Optional[float] = None
    capital_souscrit: Optional[float] = None
    capital_appele: Optional[float] = None
    capital_libere: Optional[float] = None
    confidence: Optional[float] = None
    status: FieldQualityStatus = "missing"
    evidence: list[FieldEvidence] = Field(default_factory=list)


class CapitalAnalysis(BaseModel):
    available: bool = False
    capital_social: AmountQuality = Field(default_factory=AmountQuality)
    validation_status: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    associates: list[AssociateRow] = Field(default_factory=list)


class YearsBlock(BaseModel):
    labels: list[str] = Field(default_factory=lambda: ["—", "N-1", "N"])
    years: list[int | None] = Field(default_factory=lambda: [None, None, None])
    available_count: int = 0
    series: dict[str, list[Optional[float]]] = Field(default_factory=dict)


class ScoringAnalysisResult(BaseModel):
    document: DocumentSummary
    extraction: ExtractionSummary
    fields: list[ExtractedField]
    completeness_pct: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    controls: list[AccountingControlView] = Field(default_factory=list)
    ratio_inputs: dict[str, Optional[float]] = Field(default_factory=dict)
    ratios: dict[str, Any] = Field(default_factory=dict)
    axes: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    years: YearsBlock = Field(default_factory=YearsBlock)
    quality: ExtractionQuality = Field(default_factory=ExtractionQuality)
    readiness: ScoringReadiness = Field(default_factory=ScoringReadiness)
    fiscal_analysis: FiscalAnalysis = Field(default_factory=FiscalAnalysis)
    capital_analysis: CapitalAnalysis = Field(default_factory=CapitalAnalysis)
    client_lookup: ClientLookup | None = None
    score_raw: Optional[float] = None


class AnalyseJobProgress(BaseModel):
    job_id: str
    dossier_id: str | None = None
    status: JobStatus
    progress_pct: int = 0
    current_step: str = "queued"
    current_page: int | None = None
    pages_total: int | None = None
    pages_financial: int = 0
    pages_skipped: int = 0
    pages_failed: int = 0
    message: str = ""
    error: str | None = None
    stream_url: str | None = None
    result_url: str | None = None
    filename: str | None = None


class AnalyseJobCreateResponse(BaseModel):
    job_id: str
    dossier_id: str
    status: JobStatus = "queued"
    stream_url: str
    result_url: str
    filename: str


class AnalyseStateResponse(BaseModel):
    dossier_id: str
    job: AnalyseJobProgress | None = None
    workspace: dict[str, Any] | None = None
    error: str | None = None


class DossierSyntheseResponse(BaseModel):
    dossier_id: str
    status: str
    job_id: str | None = None
    points_forts: list[str] = Field(default_factory=list)
    points_vigilance: list[str] = Field(default_factory=list)
    score_final: str | None = None
    score: int | None = None
    classe: str | None = None
    decision: str | None = None
    recommandation: str | None = None
    message: str | None = None


class CopilotHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[CopilotHistoryMessage] = Field(default_factory=list)


class CopilotChatResponse(BaseModel):
    reply: str
    model: str


class BilanIdentityResponse(BaseModel):
    identifiant_fiscal: str | None = None
    ice: str | None = None
    rc: str | None = None
    raison_sociale: str | None = None
    taxe_professionnelle: str | None = None
    ville: str | None = None
    adresse: str | None = None
    activite: str | None = None
    secteur: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    declaration_date: str | None = None
    declaration_time: str | None = None
    reference: str | None = None
