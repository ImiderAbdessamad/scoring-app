from __future__ import annotations

import json
import logging
from decimal import Decimal

from app.core.config import settings
from app.db.repositories.sector_data_repository import sector_data_repository
from app.sector.calculations import cagr, growth_gap, normalized_index, safe_growth
from app.sector.domain import (
    CompanyAnnualPoint,
    CompanySectorMetrics,
    GrowthComparisonPoint,
    NormalizedSectorPoint,
    SectorAnalysisResult,
    SectorComparableIndicator,
    SectorDataFreshness,
    SectorHeadline,
    SectorInfo,
    SectorInsight,
    SectorMomentum,
    SectorScoringInfo,
    SectorSeriesPoint,
)
from app.sector.mapping import resolve_mapping_for_record
from app.sector.sources_catalog import (
    DEFAULT_SOURCE_ID,
    dataset_id_for_role,
    get_source,
    resolve_source_id,
)
from app.services import sector_source_config
from app.services.sector_sync_service import freshness_for, schedule_background_refresh

logger = logging.getLogger(__name__)

REAL_GROWTH_NOTE = (
    "La croissance réelle sectorielle est affichée comme indicateur de "
    "conjoncture et n'est pas directement soustraite à la croissance nominale "
    "de l'entreprise."
)


def _usable(field, period: str) -> Decimal | None:
    if field is None:
        return None
    block = field.current if period == "current" else field.previous
    if block is None or not block.usable or block.usable_value is None:
        return None
    return Decimal(str(block.usable_value))


def _years_from_result(result) -> tuple[int | None, int | None]:
    years = list((result.years.years if result and result.years else []) or [])
    year_n = years[2] if len(years) > 2 else None
    year_n1 = years[1] if len(years) > 1 else None
    return year_n, year_n1


def _company_series(record, result) -> list[CompanyAnnualPoint]:
    if result is None:
        return []
    by_code = {f.code: f for f in (result.fields or [])}
    year_n, year_n1 = _years_from_result(result)
    points: list[CompanyAnnualPoint] = []
    if year_n1:
        va = _usable(by_code.get("VALEUR_AJOUTEE"), "previous")
        ca = _usable(by_code.get("CHIFFRE_AFFAIRES"), "previous")
        points.append(
            CompanyAnnualPoint(
                year=year_n1,
                va=float(va) if va is not None else None,
                ca=float(ca) if ca is not None else None,
                ebe=float(v) if (v := _usable(by_code.get("EBE"), "previous")) is not None else None,
                resultatExploitation=float(v)
                if (v := _usable(by_code.get("RESULTAT_EXPLOITATION"), "previous")) is not None
                else None,
                resultatNet=float(v) if (v := _usable(by_code.get("RESULTAT_NET"), "previous")) is not None else None,
                caf=float(v) if (v := _usable(by_code.get("CAF"), "previous")) is not None else None,
                vaUsable=va is not None,
                caUsable=ca is not None,
            )
        )
    if year_n:
        va = _usable(by_code.get("VALEUR_AJOUTEE"), "current")
        ca = _usable(by_code.get("CHIFFRE_AFFAIRES"), "current")
        points.append(
            CompanyAnnualPoint(
                year=year_n,
                va=float(va) if va is not None else None,
                ca=float(ca) if ca is not None else None,
                ebe=float(v) if (v := _usable(by_code.get("EBE"), "current")) is not None else None,
                resultatExploitation=float(v)
                if (v := _usable(by_code.get("RESULTAT_EXPLOITATION"), "current")) is not None
                else None,
                resultatNet=float(v) if (v := _usable(by_code.get("RESULTAT_NET"), "current")) is not None else None,
                caf=float(v) if (v := _usable(by_code.get("CAF"), "current")) is not None else None,
                vaUsable=va is not None,
                caUsable=ca is not None,
            )
        )
    return points


def _series_points(rows, *, yoy: bool = False) -> list[SectorSeriesPoint]:
    points: list[SectorSeriesPoint] = []
    prev = None
    keyed: dict[tuple[int, int], object] = {}
    for row in rows:
        value = float(row.value) if row.value is not None else None
        growth = None
        if yoy:
            lag = keyed.get((row.year - 1, row.quarter or 0))
            if lag is not None:
                growth = safe_growth(row.value, lag)
        elif prev is not None:
            growth = safe_growth(row.value, prev.value)
        points.append(
            SectorSeriesPoint(
                year=row.year,
                quarter=row.quarter or None,
                value=value,
                unit=row.unit,
                growthYoy=growth,
            )
        )
        keyed[(row.year, row.quarter or 0)] = row.value
        prev = row
    return points


