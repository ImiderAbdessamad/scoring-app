"""Quality gate : extraction → validation → scoring, jamais OCR → score."""
from __future__ import annotations

from app.schemas.analyse import (
    ExtractedField,
    ExtractionQuality,
    ScoringAnalysisResult,
    ScoringReadiness,
)

_CRITICAL_CODES = {
    "FONDS_PROPRES",
    "TOTAL_BILAN",
    "CHIFFRE_AFFAIRES",
    "RESULTAT_NET",
    "CAF",
    "ENDETTEMENT_TERME",
    "DETTES_BANCAIRES_MLT",
}

_SCORING_INPUT_KEYS = (
    "fonds_propres",
    "total_bilan",
    "chiffre_affaires",
    "resultat_net",
    "dettes_financement",
    "caf",
    "fdr",
    "tresorerie_nette",
    "clients",
    "fournisseurs",
    "actifs_immobilises",
)


def evaluate_quality(result: ScoringAnalysisResult) -> tuple[ExtractionQuality, ScoringReadiness]:
    fields = [item for item in result.fields if item.code != "TYPE_RESULTAT"]
    observed_c = sum(1 for f in fields if f.current.observed_value is not None)
    usable_c = sum(1 for f in fields if f.current.usable)
    observed_p = sum(1 for f in fields if f.previous and f.previous.observed_value is not None)
    usable_p = sum(1 for f in fields if f.previous and f.previous.usable)
    suspect = sum(
        1
        for f in fields
        if f.current.status == "suspect" or (f.previous and f.previous.status == "suspect")
    )
    conflict = sum(
        1
        for f in fields
        if f.current.status == "conflicting" or (f.previous and f.previous.status == "conflicting")
    )
    cross = sum(
        1
        for f in fields
        if f.current.status == "cross_checked" or (f.previous and f.previous.status == "cross_checked")
    )
    passed = sum(1 for c in result.controls if c.status == "passed")
    failed = sum(1 for c in result.controls if c.status == "failed")
    not_eval = sum(1 for c in result.controls if c.status == "not_evaluable")
    total_fields = max(len(fields), 1)
    inputs = result.ratio_inputs or {}
    required = len(_SCORING_INPUT_KEYS)
    available = sum(1 for key in _SCORING_INPUT_KEYS if inputs.get(key) is not None)
    quality = ExtractionQuality(
        observed_current_count=observed_c,
        usable_current_count=usable_c,
        observed_previous_count=observed_p,
        usable_previous_count=usable_p,
        suspect_count=suspect,
        conflict_count=conflict,
        cross_checked_count=cross,
        passed_checks=passed,
        failed_checks=failed,
        not_evaluable_checks=not_eval,
        presence_completeness_pct=round(100.0 * observed_c / total_fields, 1),
        usable_completeness_pct=round(100.0 * usable_c / total_fields, 1),
        scoring_input_completeness_pct=round(100.0 * available / required, 1),
    )

    blocking: list[str] = []
    historical: list[str] = []
    critical_conflicts = 0
    critical_suspects = 0
    for field in fields:
        if field.code not in _CRITICAL_CODES:
            continue
        if field.current.status == "conflicting":
            critical_conflicts += 1
            blocking.append(f"{field.label} en conflit.")
        if field.previous and field.previous.status == "conflicting":
            historical.append(f"{field.label} N-1 en conflit.")
        if field.current.status == "suspect":
            critical_suspects += 1
            blocking.append(f"{field.label} suspect.")
        if field.previous and field.previous.status == "suspect":
            historical.append(f"{field.label} N-1 suspect.")
        if field.code in {"CAF", "FONDS_PROPRES", "TOTAL_BILAN", "CHIFFRE_AFFAIRES"} and not field.current.usable:
            blocking.append(f"{field.label} non utilisable pour le scoring.")
    for control in result.controls:
        failed_critical = control.status == "failed" and getattr(control, "severity", "WARNING") == "CRITICAL"
        if failed_critical and control.period in {None, "current"} and control.affects_scoring:
            blocking.append(f"Contrôle en écart — {control.label}.")
        elif control.status == "failed" and control.period == "previous":
            historical.append(f"Contrôle historique en écart — {control.label}.")
    if available < 6:
        blocking.append("Moins de 6 inputs de scoring utilisables.")

    unique_block = list(dict.fromkeys(blocking))
    accounting_failures = failed
    if critical_conflicts:
        status = "blocked"
        quality_status = "blocked"
        ready = False
    elif unique_block:
        status = "review_required"
        quality_status = "review_required"
        ready = False
    elif available < required:
        status = "review_required"
        quality_status = "warning"
        ready = False
        unique_block.append("Tous les inputs de scoring ne sont pas disponibles.")
    else:
        status = "ready"
        quality_status = "valid" if not failed else "warning"
        ready = True

    readiness = ScoringReadiness(
        ready_for_automatic_scoring=ready,
        status=status,  # type: ignore[arg-type]
        blocking_reasons=unique_block,
        scoring_inputs_required=required,
        scoring_inputs_available=available,
        scoring_inputs_usable=available,
        critical_conflicts=critical_conflicts,
        critical_suspects=critical_suspects,
        accounting_failures=accounting_failures,
        quality_status=quality_status,  # type: ignore[arg-type]
        current_period_blockers=unique_block,
        historical_period_blockers=list(dict.fromkeys(historical)),
    )
    return quality, readiness
