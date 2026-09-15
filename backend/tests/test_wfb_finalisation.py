from __future__ import annotations

from app.domain.period_math import safe_sum_period_fields
from app.schemas.analyse import PeriodFieldValue
from app.services.decision_eligibility import evaluate_decision_eligibility
from app.services.scoring_engine import compute_scores, score_axe3_sectoriel
from app.services.v6_result_mapper import map_fields


def _usable(value: float) -> PeriodFieldValue:
    return PeriodFieldValue(observed_value=value, usable_value=value, status="confirmed", usable=True)


def test_period_field_observed_vs_usable():
    field = PeriodFieldValue(observed_value=10, usable_value=None, status="suspect", usable=False)
    assert field.observed_value == 10
    assert field.usable_value is None
    assert field.observed_value != field.usable_value


def test_missing_is_not_zero():
    missing = PeriodFieldValue(status="missing", usable=False)
    zero = PeriodFieldValue(observed_value=0, usable_value=0, status="confirmed", usable=True)
    assert missing.usable_value is None
    assert zero.usable_value == 0


def test_chiffre_affaires_both_components():
    canonical = {
        "ventes_marchandises": {"current": "100", "usable_current": "100", "period_status": {"current": "observed"}, "value_status": {"current": "high_confidence"}},
        "ventes_biens_services": {"current": "50", "usable_current": "50", "period_status": {"current": "observed"}, "value_status": {"current": "high_confidence"}},
    }
    fields = {f.code: f for f in map_fields(canonical)}
    ca = fields["CHIFFRE_AFFAIRES"]
    assert ca.current.usable_value == 150
    assert ca.current.status == "derived"


def test_chiffre_affaires_one_missing():
    canonical = {
        "ventes_marchandises": {"current": "100", "usable_current": "100", "period_status": {"current": "observed"}, "value_status": {"current": "high_confidence"}},
    }
    fields = {f.code: f for f in map_fields(canonical)}
    ca = fields["CHIFFRE_AFFAIRES"]
    assert ca.current.usable_value is None
    assert ca.current.accounting_status == "derived_unavailable"


def test_chiffre_affaires_explicit_zero():
    zero = PeriodFieldValue(status="missing", usable=False, accounting_status="explicit_zero")
    other = _usable(40)
    summed = safe_sum_period_fields([zero, other], accounting_status="derived_from_sales_components")
    assert summed.usable_value == 40


def test_partial_score_without_behavior():
    computed = compute_scores(85.0, None, 70.0)
    assert computed["score_status"] == "PARTIAL"
    assert computed["final_score"] is None
    assert computed["partial_score"] is not None
    assert computed["classe"] is None
    assert "behavioral" in computed["missing_axes"]


def test_final_score_requires_policy_conditions():
    computed = compute_scores(85.0, 75.0, 80.0)
    assert computed["score_status"] == "FINAL"
    assert computed["final_score"] is not None
    assert computed["classe"] is not None


def test_sector_without_benchmark_is_none():
    scored = score_axe3_sectoriel({"rentabilite_commerciale": {"value": 0.04}})
    assert scored["score"] is None
    assert scored["status"] == "NOT_CALIBRATED"


def test_bam_unknown():
    result = evaluate_decision_eligibility(
        readiness_status="ready",
        quality_ready=True,
        behavioral_ready=True,
        sector_ready=True,
        bam_status="UNKNOWN",
        incident_status="VERIFIED_CLEAR",
        mandatory_documents_ready=True,
        analysis_stale=False,
        score_status="FINAL",
    )
    assert "BAM_NOT_CHECKED" in result.blocking_reasons
    assert result.eligible_for_approval is False


def test_bam_blocked():
    result = evaluate_decision_eligibility(
        readiness_status="ready",
        quality_ready=True,
        behavioral_ready=True,
        sector_ready=True,
        bam_status="BLOCKED",
        incident_status="VERIFIED_CLEAR",
        mandatory_documents_ready=True,
        analysis_stale=False,
        score_status="FINAL",
    )
    assert "BAM_BLOCKED" in result.blocking_reasons


def test_incident_unknown():
    result = evaluate_decision_eligibility(
        readiness_status="ready",
        quality_ready=True,
        behavioral_ready=True,
        sector_ready=True,
        bam_status="VERIFIED_CLEAR",
        incident_status="UNKNOWN",
        mandatory_documents_ready=True,
        analysis_stale=False,
        score_status="FINAL",
    )
    assert "INCIDENTS_NOT_CHECKED" in result.blocking_reasons


def test_decision_approval_blocked():
    result = evaluate_decision_eligibility(
        readiness_status="review_required",
        quality_ready=False,
        behavioral_ready=False,
        sector_ready=False,
        bam_status="UNKNOWN",
        incident_status="UNKNOWN",
        mandatory_documents_ready=False,
        analysis_stale=True,
        score_status="PARTIAL",
    )
    assert result.eligible_for_approval is False
    assert result.eligible_for_rejection is True


def test_rejection_with_reason_policy():
    result = evaluate_decision_eligibility(
        readiness_status="insufficient_data",
        quality_ready=False,
        behavioral_ready=False,
        sector_ready=False,
        bam_status="UNKNOWN",
        incident_status="UNKNOWN",
        mandatory_documents_ready=False,
        analysis_stale=False,
        score_status="NOT_CALCULABLE",
    )
    assert result.eligible_for_rejection is True


def test_kafka_disabled_without_broker(monkeypatch):
    from app.core.config import settings
    from app.services import kafka_publisher

    monkeypatch.setattr(settings, "kafka_enabled", False)
    assert kafka_publisher.publish_scoring_event("x", job_id="1", dossier_id="2") is False
