from __future__ import annotations

from app.schemas.analyse import AccountingControlView, ExtractedField, PeriodFieldValue, ScoringAnalysisResult
from app.schemas.analyse import CompanyInfo, DocumentSummary, ExerciseInfo, ExtractionSummary, IdentityInfo
from app.services.quality_gate import evaluate_quality
from app.services.scoring_lab_pipeline import merge_liasse_years
from app.schemas.analyse import YearsBlock


def _base_result(fields, controls) -> ScoringAnalysisResult:
    return ScoringAnalysisResult(
        document=DocumentSummary(
            filename="x.pdf",
            pages_total=1,
            pages_processed=1,
            pages_skipped=0,
            pages_failed=0,
        ),
        extraction=ExtractionSummary(model="t"),
        fields=fields,
        controls=controls,
        ratio_inputs={
            "fonds_propres": 1,
            "total_bilan": 1,
            "chiffre_affaires": 1,
            "resultat_net": 1,
            "dettes_financement": 1,
            "caf": 1,
            "fdr": 1,
            "tresorerie_nette": 1,
            "clients": 1,
            "fournisseurs": 1,
            "actifs_immobilises": 1,
        },
    )


def test_previous_suspect_does_not_block_current():
    fields = [
        ExtractedField(
            number=2,
            code="TOTAL_BILAN",
            label="Total bilan",
            source="Bilan",
            current=PeriodFieldValue(observed_value=10, usable_value=10, status="confirmed", usable=True),
            previous=PeriodFieldValue(observed_value=9, usable_value=None, status="suspect", usable=False),
        ),
        ExtractedField(number=21, code="FONDS_PROPRES", label="FP", source="p", current=PeriodFieldValue(observed_value=1, usable_value=1, status="confirmed", usable=True)),
        ExtractedField(number=3, code="CHIFFRE_AFFAIRES", label="CA", source="c", current=PeriodFieldValue(observed_value=1, usable_value=1, status="confirmed", usable=True)),
        ExtractedField(number=30, code="CAF", label="CAF", source="e", current=PeriodFieldValue(observed_value=1, usable_value=1, status="confirmed", usable=True)),
    ]
    result = _base_result(fields, [])
    quality, readiness = evaluate_quality(result)
    assert any("N-1" in b for b in readiness.historical_period_blockers)
    assert not any("suspect." == b or b.endswith("suspect.") and "N-1" not in b for b in readiness.current_period_blockers) or "Total bilan suspect." not in readiness.current_period_blockers


def test_growth_requires_both_periods():
    from app.services.ratio_engine import croissance_ca

    r = croissance_ca(None, 100)
    assert r["value"] is None


def test_multi_liasse_same_value():
    primary = _base_result([], [])
    primary.years = YearsBlock(labels=["—", "2023", "2024"], years=[None, 2023, 2024], series={"ca": [None, 10, 20]})
    extra = _base_result([], [])
    extra.years = YearsBlock(labels=["—", "2023", "2024"], years=[None, 2023, 2024], series={"ca": [None, 10, 20]})
    merged = merge_liasse_years(primary, [extra])
    assert merged.years.series["ca"][2] == 20
    assert not any(str(w).startswith("SOURCE_CONFLICT") for w in merged.warnings)


def test_multi_liasse_conflict():
    primary = _base_result([], [])
    primary.years = YearsBlock(labels=["—", "2023", "2024"], years=[None, 2023, 2024], series={"ca": [None, 10, 20]})
    extra = _base_result([], [])
    extra.years = YearsBlock(labels=["—", "2023", "2024"], years=[None, 2023, 2024], series={"ca": [None, 10, 12]})
    merged = merge_liasse_years(primary, [extra])
    assert merged.years.series["ca"][2] is None
    assert any("SOURCE_CONFLICT" in str(w) for w in merged.warnings)
