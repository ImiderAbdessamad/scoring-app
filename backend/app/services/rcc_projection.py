"""Projection scoring V6 → contrat RCC (affichage + export métier propre)."""
from __future__ import annotations

from typing import Any

from app.schemas.analyse import RCC_ELEMENTS, SCORING_EXTRA_ELEMENTS, ScoringAnalysisResult
from app.sector.mapping import is_plausible_activity

RCC_DISPLAY_CODES = [code for _, code, _, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)]

_LABELS = {code: label for _, code, label, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)}
_SOURCES = {code: source for _, code, label, source in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)}


def _pick(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def clean_activite(*values: Any) -> str | None:
    for value in values:
        if value in (None, ""):
            continue
        text = str(value).strip()
        if not text:
            continue
        folded = text.casefold().replace("é", "e").replace("è", "e")
        if folded.startswith("raison sociale"):
            continue
        if is_plausible_activity(text):
            return text
    return None


def build_identite(result: ScoringAnalysisResult) -> dict[str, Any]:
    identity = result.document.identity
    company = result.document.company
    exercise = result.document.exercise
    lookup = result.client_lookup
    primary = lookup.primary if lookup else None
    payload = {
        "identifiant_fiscal": _pick(
            identity.identifiant_fiscal,
            company.identifiant_fiscal,
            primary.identifiant_fiscal if primary else None,
        ),
        "ice": _pick(identity.ice, company.ice, primary.ice if primary else None),
        "raison_sociale": _pick(
            identity.raison_sociale,
            company.raison_sociale,
            primary.raison_sociale if primary else None,
        ),
        "taxe_professionnelle": _pick(identity.taxe_professionnelle, company.taxe_professionnelle),
        "ville": _pick(identity.ville, company.ville),
        "adresse": _pick(identity.adresse, company.adresse),
        "activite": clean_activite(identity.activite, company.activite),
        "secteur": clean_activite(identity.secteur, company.secteur),
        "period_start": _pick(identity.period_start, company.period_start, exercise.debut),
        "period_end": _pick(identity.period_end, company.period_end, exercise.fin),
        "declaration_date": _pick(identity.declaration_date, company.declaration_date),
        "declaration_time": _pick(identity.declaration_time, company.declaration_time),
        "reference": _pick(identity.reference, company.reference),
        "rc": _pick(company.rc, primary.rc if primary else None),
        "tiers": _pick(primary.tiers if primary else None),
    }
    if lookup is not None:
        payload["client_lookup"] = lookup.model_dump(mode="json")
        payload["matched_clients"] = [
            item.model_dump(mode="json") for item in lookup.matches
        ]
    return payload


def _snake(code: str) -> str:
    return code.lower()


def _amount(field) -> float | None:
    if field is None:
        return None
    if field.current and field.current.observed_value is not None:
        return field.current.observed_value
    return field.value


def _amount_n1(field) -> float | None:
    if field is None:
        return None
    if field.previous and field.previous.observed_value is not None:
        return field.previous.observed_value
    return field.value_n1


def project_rcc_result(result: ScoringAnalysisResult) -> dict[str, Any]:
    by_code = {item.code: item for item in result.fields}
    fields = []
    for code in RCC_DISPLAY_CODES:
        item = by_code.get(code)
        number = next((n for n, c, _, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS) if c == code), 0)
        status = (item.status if item else "missing") or "missing"
        if status == "not_evaluable":
            status = "missing"
        confidence = min(1.0, max(0.0, float(item.confidence or 0) if item else 0.0))
        evidence = []
        if item:
            for row in item.evidence or []:
                evidence.append(row.model_dump() if hasattr(row, "model_dump") else dict(row))
        fields.append(
            {
                "number": number,
                "code": code,
                "label": _LABELS.get(code, code),
                "value": _amount(item),
                "value_n1": _amount_n1(item),
                "unit": "MAD",
                "source": _SOURCES.get(code, ""),
                "status": status,
                "note": item.note if item else None,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
    identite = build_identite(result)
    return {
        "identite": identite,
        "document": {
            "filename": result.document.filename,
            "pages_total": result.document.pages_total,
            "pages_processed": result.document.pages_processed,
            "pages_skipped": result.document.pages_skipped,
            "pages_failed": result.document.pages_failed,
            "company": result.document.company.model_dump(),
            "identity": identite,
            "exercise": result.document.exercise.model_dump(),
        },
        "extraction": result.extraction.model_dump(),
        "fields": fields,
        "completeness_pct": result.completeness_pct,
        "warnings": result.extraction.warnings,
        "controls": [
            {
                **c.model_dump(),
                "status": "not_testable" if c.status == "not_evaluable" else c.status,
            }
            for c in result.controls
        ],
        "year_labels": result.years.labels,
    }


def export_rcc_clean(result: ScoringAnalysisResult) -> dict[str, Any]:
    by_code = {item.code: item for item in result.fields}
    identite = build_identite(result)

    def pair(code: str) -> dict[str, float | None]:
        item = by_code.get(code)
        return {"n": _amount(item), "n1": _amount_n1(item)}

    postes = {_snake(code): pair(code) for code in RCC_DISPLAY_CODES if code != "TYPE_RESULTAT"}
    type_item = by_code.get("TYPE_RESULTAT")
    payload = {
        **identite,
        "type_resultat": type_item.note if type_item else None,
        "postes": postes,
        "document": {
            "fichier": result.document.filename,
            "pages": result.document.pages_total,
        },
    }
    return payload