def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return float(num) / float(den)


def _company_metrics(points: list[CompanyAnnualPoint]) -> CompanySectorMetrics:
    if not points:
        return CompanySectorMetrics()
    current = points[-1]
    prev = points[-2] if len(points) > 1 else None
    return CompanySectorMetrics(
        companyVaGrowth=safe_growth(current.va, prev.va) if prev else None,
        companyCaGrowth=safe_growth(current.ca, prev.ca) if prev else None,
        vaOverCa=_ratio(current.va, current.ca),
        ebeOverVa=_ratio(current.ebe, current.va),
        operatingMargin=_ratio(current.resultatExploitation, current.ca),
        netMargin=_ratio(current.resultatNet, current.ca),
        cafMargin=_ratio(current.caf, current.ca),
    )


def _momentum(annual_real: list[SectorSeriesPoint]) -> SectorMomentum:
    if len(annual_real) < 2:
        latest = annual_real[-1].growthYoy if annual_real else None
        return SectorMomentum(trend="INSUFFICIENT_DATA", latestRealGrowth=latest)
    latest = annual_real[-1].growthYoy
    previous = annual_real[-2].growthYoy
    accel = None if latest is None or previous is None else latest - previous
    trend: str = "INSUFFICIENT_DATA"
    if latest is not None and accel is not None:
        if latest > 0 and accel > 0:
            trend = "EXPANDING_ACCELERATING"
        elif latest > 0 and accel < 0:
            trend = "EXPANDING_SLOWING"
        elif latest < 0:
            trend = "CONTRACTING"
        else:
            trend = "STABLE"
    elif latest is not None and latest < 0:
        trend = "CONTRACTING"
    return SectorMomentum(
        trend=trend,  # type: ignore[arg-type]
        latestRealGrowth=latest,
        previousRealGrowth=previous,
        realGrowthAcceleration=accel,
    )


def _insights(result: SectorAnalysisResult) -> list[SectorInsight]:
    items: list[SectorInsight] = []
    trend = result.momentum.trend
    if trend == "EXPANDING_ACCELERATING":
        items.append(SectorInsight(code="SECTOR_ACCELERATION", text="La croissance réelle du secteur reste positive et accélère."))
    elif trend == "EXPANDING_SLOWING":
        items.append(SectorInsight(code="SECTOR_SLOWDOWN", text="La croissance réelle du secteur reste positive mais ralentit."))
    elif trend == "CONTRACTING":
        items.append(SectorInsight(code="SECTOR_CONTRACTION", text="La valeur ajoutée réelle du secteur se contracte."))
    elif result.headline.realGrowthYoy is not None and result.headline.realGrowthYoy > 0:
        items.append(SectorInsight(code="SECTOR_EXPANSION", text="Le secteur affiche une croissance réelle positive."))
    gap = next((g.gapPp for g in reversed(result.growthComparison) if g.gapPp is not None), None)
    if gap is not None and gap > 0:
        items.append(
            SectorInsight(
                code="COMPANY_OUTPERFORMS_NOMINAL",
                text=f"La croissance nominale de la VA de l’entreprise dépasse celle du secteur de {gap:.1f} points.",
            )
        )
    elif gap is not None and gap < 0:
        items.append(
            SectorInsight(
                code="COMPANY_UNDERPERFORMS_NOMINAL",
                text=f"La croissance nominale de la VA de l’entreprise est inférieure à celle du secteur de {abs(gap):.1f} points.",
            )
        )
    if not any(p.vaUsable for p in result.companyAnnual):
        items.append(
            SectorInsight(
                code="INSUFFICIENT_COMPARABLE_YEARS",
                severity="WARNING",
                text="Pas assez d’années d’entreprise comparables pour une trajectoire base 100.",
            )
        )
    return items


