from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.repositories import decision_event_repository, dossier_repository, risk_repository
from app.domain.scoring_policy import default_policy
from app.schemas.dossier import Dossier
from app.services import dossier_store
from app.services.decision_eligibility import DecisionEligibilityResult, evaluate_decision_eligibility
from app.services.document_checklist import documents_ready_for_decision
from app.services.workspace_builder import analysis_source_fingerprint


class DecisionNotEligible(Exception):
    def __init__(self, result: DecisionEligibilityResult, message: str | None = None) -> None:
        self.result = result
        super().__init__(message or "Le dossier n’est pas éligible à cette décision.")


def _eligibility_for(record) -> DecisionEligibilityResult:
    ws = record.analyse or {}
    readiness = ws.get("readiness") or {}
    scoring = ws.get("scoring") or {}
    bam = risk_repository.get_bam(record.id)
    incidents = risk_repository.get_incidents(record.id)
    bam_status = bam.status if bam else "UNKNOWN"
    incident_status = incidents.status if incidents else "UNKNOWN"
    policy = default_policy()
    stored_fp = ws.get("analysisFingerprint")
    current_fp = analysis_source_fingerprint(record)
    stale = bool(stored_fp and stored_fp != current_fp) or bool(ws.get("analysisStale"))
    return evaluate_decision_eligibility(
        readiness_status=readiness.get("status"),
        quality_ready=bool(readiness.get("ready_for_automatic_scoring")),
        behavioral_ready=bool((ws.get("comportement") or {}).get("available")),
        sector_ready=bool((ws.get("sectorAnalysis") or {}).get("status") in {"AVAILABLE", "PARTIAL"}),
        bam_status=bam_status,
        incident_status=incident_status,
        mandatory_documents_ready=documents_ready_for_decision(record),
        analysis_stale=stale,
        score_status=scoring.get("scoreStatus") or "NOT_CALCULABLE",
        policy_require_bam=policy.require_bam_for_final_decision,
        policy_require_incidents=policy.require_incidents_check_for_final_decision,
    )


def _append_event(record, *, event_type: str, new_status: str, reason: str | None, comment: str | None) -> None:
    ws = record.analyse or {}
    scoring = ws.get("scoring") or {}
    eligibility = _eligibility_for(record)
    decision_event_repository.append(
        dossier_id=record.id,
        analysis_run_id=None,
        event_type=event_type,
        previous_status=record.status,
        new_status=new_status,
        actor_name="Analyste",
        actor_role="analyste",
        reason=reason,
        comment=comment,
        score_status=scoring.get("scoreStatus"),
        score_value=scoring.get("finalScore") or scoring.get("scoreRaw") or scoring.get("score"),
        score_class=scoring.get("classe") or None,
        scoring_policy_version=ws.get("pipeline", {}).get("policyVersion") if isinstance(ws.get("pipeline"), dict) else None,
        quality_snapshot_json=str(ws.get("quality") or {}),
        eligibility_snapshot_json=eligibility.model_dump_json(),
        analysis_fingerprint=ws.get("analysisFingerprint"),
    )


def _apply(dossier_id: str, status: str, event_type: str, reason: str | None, comment: str | None):
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _append_event(record, event_type=event_type, new_status=status, reason=reason, comment=comment)
    updated = dossier_store.update_status(dossier_id, status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    patched = dossier_store.update_analyse(dossier_id, **{})
    # decisionDate derived from last event (UTC stored separately on payload)
    dossier_repository.update_analysis(dossier_id, decisionDate=now)
    record2 = dossier_store.get_by_id(dossier_id) or updated
    return dossier_store.to_list_item(record2)


def approve(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    eligibility = _eligibility_for(record)
    if not eligibility.eligible_for_approval:
        raise DecisionNotEligible(eligibility)
    return _apply(dossier_id, "approved", "APPROVED", reason, comment)


def reserve(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    eligibility = _eligibility_for(record)
    if not eligibility.eligible_for_reserve:
        raise DecisionNotEligible(eligibility)
    return _apply(dossier_id, "reserved", "RESERVED", reason, comment)


def reject(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if not (reason or "").strip():
        raise HTTPException(status_code=422, detail="Une justification est obligatoire pour le rejet.")
    eligibility = _eligibility_for(record)
    if not eligibility.eligible_for_rejection:
        raise DecisionNotEligible(eligibility)
    return _apply(dossier_id, "rejected", "REJECTED", reason, comment)


def cancel(dossier_id: str, reason: str | None = None, comment: str | None = None) -> Dossier:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return _apply(dossier_id, "review" if record.analyse else "pending", "DECISION_CANCELLED", reason, comment)


def history(dossier_id: str) -> list[dict]:
    if not dossier_store.get_by_id(dossier_id):
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    rows = decision_event_repository.list_for_dossier(dossier_id)
    return [
        {
            "event": row.event_type,
            "actor": row.actor_name,
            "role": row.actor_role,
            "reason": row.reason,
            "comment": row.comment,
            "createdAt": row.created_at.replace(tzinfo=timezone.utc).isoformat() if row.created_at else None,
            "score": row.score_value,
            "scoreStatus": row.score_status,
            "policyVersion": row.scoring_policy_version,
        }
        for row in rows
    ]


def eligibility(dossier_id: str) -> DecisionEligibilityResult:
    record = dossier_store.get_by_id(dossier_id)
    if not record:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return _eligibility_for(record)
