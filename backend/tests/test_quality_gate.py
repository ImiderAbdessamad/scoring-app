from __future__ import annotations

from app.schemas.analyse import ExtractedField, PeriodFieldValue
from app.services.scoring_lab_pipeline import _build_years, _ratio_inputs, _usable, build_result_from_v6
from app.services.v6_result_mapper import map_controls
from app.schemas.analyse import ExerciseInfo


def test_suspect_observed_excluded_from_ratio_inputs():
    field = ExtractedField(
        number=21,
        code="FONDS_PROPRES",
        label="Fonds propres",
        source="Bilan Passif",
        current=PeriodFieldValue(
            observed_value=50_000_000,
            usable_value=None,
            status="suspect",
            usable=False,
        ),
    )
    assert field.value == 50_000_000
    assert _usable(field) is None
    inputs = _ratio_inputs([field])
    assert inputs["fonds_propres"] is None


def test_year_labels_from_exercise_2024():
    years = _build_years([], ExerciseInfo(debut="01/01/2024", fin="31/12/2024"), "anything.pdf")
    assert years.labels == ["—", "2023", "2024"]
    assert years.years == [None, 2023, 2024]


def test_year_labels_from_exercise_2025():
    years = _build_years([], ExerciseInfo(debut="01/01/2025", fin="31/12/2025"), "Bilan 2024.pdf")
    assert years.labels == ["—", "2024", "2025"]


def test_controls_keep_current_and_previous():
    controls = map_controls(
        [
            {"check": "total_actif_equals_total_passif_current", "status": "passed", "difference": "0", "period": "current"},
            {"check": "total_actif_equals_total_passif_previous", "status": "failed", "difference": "12.5", "period": "previous"},
        ],
        year_n=2024,
    )
    assert len(controls) == 2
    by_period = {c.period: c for c in controls}
    assert by_period["current"].status == "passed"
    assert by_period["previous"].status == "failed"
    assert by_period["current"].period_label == "2024"
    assert by_period["previous"].period_label == "2023"


def test_caf_usable_feeds_scoring():
    v6 = {
        "identity": {
            "period_start": "01/01/2024",
            "period_end": "31/12/2024",
            "ice": "003120883000059",
            "raison_sociale": "TEST",
        },
        "canonical": {
            "caf": {
                "current": "120000",
                "previous": "110000",
                "usable_current": "120000",
                "usable_previous": "110000",
                "period_status": {"current": "observed", "previous": "observed"},
                "value_status": {"current": "high_confidence", "previous": "high_confidence"},
                "section": "esg",
                "label": "CAF",
            },
            "fonds_propres": {
                "current": "1000000",
                "usable_current": "1000000",
                "period_status": {"current": "observed"},
                "value_status": {"current": "high_confidence"},
            },
        },
        "validations": [],
        "pages": [],
    }
    result = build_result_from_v6(v6, "liasse.pdf")
    assert result.years.labels == ["—", "2023", "2024"]
    assert result.ratio_inputs["caf"] == 120000.0
    assert result.quality.usable_current_count >= 1
    assert result.readiness.status in {"ready", "review_required", "insufficient_data", "blocked"}