def _deterministic_summary(result: SectorAnalysisResult) -> str:
    parts: list[str] = []
    h = result.headline
    if h.nominalGrowthYoy is not None and h.latestYear:
        sign = "+" if h.nominalGrowthYoy >= 0 else ""
        parts.append(
            f"La valeur ajoutée du secteur a progressé de {sign}{h.nominalGrowthYoy:.1f} % "
            f"en valeur courante sur le dernier exercice disponible ({h.latestYear})."
        )
    elif h.latestYear:
        parts.append(f"Valeur ajoutée sectorielle disponible pour {h.latestYear}.")
    if h.realGrowthYoy is not None:
        sign = "+" if h.realGrowthYoy >= 0 else ""
        parts.append(f"En volume, la croissance est de {sign}{h.realGrowthYoy:.1f} %.")
    gap_row = next((g for g in reversed(result.growthComparison) if g.gapPp is not None), None)
    company_g = next((g for g in reversed(result.growthComparison) if g.companyGrowth is not None), None)
    if company_g and company_g.companyGrowth is not None:
        sign = "+" if company_g.companyGrowth >= 0 else ""
        parts.append(
            f"La valeur ajoutée de l’entreprise progresse de {sign}{company_g.companyGrowth:.1f} % "
            "sur la période comparable."
        )
    if gap_row and gap_row.gapPp is not None:
        sign = "+" if gap_row.gapPp >= 0 else ""
        parts.append(f"Écart nominal entreprise-secteur : {sign}{gap_row.gapPp:.1f} points.")
    return " ".join(parts) if parts else "Analyse sectorielle HCP disponible, sans commentaire de risque."


def _period_label(year: int | None, quarter: int | None = None) -> str | None:
    if year is None:
        return None
    if quarter:
        return f"{year} T{quarter}"
    return str(year)


def _latest_point(points: list[SectorSeriesPoint]):
    if not points:
        return None
    return max(points, key=lambda p: (p.year, p.quarter or 0))


def _resolve_record_source(record):
    pinned = getattr(record, "sectorSourceId", None)
    if pinned:
        return resolve_source_id(pinned, DEFAULT_SOURCE_ID)
    return resolve_source_id(sector_source_config.get_default_source_id(), DEFAULT_SOURCE_ID)


