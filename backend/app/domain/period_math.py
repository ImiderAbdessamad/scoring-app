from __future__ import annotations

from app.schemas.analyse import PeriodFieldValue

EXPLICIT_ZERO_STATUSES = {"explicit_zero", "validated_semantic_zero"}


def _is_semantic_zero(field: PeriodFieldValue) -> bool:
    if (field.accounting_status or "") in EXPLICIT_ZERO_STATUSES:
        return True
    if (field.period_status or "") in EXPLICIT_ZERO_STATUSES:
        return True
    if field.status == "blank_on_form":
        return False
    return False


def safe_sum_period_fields(
    operands: list[PeriodFieldValue],
    *,
    allow_semantic_zero: bool = True,
    accounting_status: str = "derived",
) -> PeriodFieldValue:
    """Somme uniquement si chaque opérande est utilisable ou zéro sémantique explicite."""
    total = 0.0
    confidences: list[float] = []
    evidence = []
    for operand in operands:
        if operand.usable and operand.usable_value is not None:
            total += float(operand.usable_value)
            if operand.confidence is not None:
                confidences.append(float(operand.confidence))
            evidence.extend(operand.evidence)
            continue
        if allow_semantic_zero and _is_semantic_zero(operand):
            evidence.extend(operand.evidence)
            continue
        return PeriodFieldValue(
            observed_value=None,
            usable_value=None,
            status="derived",
            usable=False,
            period_status="derived",
            accounting_status="derived_unavailable",
            evidence=evidence,
            warnings=["operand_not_usable"],
        )
    conf = min(confidences) if confidences else None
    return PeriodFieldValue(
        observed_value=total,
        usable_value=total,
        status="derived",
        usable=True,
        confidence=conf,
        period_status="derived",
        accounting_status=accounting_status,
        evidence=evidence,
    )
