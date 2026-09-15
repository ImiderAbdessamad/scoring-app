from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.scoring_policy import ScoreStatus


class DecisionEligibilityResult(BaseModel):
    financial_analysis_ready: bool = False
    behavioral_analysis_ready: bool = False
    sector_analysis_ready: bool = False
    bam_checked: bool = False
    bam_clear: bool | None = None
    incidents_checked: bool = False
    incidents_clear: bool | None = None
    mandatory_documents_ready: bool = False
    quality_gate_passed: bool = False
    analysis_stale: bool = False
    score_status: ScoreStatus = "NOT_CALCULABLE"
    eligible_for_automatic_recommendation: bool = False
    eligible_for_approval: bool = False
    eligible_for_reserve: bool = False
    eligible_for_rejection: bool = True
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def evaluate_decision_eligibility(
    *,
    readiness_status: str | None,
    quality_ready: bool,
    behavioral_ready: bool,
    sector_ready: bool,
    bam_status: str,
    incident_status: str,
    mandatory_documents_ready: bool,
    analysis_stale: bool,
    score_status: str,
    policy_require_bam: bool = True,
    policy_require_incidents: bool = True,
) -> DecisionEligibilityResult:
    blockers: list[str] = []
    warnings: list[str] = []

    financial_ok = bool(quality_ready and readiness_status == "ready")
    if not financial_ok:
        blockers.append("FINANCIAL_QUALITY_GATE_FAILED")

    if not behavioral_ready:
        blockers.append("BEHAVIORAL_AXIS_MISSING")

    if not sector_ready:
        warnings.append("SECTOR_ANALYSIS_INCOMPLETE")

    bam_checked = bam_status != "UNKNOWN"
    bam_clear = True if bam_status == "VERIFIED_CLEAR" else False if bam_status == "BLOCKED" else None
    if policy_require_bam and not bam_checked:
        blockers.append("BAM_NOT_CHECKED")
    if bam_status == "BLOCKED":
        blockers.append("BAM_BLOCKED")

    incidents_checked = incident_status != "UNKNOWN"
    incidents_clear = (
        True
        if incident_status in {"VERIFIED_CLEAR", "PRESENT_RESOLVED"}
        else False
        if incident_status == "PRESENT_UNRESOLVED"
        else None
    )
    if policy_require_incidents and not incidents_checked:
        blockers.append("INCIDENTS_NOT_CHECKED")
    if incident_status == "PRESENT_UNRESOLVED":
        blockers.append("INCIDENTS_UNRESOLVED")

    if not mandatory_documents_ready:
        blockers.append("MANDATORY_DOCUMENT_MISSING:PROFORMA")

    if analysis_stale:
        blockers.append("ANALYSIS_STALE")

    if score_status != "FINAL":
        blockers.append("SCORE_NOT_FINAL")
        if score_status == "PARTIAL":
            warnings.append("SCORE_PARTIAL")

    unique = list(dict.fromkeys(blockers))
    eligible_approval = not unique
    eligible_reserve = financial_ok and not analysis_stale and "BAM_BLOCKED" not in unique
    return DecisionEligibilityResult(
        financial_analysis_ready=financial_ok,
        behavioral_analysis_ready=behavioral_ready,
        sector_analysis_ready=sector_ready,
        bam_checked=bam_checked,
        bam_clear=bam_clear,
        incidents_checked=incidents_checked,
        incidents_clear=incidents_clear,
        mandatory_documents_ready=mandatory_documents_ready,
        quality_gate_passed=quality_ready,
        analysis_stale=analysis_stale,
        score_status=score_status if score_status in {"NOT_CALCULABLE", "PARTIAL", "FINAL"} else "NOT_CALCULABLE",  # type: ignore[arg-type]
        eligible_for_automatic_recommendation=eligible_approval,
        eligible_for_approval=eligible_approval,
        eligible_for_reserve=eligible_reserve and "SCORE_NOT_FINAL" not in unique,
        eligible_for_rejection=True,
        blocking_reasons=unique,
        warnings=warnings,
    )