class SectorAnalysisService:
    def analyze(
        self,
        *,
        record,
        result=None,
        trigger_refresh: bool = False,
        persist_run_id: str | None = None,
    ) -> SectorAnalysisResult:
        warnings: list[str] = []
        identity = None
        if result is not None:
            identity = result.document.identity

        source_id = _resolve_record_source(record)
        source_def = get_source(source_id) or get_source(DEFAULT_SOURCE_ID)
        source_label = source_def.short_label if source_def else "HCP"
        source_code = source_def.code if source_def else "HCP"

        scoring = SectorScoringInfo(includedInFinalScore=False)
        if settings.sector_analysis_affects_scoring:
            scoring.note = (
                "SECTOR_ANALYSIS_AFFECTS_SCORING=true mais aucune politique Wafabail n’est configurée — "
                "le score officiel reste null."
            )

        # Source non prête pour l'analyse VA → pas de mélange avec HCP.
        if source_def is None or not source_def.supports_va_analysis:
            sector_info = SectorInfo(
                rawActivity=getattr(record, "sectorRaw", None) or getattr(record, "sector", None),
                sourceId=source_id,
                sourceLabel=source_label,
                sourceCode=source_code,
            )
            out = SectorAnalysisResult(
                status="UNAVAILABLE",
                sector=sector_info,
                dataFreshness=SectorDataFreshness(status="UNAVAILABLE", source=source_code),
                warnings=[
                    (
                        f"La source « {source_label} » n’est pas encore disponible pour "
                        "l’analyse sectorielle VA. Choisissez HCP ou une autre source compatible."
                    )
                ],
                scoring=scoring,
                realGrowthNote=REAL_GROWTH_NOTE,
            )
            return self._maybe_persist(record, persist_run_id, out)

        # Mapping branches : uniquement pour la taxonomie de la source active.
        if source_def.branch_catalog == "hcp":
            mapping = resolve_mapping_for_record(record, identity)
        else:
            from app.sector.domain import SectorMappingResult

            mapping = SectorMappingResult(
                raw_activity=getattr(record, "sectorRaw", None) or getattr(record, "sector", None),
                status="UNMATCHED",
                confidence=0.0,
            )

        role_current = dataset_id_for_role(source_id, "annual_va_current")
        role_volume = dataset_id_for_role(source_id, "annual_va_volume")
        role_q_current = dataset_id_for_role(source_id, "quarterly_va_current")
        role_q_volume = dataset_id_for_role(source_id, "quarterly_va_volume")

        # Datasets liés à la source (évite collision d'IDs externes entre providers).
        hcp_source_row = None
        try:
            hcp_source_row = sector_data_repository.ensure_hcp_source()
        except Exception:
            hcp_source_row = None
        sqlite_source_pk = hcp_source_row.id if hcp_source_row and source_id == "hcp" else None

        current_ds = (
            sector_data_repository.get_dataset_by_external(role_current, source_id=sqlite_source_pk)
            if role_current
            else None
        )
        if current_ds is None and role_current:
            current_ds = sector_data_repository.get_dataset_by_external(role_current)
        volume_ds = (
            sector_data_repository.get_dataset_by_external(role_volume, source_id=sqlite_source_pk)
            if role_volume
            else None
        )
        if volume_ds is None and role_volume:
            volume_ds = sector_data_repository.get_dataset_by_external(role_volume)
        q_current_ds = (
            sector_data_repository.get_dataset_by_external(role_q_current, source_id=sqlite_source_pk)
            if role_q_current
            else None
        )
        if q_current_ds is None and role_q_current:
            q_current_ds = sector_data_repository.get_dataset_by_external(role_q_current)
        q_ds = (
            sector_data_repository.get_dataset_by_external(role_q_volume, source_id=sqlite_source_pk)
            if role_q_volume
            else None
        )
        if q_ds is None and role_q_volume:
            q_ds = sector_data_repository.get_dataset_by_external(role_q_volume)

        freshness_status = freshness_for(current_ds)
        if trigger_refresh and freshness_status in {"STALE", "VERY_STALE", "UNAVAILABLE"}:
            if source_id == "hcp":
                schedule_background_refresh()
        if freshness_status in {"STALE", "VERY_STALE"}:
            warnings.append(
                f"Données {source_label} en cache — dernière synchronisation antérieure au seuil de fraîcheur."
            )
        versions = []
        for ds in (current_ds, volume_ds, q_current_ds, q_ds):
            if ds:
                versions.append(
                    {
                        "datasetId": ds.external_dataset_id,
                        "sha256": ds.resource_sha256,
                        "updatedAt": ds.source_updated_at,
                    }
                )
        freshness = SectorDataFreshness(
            status=freshness_status if freshness_status != "VERY_STALE" else "STALE",
            lastSyncAt=current_ds.last_successful_sync_at.isoformat()
            if current_ds and current_ds.last_successful_sync_at
            else None,
            lastCheckedAt=current_ds.last_checked_at.isoformat() if current_ds and current_ds.last_checked_at else None,
            source=source_code,
            datasetVersions=versions,
            cached=freshness_status in {"STALE", "VERY_STALE", "FRESH"},
        )
        sector_info = SectorInfo(
            rawActivity=mapping.raw_activity,
            code=mapping.sector_code,
            label=mapping.sector_label,
            mappingConfidence=mapping.confidence,
            mappingStatus=mapping.status,
            mappingType=mapping.mapping_method,
            validated=mapping.validated,
            sourceId=source_id,
            sourceLabel=source_label,
            sourceCode=source_code,
        )
        if mapping.status == "REVIEW_REQUIRED":
            out = SectorAnalysisResult(
                status="MAPPING_REVIEW_REQUIRED",
                sector=sector_info,
                dataFreshness=freshness,
                warnings=["Classification sectorielle à confirmer."] + warnings,
                scoring=scoring,
                realGrowthNote=REAL_GROWTH_NOTE,
            )
            return self._maybe_persist(record, persist_run_id, out)
        if mapping.status != "MATCHED" or not mapping.sector_code:
            out = SectorAnalysisResult(
                status="UNMAPPED",
                sector=sector_info,
                dataFreshness=freshness,
                warnings=[
                    f"Le secteur de l’entreprise n’a pas pu être rapproché d’une branche {source_label} "
                    "de manière fiable."
                ]
                + warnings,
                scoring=scoring,
                realGrowthNote=REAL_GROWTH_NOTE,
            )
            return self._maybe_persist(record, persist_run_id, out)
        if current_ds is None or not current_ds.resource_sha256:
            out = SectorAnalysisResult(
                status="NO_DATA",
                sector=sector_info,
                dataFreshness=SectorDataFreshness(status="UNAVAILABLE", source=source_code),
                warnings=[
                    f"Les données sectorielles ({source_label}) ne sont pas disponibles actuellement."
                ]
                + warnings,
                scoring=scoring,
                realGrowthNote=REAL_GROWTH_NOTE,
            )
            return self._maybe_persist(record, persist_run_id, out)

        annual_current = _series_points(
            sector_data_repository.list_observations(
                dataset_pk=current_ds.id, sector_code=mapping.sector_code, period_type="ANNUAL"
            )
        )
        annual_real: list[SectorSeriesPoint] = []
        if volume_ds:
            annual_real = _series_points(
                sector_data_repository.list_observations(
                    dataset_pk=volume_ds.id, sector_code=mapping.sector_code, period_type="ANNUAL"
                )
            )
        quarterly: list[SectorSeriesPoint] = []
        if q_current_ds:
            quarterly = _series_points(
                sector_data_repository.list_observations(
                    dataset_pk=q_current_ds.id, sector_code=mapping.sector_code
                ),
                yoy=True,
            )
        quarterly_real: list[SectorSeriesPoint] = []
        if q_ds:
            quarterly_real = _series_points(
                sector_data_repository.list_observations(
                    dataset_pk=q_ds.id, sector_code=mapping.sector_code
                ),
                yoy=True,
            )
        if not quarterly and quarterly_real:
            quarterly = quarterly_real
        latest_q = _latest_point(quarterly)
        latest_q_real = _latest_point(quarterly_real)
        quarterly_for_chart = quarterly[-16:]
        if current_ds:
            latest_annual = annual_current[-1] if annual_current else None
            q_is_newer = bool(
                latest_q
                and (
                    latest_annual is None
                    or (latest_q.year, latest_q.quarter or 0) > (latest_annual.year, 0)
                )
            )
            freshness.latestObservationPeriod = (
                _period_label(latest_q.year, latest_q.quarter)
                if q_is_newer and latest_q
                else _period_label(latest_annual.year if latest_annual else None)
            )
        company = _company_series(record, result)
        company_by_year = {p.year: p for p in company}
        growth_rows: list[GrowthComparisonPoint] = []
        for i, point in enumerate(annual_current):
            prev = annual_current[i - 1] if i else None
            company_point = company_by_year.get(point.year)
            prev_company = company_by_year.get(point.year - 1)
            company_growth = None
            if company_point and prev_company:
                company_growth = safe_growth(company_point.va, prev_company.va)
            growth_rows.append(
                GrowthComparisonPoint(
                    year=point.year,
                    companyGrowth=company_growth,
                    sectorGrowth=point.growthYoy,
                    gapPp=growth_gap(company_growth, point.growthYoy),
                    companyAvailable=bool(company_point and company_point.vaUsable),
                )
            )
        overlap_years = [p.year for p in annual_current if p.year in company_by_year and company_by_year[p.year].vaUsable]
        normalized: list[NormalizedSectorPoint] = []
        if overlap_years:
            base_year = overlap_years[0]
            company_vals = [company_by_year.get(y).va if company_by_year.get(y) else None for y in overlap_years]
            sector_vals = []
            for y in overlap_years:
                match = next((p.value for p in annual_current if p.year == y), None)
                sector_vals.append(match)
            c_idx = normalized_index(company_vals)
            s_idx = normalized_index(sector_vals)
            for year, ci, si in zip(overlap_years, c_idx, s_idx):
                normalized.append(NormalizedSectorPoint(year=year, companyIndex=ci, sectorIndex=si))
            del base_year
        latest = annual_current[-1] if annual_current else None
        prev_latest = annual_current[-2] if len(annual_current) > 1 else None
        real_latest = annual_real[-1] if annual_real else None
        real_prev = annual_real[-2] if len(annual_real) > 1 else None
        real_growth = safe_growth(real_latest.value, real_prev.value) if real_latest and real_prev else None
        if latest_q_real and latest_q_real.growthYoy is not None:
            if real_latest is None or latest_q_real.year > real_latest.year:
                real_growth = latest_q_real.growthYoy
        cagr3 = None
        if len(annual_current) >= 4:
            cagr3 = cagr(annual_current[-4].value, annual_current[-1].value, 3)
        headline = SectorHeadline(
            latestSectorVa=latest.value if latest else None,
            latestYear=latest.year if latest else None,
            latestUnit=latest.unit if latest else "M MAD",
            latestQuarterlyPeriod=_period_label(latest_q.year, latest_q.quarter) if latest_q else None,
            nominalGrowthYoy=safe_growth(latest.value, prev_latest.value) if latest and prev_latest else None,
            realGrowthYoy=real_growth,
            cagr3y=cagr3,
        )
        last_gap = next((g for g in reversed(growth_rows) if g.gapPp is not None), None)
        last_company = next((g for g in reversed(growth_rows) if g.companyGrowth is not None), None)
        comparables = [
            SectorComparableIndicator(
                code="VA_NOMINAL_GROWTH",
                label="Croissance VA nominale",
                companyValue=last_company.companyGrowth if last_company else None,
                sectorValue=headline.nominalGrowthYoy,
                unit="%",
                gap=last_gap.gapPp if last_gap else None,
                comparable=last_company is not None and headline.nominalGrowthYoy is not None,
                reason=None if last_company else "Analyse de la liasse requise",
                source="HCP comptes nationaux / ESG entreprise",
            )
        ]
        status = "AVAILABLE" if annual_current else "NO_DATA"
        if status == "AVAILABLE" and (not company or all(not p.vaUsable for p in company)):
            status = "PARTIAL"
            warnings.append("Analyse de la liasse requise pour comparer l’entreprise au secteur.")
        if not annual_real:
            warnings.append("Série annuelle de volume HCP absente — croissance réelle annuelle non calculée.")
        if latest_q and latest and latest_q.year > latest.year:
            warnings.append(
                f"Comptes annuels HCP disponibles jusqu’à {latest.year}. "
                f"Conjoncture trimestrielle jusqu’à {_period_label(latest_q.year, latest_q.quarter)}."
            )
        metrics = _company_metrics(company)
        momentum = _momentum(annual_real if len(annual_real) >= 2 else quarterly_real)
        out = SectorAnalysisResult(
            status=status,
            sector=sector_info,
            dataFreshness=freshness,
            headline=headline,
            sectorAnnualCurrent=annual_current,
            sectorAnnualReal=annual_real,
            sectorQuarterly=quarterly_for_chart,
            companyAnnual=company,
            normalizedComparison=normalized,
            growthComparison=growth_rows[-12:],
            comparableIndicators=comparables,
            companyMetrics=metrics,
            momentum=momentum,
            warnings=warnings,
            scoring=scoring,
            realGrowthNote=REAL_GROWTH_NOTE,
        )
        out.insights = _insights(out)
        out.summary = _deterministic_summary(out)
        return self._maybe_persist(record, persist_run_id, out)

    def _maybe_persist(self, record, run_id: str | None, result: SectorAnalysisResult) -> SectorAnalysisResult:
        if record is None:
            return result
        try:
            sector_data_repository.save_snapshot(
                dossier_id=record.id,
                analysis_run_id=run_id,
                sector_code=result.sector.code,
                sector_label=result.sector.label,
                data_version={"freshness": result.dataFreshness.model_dump(), "datasets": result.dataFreshness.datasetVersions},
                result=result.model_dump(),
            )
        except Exception as exc:
            logger.warning("sector snapshot persist failed: %s", exc)
        return result

    def for_workspace(self, record, result) -> dict:
        try:
            analysis = self.analyze(record=record, result=result, trigger_refresh=True)
            return json.loads(analysis.model_dump_json())
        except Exception as exc:
            logger.warning("sector analysis skipped: %s", exc)
            return SectorAnalysisResult(
                status="UNAVAILABLE",
                warnings=["Analyse sectorielle temporairement indisponible."],
                scoring=SectorScoringInfo(),
            ).model_dump()


sector_analysis_service = SectorAnalysisService()
